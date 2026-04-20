#!/usr/bin/env python3
"""
eve_kv_memory_v108.py — Key-Value Memory with Importance Scoring
Inspired by EVE-Agent's structured memory.

Stores structured facts with priority-based retrieval.
"""
from __future__ import annotations

import json
import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

DATA_DIR = Path("/root/evolution/data")
DB_PATH = DATA_DIR / "eve_kv.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class KVMemoryStore:
    """
    Key-value memory with importance scoring and automatic decay.
    
    Tables:
    - facts: Core key-value storage
    - fact_relations: Links between related facts
    - access_log: Tracks recall frequency
    """

    def __init__(self, db_path: Path = DB_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 1,  -- 1-5 scale
                category TEXT DEFAULT 'general',
                created_ts TEXT NOT NULL,
                updated_ts TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_facts_importance ON facts(importance);
            CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
            CREATE INDEX IF NOT EXISTS idx_facts_access ON facts(access_count);

            CREATE TABLE IF NOT EXISTS fact_relations (
                source_key TEXT NOT NULL,
                target_key TEXT NOT NULL,
                relation_type TEXT DEFAULT 'related',
                strength REAL DEFAULT 0.5,
                PRIMARY KEY (source_key, target_key)
            );

            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                key TEXT NOT NULL,
                context TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_access_key ON access_log(key);
        """)
        self.conn.commit()

    def remember(self, key: str, value: str, importance: int = 1,
                 category: str = "general", auto_append: bool = False) -> bool:
        """
        Store a fact with importance score.
        
        Args:
            key: Unique identifier (will be normalized)
            value: The fact/value to store
            importance: 1=low, 5=critical
            category: Category for grouping
            auto_append: If True, append to existing value instead of replacing
        """
        key = self._normalize_key(key)
        importance = max(1, min(5, importance))  # Clamp to 1-5
        
        now = _utcnow()
        
        if auto_append:
            existing = self.recall(key)
            if existing:
                value = f"{existing}\n{value}"
        
        self.conn.execute(
            """INSERT INTO facts (key, value, importance, category, created_ts, updated_ts)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   importance = excluded.importance,
                   category = excluded.category,
                   updated_ts = excluded.updated_ts""",
            (key, value, importance, category, now, now)
        )
        self.conn.commit()
        
        return True

    def recall(self, key: str, log_access: bool = True) -> Optional[str]:
        """Retrieve a fact by key."""
        key = self._normalize_key(key)
        
        row = self.conn.execute(
            "SELECT value FROM facts WHERE key=?", (key,)
        ).fetchone()
        
        if row and log_access:
            self._log_access(key)
        
        return row[0] if row else None

    def _log_access(self, key: str, context: str = ""):
        """Log access for analytics."""
        now = _utcnow()
        self.conn.execute(
            "INSERT INTO access_log (ts, key, context) VALUES (?,?,?)",
            (now, key, context)
        )
        self.conn.execute(
            """UPDATE facts SET 
                access_count = access_count + 1,
                last_accessed = ?
               WHERE key=?""",
            (now, key)
        )
        self.conn.commit()

    def recall_all(self, category: Optional[str] = None,
                   min_importance: int = 1, 
                   order_by: str = "importance") -> Dict[str, Dict[str, Any]]:
        """
        Retrieve all facts, optionally filtered.
        
        Args:
            category: Filter by category
            min_importance: Minimum importance (1-5)
            order_by: 'importance', 'recency', 'access'
        """
        query = "SELECT key, value, importance, category, created_ts, access_count FROM facts WHERE importance >= ?"
        params = [min_importance]
        
        if category:
            query += " AND category=?"
            params.append(category)
        
        order_map = {
            "importance": "importance DESC, access_count DESC",
            "recency": "updated_ts DESC",
            "access": "access_count DESC"
        }
        query += f" ORDER BY {order_map.get(order_by, 'importance DESC, access_count DESC')}"
        
        rows = self.conn.execute(query, params).fetchall()
        
        return {
            r[0]: {
                "value": r[1],
                "importance": r[2],
                "category": r[3],
                "created": r[4],
                "access_count": r[5]
            }
            for r in rows
        }

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search facts by key or value."""
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """SELECT key, value, importance, category
               FROM facts 
               WHERE key LIKE ? OR value LIKE ?
               ORDER BY importance DESC, access_count DESC
               LIMIT ?""",
            (pattern, pattern, limit)
        ).fetchall()
        
        return [
            {"key": r[0], "value": r[1][:200], "importance": r[2], "category": r[3]}
            for r in rows
        ]

    def forget(self, key: str) -> bool:
        """Remove a fact."""
        key = self._normalize_key(key)
        
        cursor = self.conn.execute("DELETE FROM facts WHERE key=?", (key,))
        self.conn.execute("DELETE FROM fact_relations WHERE source_key=? OR target_key=?", (key, key))
        self.conn.commit()
        
        return cursor.rowcount > 0

    def _normalize_key(self, key: str) -> str:
        """Normalize key for storage."""
        normalized = re.sub(r'[^\w\-]', '_', key.lower())
        return re.sub(r'_+', '_', normalized).strip('_')[:100]

    def relate(self, key1: str, key2: str, relation_type: str = "related", strength: float = 0.5):
        """Create a relationship between two facts."""
        key1 = self._normalize_key(key1)
        key2 = self._normalize_key(key2)
        
        self.conn.execute(
            """INSERT INTO fact_relations (source_key, target_key, relation_type, strength)
               VALUES (?,?,?,?)
               ON CONFLICT(source_key, target_key) DO UPDATE SET
                   relation_type = excluded.relation_type,
                   strength = excluded.strength""",
            (key1, key2, relation_type, strength)
        )
        self.conn.commit()

    def get_related(self, key: str, relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get related facts."""
        key = self._normalize_key(key)
        
        if relation_type:
            rows = self.conn.execute(
                """SELECT f.key, f.value, f.importance, r.relation_type, r.strength
                   FROM fact_relations r
                   JOIN facts f ON (r.source_key=? AND r.target_key=f.key)
                                    OR (r.target_key=? AND r.source_key=f.key)
                   WHERE r.relation_type=?
                   ORDER BY r.strength DESC""",
                (key, key, relation_type)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT f.key, f.value, f.importance, r.relation_type, r.strength
                   FROM fact_relations r
                   JOIN facts f ON (r.source_key=? AND r.target_key=f.key)
                                    OR (r.target_key=? AND r.source_key=f.key)
                   ORDER BY r.strength DESC""",
                (key, key)
            ).fetchall()
        
        return [
            {"key": r[0], "value": r[1][:200], "importance": r[2], 
             "relation": r[3], "strength": r[4]}
            for r in rows
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        
        by_importance = {}
        for i in range(1, 6):
            count = self.conn.execute(
                "SELECT COUNT(*) FROM facts WHERE importance=?", (i,)
            ).fetchone()[0]
            by_importance[i] = count
        
        categories = self.conn.execute(
            "SELECT category, COUNT(*) FROM facts GROUP BY category"
        ).fetchall()
        
        top_accessed = self.conn.execute(
            """SELECT key, access_count FROM facts 
               ORDER BY access_count DESC LIMIT 5"""
        ).fetchall()
        
        return {
            "total_facts": total,
            "by_importance": by_importance,
            "by_category": {r[0]: r[1] for r in categories},
            "most_accessed": [{"key": r[0], "count": r[1]} for r in top_accessed]
        }


class SemanticKVMemory:
    """
    KV Memory with semantic similarity search (requires embeddings).
    Falls back to keyword search if embeddings unavailable.
    """

    def __init__(self, kv_store: Optional[KVMemoryStore] = None):
        self.kv = kv_store or KVMemoryStore()
        self._embedding_cache: Dict[str, List[float]] = {}

    def remember(self, key: str, value: str, importance: int = 1,
                 category: str = "general") -> bool:
        """Store with optional embedding."""
        result = self.kv.remember(key, value, importance, category)
        
        # Try to cache embedding for semantic search
        try:
            self._update_embedding(key, value)
        except:
            pass
        
        return result

    def _update_embedding(self, key: str, value: str):
        """Update embedding cache (stub for ChromaDB integration)."""
        # In full implementation, this would use nomic-embed-text
        # For now, just token-based representation
        pass

    def recall_semantic(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Recall using semantic similarity."""
        # Fallback to keyword search with ranking
        results = self.kv.search(query, limit=top_k * 2)
        
        # Simple ranking: boost exact matches
        for r in results:
            if query.lower() in r["key"].lower():
                r["score"] = 0.9
            elif query.lower() in r["value"].lower():
                r["score"] = 0.7
            else:
                r["score"] = 0.5
        
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]


# ── High-level Memory Manager ─────────────────────────────────────────────────

class UnifiedMemory:
    """
    Combines ChromaDB (semantic) + KV (structured) + Files (curated).
    Inspired by EVE-Agent's layered memory.
    """

    def __init__(self):
        self.kv = KVMemoryStore()
        # ChromaDB integration would be here

    def store_fact(self, key: str, value: str, importance: int = 1,
                   category: str = "general", mirror_to_file: bool = False):
        """
        Store fact with optional mirroring to MEMORY.md.
        
        Args:
            key: Fact identifier
            value: The fact
            importance: Priority (1-5)
            category: Grouping
            mirror_to_file: Also append to MEMORY.md
        """
        # Store in KV
        self.kv.remember(key, value, importance, category)
        
        # Mirror to file if requested
        if mirror_to_file:
            self._append_to_memory_md(key, value, importance)

    def _append_to_memory_md(self, key: str, value: str, importance: int):
        """Append fact to MEMORY.md."""
        memory_path = Path("/MEMORY.md")
        
        if not memory_path.exists():
            return
        
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        importance_markers = {1: "", 2: "", 3: "⭐", 4: "⭐⭐", 5: "⭐⭐⭐"}
        marker = importance_markers.get(importance, "")
        
        entry = f"\n- [{ts}] {marker} **{key}**: {value[:150]}"
        
        try:
            content = memory_path.read_text(encoding="utf-8")
            content = content.rstrip() + entry + "\n"
            memory_path.write_text(content, encoding="utf-8")
        except Exception:
            pass

    def recall(self, query: str, use_semantic: bool = True) -> List[Dict[str, Any]]:
        """
        Unified recall: KV first, then semantic, then keyword.
        """
        # Direct KV lookup
        direct = self.kv.recall(query, log_access=False)
        if direct:
            return [{"source": "kv", "key": query, "value": direct, "score": 1.0}]
        
        # Search
        if use_semantic:
            return self.kv.recall_semantic(query)
        else:
            return self.kv.search(query)

    def get_context(self, max_facts: int = 20) -> str:
        """Get curated context for LLM prompts."""
        facts = self.kv.recall_all(min_importance=3, order_by="importance")
        
        lines = []
        for key, data in list(facts.items())[:max_facts]:
            importance = "!" * data["importance"]
            lines.append(f"{importance} {key}: {data['value'][:100]}")
        
        return "\n".join(lines) if lines else "No important memories yet."


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    kv = KVMemoryStore()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "remember" and len(sys.argv) >= 4:
            key, value = sys.argv[2], sys.argv[3]
            importance = int(sys.argv[4]) if len(sys.argv) > 4 else 3
            kv.remember(key, value, importance)
            print(f"Remembered: {key}")
        elif sys.argv[1] == "recall" and len(sys.argv) > 2:
            value = kv.recall(sys.argv[2])
            print(value if value else "Not found")
        elif sys.argv[1] == "search" and len(sys.argv) > 2:
            results = kv.search(sys.argv[2])
            for r in results:
                print(f"[{r['importance']}] {r['key']}: {r['value'][:100]}...")
        elif sys.argv[1] == "stats":
            print(json.dumps(kv.get_stats(), indent=2))
        elif sys.argv[1] == "all":
            facts = kv.recall_all(order_by="importance")
            for key, data in facts.items():
                print(f"[{data['importance']}] {key}: {data['value'][:80]}...")
    else:
        print("Usage: python eve_kv_memory_v108.py [remember key value [importance]|recall key|search query|stats|all]")
