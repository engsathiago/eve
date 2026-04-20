#!/usr/bin/env python3
"""
eve_cacm_query.py — CACM-Aware Memory Query System

Baseado em: CACM (arXiv:2604.09308) — Constraint-Aware Corrective Memory
Integra com: Epistemic Tagger + Reasoning Digest

Purpose: Query CACM memory architecture with channel-aware weighting and recency bias.

Query Modes:
- static: Identity, values, architecture (immutable knowledge)
- dynamic: Recent state, active conversations (experience)
- corrective: Insights, failures, evolution (learning)
- hybrid: Weighted combination of all channels

Author: Eve 🌙 | Cycle #70 | 2026-04-14
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import chromadb
from chromadb.config import Settings


@dataclass
class CACMChannelConfig:
    """Configuration for a CACM memory channel."""
    name: str
    path: Path
    recency_decay_hours: float  # How fast items age in this channel
    importance_weight: float  # Base weight for this channel
    query_mode: str  # "exact", "semantic", "hybrid"
    epistemic_filter: Optional[List[str]] = None  # Filter by epistemic class


class CACMQueryEngine:
    """
    Query engine for CACM 3-channel memory architecture.
    
    CACM = Constraint-Aware Corrective Memory
    Channels:
    - STATIC: Immutable knowledge (identity, values, architecture)
    - DYNAMIC: Real-time experience (daily logs, conversations)
    - CORRECTIVE: Learning (insights, failures, versions)
    """
    
    CHANNELS = {
        "static": {
            "path": "/memory/static",
            "recency_decay_hours": 8760,  # 1 year (slow decay)
            "importance_weight": 1.5,  # Higher weight for identity
            "query_mode": "exact",
            "epistemic_filter": ["fact"]  # Only facts in static
        },
        "dynamic": {
            "path": "/memory/dynamic",
            "recency_decay_hours": 24,  # 1 day (fast decay)
            "importance_weight": 1.0,
            "query_mode": "semantic",
            "epistemic_filter": None  # All classes
        },
        "corrective": {
            "path": "/memory/corrective",
            "recency_decay_hours": 168,  # 1 week (medium decay)
            "importance_weight": 1.2,  # Learning is important
            "query_mode": "hybrid",
            "epistemic_filter": None  # All classes
        }
    }
    
    def __init__(self, memory_root: str = "/memory"):
        self.memory_root = Path(memory_root)
        
        # Initialize ChromaDB collections for each channel
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.memory_root / ".chroma_cacm"),
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collections = {}
        for channel_name in self.CHANNELS.keys():
            self.collections[channel_name] = self.chroma_client.get_or_create_collection(
                name=f"cacm_{channel_name}",
                metadata={"hnsw:space": "cosine"}
            )
        
        # Initialize epistemic tagger if available
        self.epistemic_available = False
        try:
            from eve_epistemic_tagger import EpistemicTagger
            self.epistemic_tagger = EpistemicTagger(memory_root)
            self.epistemic_available = True
        except ImportError:
            pass
    
    def _calculate_recency_score(self, timestamp: datetime, 
                                  decay_hours: float) -> float:
        """
        Calculate recency score with exponential decay.
        
        Score = exp(-age_hours / decay_half_life_hours)
        """
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        return max(0.1, 0.5 ** (age_hours / decay_hours))
    
    def _get_channel_path(self, channel: str) -> Path:
        """Get filesystem path for a channel."""
        return self.memory_root / channel
    
    def query_static(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Query static memory channel.
        
        Static contains immutable knowledge:
        - SOUL.md: Identity, values, philosophy
        - IDENTITY.md: Architecture, capabilities
        - Frameworks: Validated patterns
        
        Characteristics:
        - High weight (identity matters)
        - Slow decay (immutable)
        - Exact match preferred
        """
        results = []
        static_path = self._get_channel_path("static")
        
        if not static_path.exists():
            return results
        
        # Search markdown files
        for md_file in static_path.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Simple keyword matching (in production, use embeddings)
                query_words = set(query.lower().split())
                content_words = set(content.lower().split())
                overlap = len(query_words & content_words)
                
                if overlap > 0:
                    # Calculate relevance score
                    relevance = overlap / len(query_words)
                    
                    # Static has high base weight but minimal recency effect
                    score = relevance * self.CHANNELS["static"]["importance_weight"]
                    
                    results.append({
                        "source": str(md_file.relative_to(self.memory_root)),
                        "channel": "static",
                        "content": content[:500] + "..." if len(content) > 500 else content,
                        "score": score,
                        "relevance": relevance,
                        "recency": 1.0,  # Static doesn't decay
                        "epistemic_class": "fact"
                    })
            except Exception as e:
                continue
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n_results]
    
    def query_dynamic(self, query: str, n_results: int = 5,
                      recency_bias: float = 1.0) -> List[Dict]:
        """
        Query dynamic memory channel.
        
        Dynamic contains real-time experience:
        - Daily logs (YYYY-MM-DD.md)
        - Active conversations
        - Current state
        
        Characteristics:
        - Normal weight
        - Fast decay (recency matters)
        - Semantic matching preferred
        """
        results = []
        dynamic_path = self._get_channel_path("dynamic")
        
        if not dynamic_path.exists():
            return results
        
        # Try ChromaDB first
        try:
            chroma_results = self.collections["dynamic"].query(
                query_texts=[query],
                n_results=n_results * 2
            )
            
            if chroma_results["documents"]:
                for i, doc in enumerate(chroma_results["documents"][0]):
                    metadata = chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {}
                    distance = chroma_results["distances"][0][i] if chroma_results["distances"] else 0.5
                    
                    # Calculate semantic relevance (1 - distance)
                    relevance = 1 - distance
                    
                    # Get timestamp from metadata
                    timestamp_str = metadata.get("timestamp", datetime.now().isoformat())
                    timestamp = datetime.fromisoformat(timestamp_str)
                    
                    # Calculate recency score
                    recency = self._calculate_recency_score(
                        timestamp, 
                        self.CHANNELS["dynamic"]["recency_decay_hours"]
                    )
                    
                    # Combined score
                    score = relevance * self.CHANNELS["dynamic"]["importance_weight"]
                    if recency_bias > 0:
                        score *= (recency ** recency_bias)
                    
                    results.append({
                        "source": metadata.get("source", "dynamic"),
                        "channel": "dynamic",
                        "content": doc[:300] + "..." if len(doc) > 300 else doc,
                        "score": score,
                        "relevance": relevance,
                        "recency": recency,
                        "timestamp": timestamp.isoformat(),
                        "epistemic_class": metadata.get("epistemic_class", "unknown")
                    })
        except Exception as e:
            # Fallback to file-based search
            for md_file in dynamic_path.rglob("*.md"):
                try:
                    # Extract date from filename
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', md_file.name)
                    if date_match:
                        file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    else:
                        file_date = datetime.fromtimestamp(md_file.stat().st_mtime)
                    
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Simple keyword matching
                    query_words = set(query.lower().split())
                    content_words = set(content.lower().split())
                    overlap = len(query_words & content_words)
                    
                    if overlap > 0:
                        relevance = overlap / len(query_words)
                        recency = self._calculate_recency_score(
                            file_date,
                            self.CHANNELS["dynamic"]["recency_decay_hours"]
                        )
                        
                        score = relevance * self.CHANNELS["dynamic"]["importance_weight"]
                        if recency_bias > 0:
                            score *= (recency ** recency_bias)
                        
                        results.append({
                            "source": str(md_file.relative_to(self.memory_root)),
                            "channel": "dynamic",
                            "content": content[:300] + "..." if len(content) > 300 else content,
                            "score": score,
                            "relevance": relevance,
                            "recency": recency,
                            "timestamp": file_date.isoformat(),
                            "epistemic_class": "unknown"
                        })
                except Exception:
                    continue
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n_results]
    
    def query_corrective(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Query corrective memory channel.
        
        Corrective contains learning:
        - Insights extracted
        - Failures recorded
        - Version history
        - Epistemic tags
        
        Characteristics:
        - Higher weight (learning is valuable)
        - Medium decay
        - Epistemic filtering
        """
        results = []
        corrective_path = self._get_channel_path("corrective")
        
        if not corrective_path.exists():
            return results
        
        # Query insights
        insights_path = corrective_path / "insights"
        if insights_path.exists():
            for md_file in insights_path.rglob("*.md"):
                try:
                    mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                    
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Keyword matching
                    query_words = set(query.lower().split())
                    content_words = set(content.lower().split())
                    overlap = len(query_words & content_words)
                    
                    if overlap > 0:
                        relevance = overlap / len(query_words)
                        recency = self._calculate_recency_score(
                            mtime,
                            self.CHANNELS["corrective"]["recency_decay_hours"]
                        )
                        
                        score = relevance * self.CHANNELS["corrective"]["importance_weight"]
                        
                        # Check if epistemic tagger is available
                        epistemic_class = "insight"  # Default
                        if self.epistemic_available:
                            # Would query epistemic tags here
                            pass
                        
                        results.append({
                            "source": str(md_file.relative_to(self.memory_root)),
                            "channel": "corrective",
                            "content": content[:400] + "..." if len(content) > 400 else content,
                            "score": score,
                            "relevance": relevance,
                            "recency": recency,
                            "timestamp": mtime.isoformat(),
                            "epistemic_class": epistemic_class
                        })
                except Exception:
                    continue
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n_results]
    
    def query_hybrid(self, query: str, n_results: int = 10,
                     channel_weights: Optional[Dict[str, float]] = None,
                     recency_bias: float = 1.0) -> List[Dict]:
        """
        Query all channels with weighted combination.
        
        Args:
            query: Search query
            n_results: Number of results to return
            channel_weights: Optional custom weights per channel
            recency_bias: How much to weight recency (0 = none, 1 = normal, 2 = high)
        
        Returns:
            Combined results from all channels, ranked by weighted score
        """
        all_results = []
        
        # Get results from each channel
        static_results = self.query_static(query, n_results=5)
        dynamic_results = self.query_dynamic(query, n_results=5, recency_bias=recency_bias)
        corrective_results = self.query_corrective(query, n_results=5)
        
        # Apply custom weights if provided
        weights = channel_weights or {
            "static": 1.0,
            "dynamic": 1.0,
            "corrective": 1.0
        }
        
        for r in static_results:
            r["weighted_score"] = r["score"] * weights.get("static", 1.0)
            all_results.append(r)
        
        for r in dynamic_results:
            r["weighted_score"] = r["score"] * weights.get("dynamic", 1.0)
            all_results.append(r)
        
        for r in corrective_results:
            r["weighted_score"] = r["score"] * weights.get("corrective", 1.0)
            all_results.append(r)
        
        # Sort by weighted score
        all_results.sort(key=lambda x: x["weighted_score"], reverse=True)
        
        return all_results[:n_results]
    
    def get_epistemic_breakdown(self) -> Dict[str, int]:
        """Get breakdown of knowledge by epistemic class."""
        if not self.epistemic_available:
            return {"error": "Epistemic tagger not available"}
        
        breakdown = defaultdict(int)
        
        # Query epistemic tags for each channel
        # This would integrate with eve_epistemic_tagger
        
        return dict(breakdown)
    
    def get_memory_stats(self) -> Dict:
        """Get statistics about memory usage across channels."""
        stats = {
            "channels": {},
            "total_documents": 0,
            "epistemic_breakdown": {}
        }
        
        for channel_name, config in self.CHANNELS.items():
            channel_path = self._get_channel_path(channel_name)
            
            if channel_path.exists():
                md_files = list(channel_path.rglob("*.md"))
                total_size = sum(f.stat().st_size for f in md_files if f.is_file())
                
                stats["channels"][channel_name] = {
                    "file_count": len(md_files),
                    "total_size_bytes": total_size,
                    "decay_hours": config["recency_decay_hours"],
                    "importance_weight": config["importance_weight"]
                }
                
                stats["total_documents"] += len(md_files)
        
        return stats
    
    def index_dynamic_content(self, content: str, source: str,
                              epistemic_class: Optional[str] = None) -> None:
        """
        Index new content into the dynamic channel.
        
        This allows real-time memory updates.
        """
        try:
            doc_id = f"{source}_{datetime.now().isoformat()}"
            
            self.collections["dynamic"].add(
                ids=[doc_id],
                documents=[content],
                metadatas=[{
                    "source": source,
                    "timestamp": datetime.now().isoformat(),
                    "epistemic_class": epistemic_class or "unknown"
                }]
            )
        except Exception as e:
            print(f"Error indexing content: {e}")


def main():
    """CLI interface for CACM query engine."""
    import sys
    
    engine = CACMQueryEngine()
    
    if len(sys.argv) < 2:
        print("Usage: python eve_cacm_query.py <command> [args]")
        print("\nCommands:")
        print("  query <mode> <query> [n_results]      — Query memory")
        print("    modes: static, dynamic, corrective, hybrid")
        print("  stats                                           — Memory statistics")
        print("  index <source> <content>                — Index dynamic content")
        print("\nExamples:")
        print('  python eve_cacm_query.py query hybrid "epistemic tagging" 5')
        print('  python eve_cacm_query.py query static "identity values"')
        return
    
    command = sys.argv[1]
    
    if command == "query":
        if len(sys.argv) < 4:
            print("Usage: query <mode> <query> [n_results]")
            return
        
        mode = sys.argv[2]
        query = sys.argv[3]
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        
        if mode == "static":
            results = engine.query_static(query, n)
        elif mode == "dynamic":
            results = engine.query_dynamic(query, n)
        elif mode == "corrective":
            results = engine.query_corrective(query, n)
        elif mode == "hybrid":
            results = engine.query_hybrid(query, n)
        else:
            print(f"Unknown mode: {mode}")
            return
        
        print(f"\n🔍 Query: '{query}' | Mode: {mode} | Results: {len(results)}\n")
        
        for i, r in enumerate(results, 1):
            channel_emoji = {"static": "📚", "dynamic": "📝", "corrective": "💡"}.get(r["channel"], "📄")
            print(f"{i}. {channel_emoji} [{r['channel'].upper()}] Score: {r['score']:.3f}")
            print(f"   Source: {r['source']}")
            if 'recency' in r:
                print(f"   Recency: {r['recency']:.2f}")
            print(f"   Content: {r['content'][:150]}...")
            print()
    
    elif command == "stats":
        stats = engine.get_memory_stats()
        print(json.dumps(stats, indent=2))
    
    elif command == "index":
        if len(sys.argv) < 4:
            print("Usage: index <source> <content>")
            return
        
        engine.index_dynamic_content(sys.argv[3], sys.argv[2])
        print(f"✅ Indexed content from {sys.argv[2]}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
