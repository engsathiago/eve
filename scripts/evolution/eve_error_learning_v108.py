#!/usr/bin/env python3
"""
eve_error_learning_v108.py — Error Learning System
Inspired by EVE-Agent's error learning layer.

Adapts behavior based on past failures without human intervention.
"""
from __future__ import annotations

import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

DATA_DIR = Path("/root/evolution/data")
DB_PATH = DATA_DIR / "eve_learning.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_context(tool: str, input_data: str) -> str:
    """Create a hash of the context for similarity matching."""
    content = f"{tool}:{input_data}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


class ErrorLearningStore:
    """
    SQLite-backed error learning with pattern recognition.
    
    Tables:
    - errors: Raw error logs with context
    - error_patterns: Aggregated patterns from similar errors
    - tool_adaptations: Learned adaptations per tool
    """

    def __init__(self, db_path: Path = DB_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                tool TEXT NOT NULL,
                input TEXT NOT NULL,
                context_hash TEXT NOT NULL,
                error TEXT NOT NULL,
                error_type TEXT,
                learned TEXT DEFAULT '',
                adapted_attempt INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_errors_tool ON errors(tool);
            CREATE INDEX IF NOT EXISTS idx_errors_hash ON errors(context_hash);
            CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors(ts);

            CREATE TABLE IF NOT EXISTS error_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_hash TEXT UNIQUE NOT NULL,
                tool TEXT NOT NULL,
                error_pattern TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                learned_strategy TEXT DEFAULT '',
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tool_adaptations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL UNIQUE,
                adaptation TEXT NOT NULL,
                created_ts TEXT NOT NULL,
                success_rate REAL DEFAULT 0.0,
                uses INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def log_error(self, tool: str, input_data: str, error: str, 
                  learned: str = "", error_type: Optional[str] = None) -> int:
        """
        Log an error with context for future learning.
        
        Args:
            tool: Tool name that failed
            input_data: Input that caused the error
            error: Error message
            learned: What was learned from this error
            error_type: Classification (e.g., "timeout", "permission", "not_found")
        """
        context_hash = _hash_context(tool, input_data)
        
        cursor = self.conn.execute(
            """INSERT INTO errors (ts, tool, input, context_hash, error, error_type, learned)
               VALUES (?,?,?,?,?,?,?)""",
            (_utcnow(), tool, input_data, context_hash, error, error_type or "unknown", learned)
        )
        self.conn.commit()
        
        # Update pattern aggregation
        self._update_pattern(tool, context_hash, error, error_type)
        
        return cursor.lastrowid

    def _update_pattern(self, tool: str, context_hash: str, error: str, error_type: Optional[str]):
        """Aggregate similar errors into patterns."""
        pattern = self._extract_pattern(error)
        pattern_hash = hashlib.md5(f"{tool}:{pattern}".encode()).hexdigest()[:16]
        
        now = _utcnow()
        self.conn.execute(
            """INSERT INTO error_patterns (pattern_hash, tool, error_pattern, first_seen, last_seen)
               VALUES (?,?,?,?,?)
               ON CONFLICT(pattern_hash) DO UPDATE SET
                   frequency = frequency + 1,
                   last_seen = excluded.last_seen""",
            (pattern_hash, tool, pattern, now, now)
        )
        self.conn.commit()

    def _extract_pattern(self, error: str) -> str:
        """Extract a generalized pattern from error message."""
        # Remove specific values (paths, IDs, timestamps)
        patterns = [
            (r'/[\w/]+', '[PATH]'),
            (r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}', '[TIMESTAMP]'),
            (r'0x[0-9a-fA-F]+', '[ADDR]'),
            (r'\d+\.\d+\.\d+\.\d+', '[IP]'),
            (r'[a-f0-9]{8}-[a-f0-9]{4}', '[UUID]'),
        ]
        
        result = error
        for regex, replacement in patterns:
            import re
            result = re.sub(regex, replacement, result)
        
        return result[:500]  # Limit size

    def get_recent_errors(self, tool: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent errors, optionally filtered by tool."""
        if tool:
            rows = self.conn.execute(
                """SELECT tool, input, error, learned, ts, adapted_attempt
                   FROM errors WHERE tool=? ORDER BY id DESC LIMIT ?""",
                (tool, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT tool, input, error, learned, ts, adapted_attempt
                   FROM errors ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        
        return [{"tool": r[0], "input": r[1][:200], "error": r[2][:300], 
                 "learned": r[3], "ts": r[4], "attempts": r[5]} for r in rows]

    def get_similar_errors(self, tool: str, input_data: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find errors with similar context."""
        context_hash = _hash_context(tool, input_data)
        
        rows = self.conn.execute(
            """SELECT tool, input, error, learned, adapted_attempt
               FROM errors 
               WHERE tool=? AND context_hash=? AND adapted_attempt > 0
               ORDER BY ts DESC LIMIT ?""",
            (tool, context_hash, limit)
        ).fetchall()
        
        return [{"input": r[1][:200], "error": r[2][:300], "learned": r[3], 
                 "attempts": r[4]} for r in rows]

    def get_learned_strategy(self, tool: str, input_data: str) -> Optional[str]:
        """
        Get a learned strategy for avoiding similar errors.
        Returns None if no applicable strategy found.
        """
        context_hash = _hash_context(tool, input_data)
        
        # Check for successful adaptations
        row = self.conn.execute(
            """SELECT learned FROM errors 
               WHERE tool=? AND context_hash=? AND learned != ''
               ORDER BY adapted_attempt DESC LIMIT 1""",
            (tool, context_hash)
        ).fetchone()
        
        if row:
            return row[0]
        
        # Check tool-level adaptations
        adaptation = self.conn.execute(
            "SELECT adaptation FROM tool_adaptations WHERE tool=? ORDER BY success_rate DESC LIMIT 1",
            (tool,)
        ).fetchone()
        
        return adaptation[0] if adaptation else None

    def mark_adapted(self, error_id: int, success: bool):
        """Mark an error as having an adaptation attempted."""
        self.conn.execute(
            "UPDATE errors SET adapted_attempt = adapted_attempt + 1 WHERE id=?",
            (error_id,)
        )
        self.conn.commit()

    def save_tool_adaptation(self, tool: str, adaptation: str):
        """Save a general adaptation strategy for a tool."""
        now = _utcnow()
        self.conn.execute(
            """INSERT INTO tool_adaptations (tool, adaptation, created_ts)
               VALUES (?,?,?)
               ON CONFLICT(tool) DO UPDATE SET
                   adaptation = excluded.adaptation,
                   created_ts = excluded.created_ts""",
            (tool, adaptation, now)
        )
        self.conn.commit()

    def update_adaptation_success(self, tool: str, success: bool):
        """Update success rate of a tool adaptation."""
        row = self.conn.execute(
            "SELECT success_rate, uses FROM tool_adaptations WHERE tool=?",
            (tool,)
        ).fetchone()
        
        if row:
            current_rate, uses = row
            new_uses = uses + 1
            # Bayesian update
            new_rate = (current_rate * uses + (1.0 if success else 0.0)) / new_uses
            self.conn.execute(
                "UPDATE tool_adaptations SET success_rate=?, uses=? WHERE tool=?",
                (new_rate, new_uses, tool)
            )
            self.conn.commit()

    def get_error_stats(self) -> Dict[str, Any]:
        """Get statistics on errors and learning."""
        total = self.conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        learned = self.conn.execute(
            "SELECT COUNT(*) FROM errors WHERE learned != ''"
        ).fetchone()[0]
        patterns = self.conn.execute("SELECT COUNT(*) FROM error_patterns").fetchone()[0]
        adaptations = self.conn.execute(
            "SELECT COUNT(*) FROM tool_adaptations"
        ).fetchone()[0]
        
        return {
            "total_errors": total,
            "errors_with_lessons": learned,
            "patterns_identified": patterns,
            "tool_adaptations": adaptations,
            "learning_rate": learned / total if total > 0 else 0
        }


class ErrorLearner:
    """
    High-level interface for error learning integration.
    Use this to wrap tool calls with automatic learning.
    """

    def __init__(self, store: Optional[ErrorLearningStore] = None):
        self.store = store or ErrorLearningStore()

    def before_call(self, tool: str, input_data: str) -> Optional[str]:
        """
        Check for learned strategies before calling a tool.
        Returns advice string or None.
        """
        strategy = self.store.get_learned_strategy(tool, input_data)
        if strategy:
            return f"[Learned] {strategy}"
        
        # Check recent similar errors
        similar = self.store.get_similar_errors(tool, input_data, limit=2)
        if similar:
            lessons = [s["learned"] for s in similar if s["learned"]]
            if lessons:
                return f"[Similar errors] Lessons: {'; '.join(lessons[:2])}"
        
        return None

    def after_call(self, tool: str, input_data: str, success: bool, 
                   result: Any = None, error: Optional[str] = None) -> str:
        """
        Log result and return what was learned.
        Call this after every tool execution.
        """
        if success:
            return "Success"
        
        # Determine error type
        error_type = self._classify_error(error or "unknown")
        
        # Generate learned message
        learned = self._generate_lesson(tool, input_data, error, error_type)
        
        # Log it
        self.store.log_error(tool, input_data, error or "unknown", learned, error_type)
        
        return learned

    def _classify_error(self, error: str) -> str:
        """Classify error into types for pattern matching."""
        error_lower = error.lower()
        
        patterns = {
            "timeout": ["timeout", "timed out", "deadline"],
            "permission": ["permission denied", "unauthorized", "access denied", "forbidden"],
            "not_found": ["not found", "doesn't exist", "no such file", "404"],
            "rate_limit": ["rate limit", "too many requests", "429", "throttled"],
            "format": ["invalid format", "parse error", "json", "malformed"],
            "network": ["connection", "network", "unreachable", "refused"],
            "memory": ["memory", "oom", "out of memory", "ram"],
            "auth": ["authentication", "unauthorized", "token", "api key"]
        }
        
        for error_type, keywords in patterns.items():
            if any(kw in error_lower for kw in keywords):
                return error_type
        
        return "unknown"

    def _generate_lesson(self, tool: str, input_data: str, error: str, error_type: str) -> str:
        """Generate a learned lesson from an error."""
        lessons = {
            "timeout": "Add timeout parameter or retry with exponential backoff",
            "permission": "Check permissions before execution; use elevated if safe",
            "not_found": "Verify path/file exists; create if missing and appropriate",
            "rate_limit": "Add delays between calls; cache results; batch requests",
            "format": "Validate input format before calling; add error handling",
            "network": "Retry with exponential backoff; check connectivity first",
            "memory": "Process in smaller chunks; close resources explicitly",
            "auth": "Verify credentials are set; refresh tokens if needed"
        }
        
        base_lesson = lessons.get(error_type, "Add defensive checks before execution")
        
        # Tool-specific refinements
        if tool == "web_search" and error_type == "rate_limit":
            base_lesson += "; consider using cached results or alternative search"
        elif tool == "file_read" and error_type == "not_found":
            base_lesson += "; use file_list to check existence first"
        elif tool == "exec" and error_type == "permission":
            base_lesson += "; check if elevated=True is appropriate"
        
        return base_lesson


# ── Tool wrappers for integration ─────────────────────────────────────────────

def wrap_tool_with_learning(tool_fn, tool_name: str):
    """
    Wrap a tool function with error learning.
    
    Usage:
        from eve.tools import web_search
        web_search_learning = wrap_tool_with_learning(web_search, "web_search")
    """
    learner = ErrorLearner()
    
    def wrapped(*args, **kwargs):
        input_repr = json.dumps({"args": args, "kwargs": kwargs}, default=str)[:500]
        
        # Check for learned strategies
        advice = learner.before_call(tool_name, input_repr)
        if advice:
            print(f"💡 {advice}")
        
        try:
            result = tool_fn(*args, **kwargs)
            learner.after_call(tool_name, input_repr, success=True, result=result)
            return result
        except Exception as e:
            error_str = str(e)
            learned = learner.after_call(tool_name, input_repr, success=False, error=error_str)
            print(f"❌ Error logged. Learned: {learned}")
            raise
    
    return wrapped


# ── CLI for testing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    learner = ErrorLearner()
    store = ErrorLearningStore()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            stats = store.get_error_stats()
            print(json.dumps(stats, indent=2))
        elif sys.argv[1] == "recent":
            tool = sys.argv[2] if len(sys.argv) > 2 else ""
            errors = store.get_recent_errors(tool, limit=5)
            for e in errors:
                print(f"[{e['ts']}] {e['tool']}: {e['error'][:100]}...")
                if e['learned']:
                    print(f"  → Learned: {e['learned']}")
        elif sys.argv[1] == "test":
            # Simulate error learning
            store.log_error("web_search", '{"query": "test"}', 
                          "Rate limit exceeded", 
                          "Add delay between searches")
            print("Test error logged. Stats:")
            print(json.dumps(store.get_error_stats(), indent=2))
    else:
        print("Usage: python eve_error_learning_v108.py [stats|recent [tool]|test]")
