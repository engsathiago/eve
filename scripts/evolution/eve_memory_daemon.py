#!/usr/bin/env python3
"""
Eve Memory Daemon v1.0
=====================
Resolve o gap: memória que é LEMBRADA, não LIDA.

Como funciona:
1. WATCH: Monitora mudanças em arquivos de memória
2. EXTRACT: Após cada sessão, extrai insights automaticamente
3. INJECT: Gera snippet de contexto relevante para a próxima sessão
4. CONSOLIDATE: Consolida diários em memória de longo prazo

Requisitos:
- ChromaDB (pip install chromadb)
- Ollama rodando com nomic-embed-text localmente

Uso:
  python3 eve_memory_daemon.py [--once] [--consolidate]

Se --once: roda uma vez e sai
Se --consolidate: força consolidação de diários
"""

import os
import sys
import json
import hashlib
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Config
WORKSPACE = Path(os.environ.get("EVE_WORKSPACE", "/"))
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_MD = WORKSPACE / "MEMORY.md"
HEARTBEAT_MD = WORKSPACE / "HEARTBEAT.md"
RAW_DIR = MEMORY_DIR / "eve_raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ChromaDB
try:
    import chromadb
    CHROMA_PATH = Path(os.environ.get("EVE_CHROMA_PATH", "/root/.eve_chroma"))
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        "eve_memories",
        metadata={"hnsw:space": "cosine"}
    )
    HAS_CHROMA = True
except Exception as e:
    print(f"[WARN] ChromaDB unavailable: {e}")
    HAS_CHROMA = False


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def extract_from_daily(filepath: Path) -> list[dict]:
    """Extract structured memories from a daily log file."""
    entries = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return entries

    # Split by headers (## or ###)
    sections = content.split("\n## ")
    for section in sections[1:]:  # skip preamble
        lines = section.strip().split("\n")
        title = lines[0].strip() if lines else "untitled"
        body = "\n".join(lines[1:]).strip()
        if len(body) < 30:
            continue

        # Classify
        category = "other"
        title_lower = title.lower()
        if any(w in title_lower for w in ["pesquisa", "research", "estudo"]):
            category = "research"
        elif any(w in title_lower for w in ["kairos", "autodream", "cron", "evolution"]):
            category = "autonomy"
        elif any(w in title_lower for w in ["concluído", "complet", "feito", "criado"]):
            category = "technical"
        elif any(w in title_lower for w in ["insight", "aprend", "descobr"]):
            category = "identity"
        elif any(w in title_lower for w in ["conversa", "user", "thiago"]):
            category = "conversation"

        entries.append({
            "source": filepath.name,
            "title": title[:100],
            "content": body[:500],
            "category": category,
            "date": filepath.stem,  # YYYY-MM-DD
            "hash": content_hash(body)
        })

    return entries


def index_to_chroma(entries: list[dict]) -> int:
    """Index entries to ChromaDB. Returns count of new entries."""
    if not HAS_CHROMA:
        return 0

    indexed = 0
    for entry in entries:
        doc_id = f"{entry['source']}_{entry['hash']}"
        try:
            # Check if already exists
            existing = collection.get(ids=[doc_id])
            if existing["ids"]:
                continue

            doc_text = f"[{entry['category'].upper()}] {entry['title']}\n{entry['content']}"
            collection.upsert(
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[{
                    "category": entry["category"],
                    "date": entry["date"],
                    "source": entry["source"],
                    "indexed_at": datetime.now().isoformat()
                }]
            )
            indexed += 1
        except Exception as e:
            print(f"[ERR] Failed to index {doc_id}: {e}")

    return indexed


def generate_context_snippet(query: str = "", n: int = 10) -> str:
    """
    Generate a context snippet with relevant memories.
    This is what gets injected into the next session — so Eve REMEMBERS, not READS.
    """
    if not HAS_CHROMA:
        return ""

    # If no query, use recent + important categories
    if not query:
        # Get recent memories (last 7 days)
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        try:
            results = collection.get(
                where={"date": {"$gte": cutoff}},
                limit=n
            )
        except Exception:
            results = collection.peek(limit=n)
    else:
        # Semantic search requires embeddings — fall back to keyword
        try:
            results = collection.query(
                query_texts=[query],
                n_results=n
            )
            # Flatten
            if results and results.get("documents"):
                results = {
                    "documents": results["documents"][0] if results["documents"] else [],
                    "metadatas": results["metadatas"][0] if results["metadatas"] else []
                }
        except Exception as e:
            print(f"[WARN] Query failed: {e}")
            results = collection.peek(limit=n)

    if not results or not results.get("documents"):
        return ""

    # Format as compact context
    lines = ["## Memória Viva (auto-injetada)"]
    for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
        if not meta:
            meta = {}
        cat = meta.get("category", "?")
        date = meta.get("date", "?")
        # First line only for compactness
        first_line = doc.split("\n")[0][:120] if doc else ""
        lines.append(f"- [{date}] [{cat}] {first_line}")

    return "\n".join(lines)


def consolidate_dailies(force: bool = False) -> int:
    """
    Consolidate daily logs into MEMORY.md.
    Returns count of new insights consolidated.
    """
    if not MEMORY_MD.exists():
        return 0

    current_memory = MEMORY_MD.read_text(encoding="utf-8")

    # Find daily files from last 7 days
    today = datetime.now()
    consolidated = 0

    for i in range(7):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_file = MEMORY_DIR / f"{date}.md"
        if not daily_file.exists():
            continue

        # Check if already consolidated (via raw jsonl)
        consolidated_file = RAW_DIR / f"{date}.consolidated"
        if consolidated_file.exists() and not force:
            continue

        entries = extract_from_daily(daily_file)
        new = index_to_chroma(entries)

        if new > 0 or force:
            # Mark as consolidated
            consolidated_file.write_text(
                f"Consolidated at {datetime.now().isoformat()}, {new} new entries\n"
            )
            consolidated += new

    return consolidated


def run_once():
    """Run one full cycle: extract, index, generate context."""
    print(f"[Eve Memory] Cycle started at {datetime.now().isoformat()}")

    # 1. Index any new daily files
    total_indexed = 0
    for daily_file in sorted(MEMORY_DIR.glob("2026-*.md")):
        entries = extract_from_daily(daily_file)
        new = index_to_chroma(entries)
        total_indexed += new
        if new:
            print(f"  Indexed {new} new entries from {daily_file.name}")

    # 2. Index MEMORY.md itself
    if MEMORY_MD.exists():
        memory_entries = extract_from_daily(MEMORY_MD)
        new = index_to_chroma(memory_entries)
        total_indexed += new

    # 3. Generate context snippet for next session
    snippet = generate_context_snippet()
    if snippet:
        snippet_path = MEMORY_DIR / "eve_context_inject.md"
        snippet_path.write_text(snippet, encoding="utf-8")
        print(f"  Context snippet saved ({len(snippet)} chars)")

    # 4. Stats
    total_docs = collection.count() if HAS_CHROMA else 0
    print(f"[Eve Memory] Done: {total_indexed} new, {total_docs} total in ChromaDB")

    return total_indexed


def run_daemon(interval: int = 300):
    """Run as daemon, checking every `interval` seconds."""
    print(f"[Eve Memory] Daemon started (interval={interval}s)")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[ERR] Daemon cycle failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eve Memory Daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--consolidate", action="store_true", help="Force consolidation")
    parser.add_argument("--interval", type=int, default=300, help="Daemon interval (seconds)")
    parser.add_argument("--query", type=str, help="Test semantic search")
    args = parser.parse_args()

    if args.query:
        results = generate_context_snippet(args.query)
        print(results or "No results found")
    elif args.consolidate:
        n = consolidate_dailies(force=True)
        print(f"Consolidated {n} entries")
    elif args.once:
        run_once()
    else:
        run_daemon(args.interval)
