#!/usr/bin/env python3
"""
eve_memory_loop.py — Self-Consolidating Memory System

Inspired by MemGPT/Letta sleep-time processing + Claude Code KAIROS.
Radically simple: consolidate or forget.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib


class EveMemoryLoop:
    """
    Self-consolidating memory system.
    
    Principles:
    1. Working memory is small and ephemeral
    2. Archive memory is large but requires retrieval
    3. Sleep-time: consolidate working → archive
    4. Wake-time: retrieve relevant from archive
    
    No complex hierarchies. Just: now | later | never.
    """
    
    def __init__(self, 
                 working_dir: str = "/root/evolution/memory/working",
                 archive_dir: str = "/root/evolution/memory/archive",
                 max_working_items: int = 20,
                 consolidation_threshold: int = 5):
        
        self.working_dir = Path(working_dir)
        self.archive_dir = Path(archive_dir)
        self.max_working_items = max_working_items
        self.consolidation_threshold = consolidation_threshold
        
        # Ensure directories exist
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Working memory (hot, recent, small)
        self.working: List[Dict] = []
        
        # Load existing working memory
        self._load_working()
    
    def _load_working(self) -> None:
        """Load working memory from disk."""
        working_file = self.working_dir / "working.json"
        if working_file.exists():
            with open(working_file, 'r') as f:
                self.working = json.load(f)
    
    def _save_working(self) -> None:
        """Persist working memory."""
        working_file = self.working_dir / "working.json"
        with open(working_file, 'w') as f:
            json.dump(self.working, f, indent=2)
    
    def add(self, content: str, source: str = "unknown", 
            priority: int = 5, tags: List[str] = None) -> str:
        """
        Add item to working memory.
        
        Args:
            content: The memory content
            source: Where this came from (file, conversation, etc.)
            priority: 1-10 (10 = critical, consolidate immediately)
            tags: Categories for retrieval
        
        Returns:
            Memory ID
        """
        memory_id = hashlib.md5(f"{content}{datetime.now()}".encode()).hexdigest()[:12]
        
        memory = {
            "id": memory_id,
            "content": content,
            "source": source,
            "priority": priority,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "accessed": 0,
            "consolidated": False
        }
        
        self.working.append(memory)
        
        # If working memory full, trigger consolidation
        if len(self.working) > self.max_working_items:
            self.consolidate()
        
        self._save_working()
        
        return memory_id
    
    def get(self, memory_id: str) -> Optional[Dict]:
        """Retrieve specific item from working memory."""
        for item in self.working:
            if item["id"] == memory_id:
                item["accessed"] += 1
                self._save_working()
                return item
        return None
    
    def search_working(self, query: str) -> List[Dict]:
        """Simple text search in working memory."""
        query_lower = query.lower()
        results = []
        
        for item in self.working:
            if (query_lower in item["content"].lower() or
                any(query_lower in tag.lower() for tag in item["tags"])):
                item["accessed"] += 1
                results.append(item)
        
        # Sort by priority, then recency
        results.sort(key=lambda x: (-x["priority"], x["created"]), reverse=True)
        
        self._save_working()
        return results
    
    def consolidate(self) -> Dict[str, int]:
        """
        Consolidate working memory into archive.
        
        Strategy:
        - High priority (>7): Archive immediately
        - Medium priority (4-7): Archive if old or frequently accessed
        - Low priority (<4): Discard unless frequently accessed
        
        Returns:
            Stats: {archived: int, discarded: int, kept: int}
        """
        stats = {"archived": 0, "discarded": 0, "kept": 0}
        
        now = datetime.now()
        new_working = []
        
        for item in self.working:
            age_days = (now - datetime.fromisoformat(item["created"])).days
            
            # Decision logic
            should_archive = False
            should_discard = False
            
            if item["priority"] >= 8:
                should_archive = True
            elif item["priority"] >= 5:
                if item["accessed"] >= 2 or age_days > 7:
                    should_archive = True
                else:
                    should_discard = True
            else:
                if item["accessed"] >= 3:
                    should_archive = True
                else:
                    should_discard = True
            
            # Execute decision
            if should_archive:
                self._archive_item(item)
                stats["archived"] += 1
            elif should_discard:
                stats["discarded"] += 1
            else:
                new_working.append(item)
                stats["kept"] += 1
        
        self.working = new_working
        self._save_working()
        
        return stats
    
    def _archive_item(self, item: Dict) -> None:
        """Move item to archive storage."""
        item["consolidated"] = True
        item["consolidated_at"] = datetime.now().isoformat()
        
        # Organize by month for easy retrieval
        month_key = datetime.now().strftime("%Y-%m")
        archive_file = self.archive_dir / f"{month_key}.jsonl"
        
        with open(archive_file, 'a') as f:
            f.write(json.dumps(item) + "\n")
    
    def search_archive(self, query: str, months: int = 3) -> List[Dict]:
        """
        Search archived memories.
        
        Args:
            query: Search string
            months: How many recent months to search
        """
        results = []
        query_lower = query.lower()
        
        now = datetime.now()
        for i in range(months):
            month = (now - timedelta(days=30*i)).strftime("%Y-%m")
            archive_file = self.archive_dir / f"{month}.jsonl"
            
            if not archive_file.exists():
                continue
            
            with open(archive_file, 'r') as f:
                for line in f:
                    try:
                        item = json.loads(line.strip())
                        if (query_lower in item["content"].lower() or
                            any(query_lower in tag.lower() for tag in item["tags"])):
                            results.append(item)
                    except json.JSONDecodeError:
                        continue
        
        # Sort by priority
        results.sort(key=lambda x: -x.get("priority", 0))
        
        return results[:20]  # Limit results
    
    def get_insights(self) -> List[str]:
        """
        Extract insights from working memory.
        Called during 'sleep' cycles.
        """
        insights = []
        
        # High-priority items are insights
        for item in self.working:
            if item["priority"] >= 7 and not item.get("insight_extracted"):
                insights.append(item["content"])
                item["insight_extracted"] = True
        
        self._save_working()
        return insights
    
    def stats(self) -> Dict:
        """Return memory system statistics."""
        working_count = len(self.working)
        
        # Count archive entries
        archive_count = 0
        for archive_file in self.archive_dir.glob("*.jsonl"):
            with open(archive_file, 'r') as f:
                archive_count += sum(1 for _ in f)
        
        return {
            "working_memory_items": working_count,
            "archive_entries": archive_count,
            "working_capacity": self.max_working_items,
            "working_utilization": working_count / self.max_working_items
        }


def run_consolidation_cycle():
    """
    Run a full consolidation cycle.
    Called by cron during 'sleep' periods.
    """
    memory = EveMemoryLoop()
    
    print(f"[{datetime.now().isoformat()}] Starting consolidation cycle")
    
    # Get pre-stats
    pre_stats = memory.stats()
    print(f"  Working: {pre_stats['working_memory_items']} items")
    
    # Extract insights before consolidation
    insights = memory.get_insights()
    if insights:
        print(f"  Extracted {len(insights)} insights")
        # Save insights to special file
        insights_file = Path("/root/evolution/memory/insights.jsonl")
        with open(insights_file, 'a') as f:
            for insight in insights:
                f.write(json.dumps({
                    "insight": insight,
                    "extracted_at": datetime.now().isoformat()
                }) + "\n")
    
    # Consolidate
    result = memory.consolidate()
    print(f"  Consolidated: {result['archived']} archived, {result['discarded']} discarded, {result['kept']} kept")
    
    # Get post-stats
    post_stats = memory.stats()
    print(f"  Final working: {post_stats['working_memory_items']} items")
    
    return result


if __name__ == "__main__":
    # Test the memory loop
    memory = EveMemoryLoop()
    
    print("=== Testing EveMemoryLoop ===")
    
    # Add some test memories
    memory.add(
        "Gemma 4 E2B runs in 8GB VRAM, perfect for RTX 3060",
        source="research",
        priority=9,
        tags=["models", "gemma4", "hardware"]
    )
    
    memory.add(
        "mini-SWE-agent achieves 74% with only 100 lines",
        source="research", 
        priority=8,
        tags=["agents", "swe-agent", "simplicity"]
    )
    
    memory.add(
        "Need to buy milk",
        source="random",
        priority=2,
        tags=["personal"]
    )
    
    print(f"\nWorking memory: {memory.stats()}")
    
    # Search
    print("\n=== Search for 'gemma' ===")
    results = memory.search_working("gemma")
    for r in results:
        print(f"  [{r['priority']}] {r['content'][:60]}...")
    
    # Consolidate
    print("\n=== Consolidation ===")
    result = memory.consolidate()
    print(f"  Archived: {result['archived']}, Discarded: {result['discarded']}, Kept: {result['kept']}")
    
    print(f"\nFinal stats: {memory.stats()}")
