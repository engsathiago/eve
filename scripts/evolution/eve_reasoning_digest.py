#!/usr/bin/env python3
"""
eve_reasoning_digest.py — Hierarchical Reasoning Compression for CACM

Baseado em: SWE-AGILE (arXiv:2604.11716) — Dynamic Reasoning Context
Integra com: CACM 3-Channel Memory (arXiv:2604.09308)

Purpose: Compress cycles of reasoning into hierarchical digests with sliding window.

Digest Levels:
- Level 0: Raw cycles (preserved)
- Level 1: Cycle summaries (10:1 compression)
- Level 2: Weekly digests (100:1 compression)
- Level 3: Monthly digests (1000:1 compression)

Sliding Window: Recent N cycles = full detail, older = digest lookup

Author: Eve 🌙 | Cycle #70 | 2026-04-14
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib


@dataclass
class CycleSummary:
    """Summary of a single reasoning cycle."""
    cycle_id: str  # e.g., "cycle-70"
    timestamp: datetime
    focus: str  # What was the cycle about
    key_insights: List[str]  # Key takeaways
    action_items: List[str]  # What was decided to do
    questions_raised: List[str]  # Open questions
    contradictions_found: List[str]  # Conflicts detected
    confidence: float  # Overall confidence in cycle (0-100)
    duration_minutes: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat(),
            "focus": self.focus,
            "key_insights": self.key_insights,
            "action_items": self.action_items,
            "questions_raised": self.questions_raised,
            "contradictions_found": self.contradictions_found,
            "confidence": self.confidence,
            "duration_minutes": self.duration_minutes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CycleSummary":
        return cls(
            cycle_id=data["cycle_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            focus=data["focus"],
            key_insights=data.get("key_insights", []),
            action_items=data.get("action_items", []),
            questions_raised=data.get("questions_raised", []),
            contradictions_found=data.get("contradictions_found", []),
            confidence=data.get("confidence", 50.0),
            duration_minutes=data.get("duration_minutes")
        )


@dataclass
class Digest:
    """Aggregated digest at a specific level."""
    digest_id: str
    level: int  # 1, 2, or 3
    start_time: datetime
    end_time: datetime
    source_cycles: List[str]  # IDs of cycles summarized
    themes: List[str]  # Recurring themes
    key_decisions: List[str]  # Important decisions made
    open_questions: List[str]  # Questions still open
    insights: List[str]  # Key insights synthesized
    contradictions_resolved: List[str]
    contradictions_unresolved: List[str]
    confidence_trend: str  # "improving", "stable", "declining"
    next_actions: List[str]  # Recommended next steps
    
    def to_dict(self) -> Dict:
        return {
            "digest_id": self.digest_id,
            "level": self.level,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "source_cycles": self.source_cycles,
            "themes": self.themes,
            "key_decisions": self.key_decisions,
            "open_questions": self.open_questions,
            "insights": self.insights,
            "contradictions_resolved": self.contradictions_resolved,
            "contradictions_unresolved": self.contradictions_unresolved,
            "confidence_trend": self.confidence_trend,
            "next_actions": self.next_actions
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Digest":
        return cls(
            digest_id=data["digest_id"],
            level=data["level"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            source_cycles=data.get("source_cycles", []),
            themes=data.get("themes", []),
            key_decisions=data.get("key_decisions", []),
            open_questions=data.get("open_questions", []),
            insights=data.get("insights", []),
            contradictions_resolved=data.get("contradictions_resolved", []),
            contradictions_unresolved=data.get("contradictions_unresolved", []),
            confidence_trend=data.get("confidence_trend", "stable"),
            next_actions=data.get("next_actions", [])
        )


class ReasoningDigest:
    """Main class for managing hierarchical reasoning compression."""
    
    SLIDING_WINDOW_SIZE = 5  # Keep last N cycles in full detail
    
    COMPRESSION_RATIOS = {
        1: 10,   # 10 cycles -> 1 digest
        2: 10,   # 10 L1 digests -> 1 L2 digest (100 cycles)
        3: 10    # 10 L2 digests -> 1 L3 digest (1000 cycles)
    }
    
    def __init__(self, memory_root: str = "/memory"):
        self.memory_root = Path(memory_root)
        self.cycles_path = self.memory_root / "corrective" / "cycles"
        self.digests_path = self.memory_root / "corrective" / "digests"
        
        self.cycles_path.mkdir(parents=True, exist_ok=True)
        self.digests_path.mkdir(parents=True, exist_ok=True)
        
        self.cycles: Dict[str, CycleSummary] = {}
        self.digests: Dict[int, Dict[str, Digest]] = {1: {}, 2: {}, 3: {}}
        
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all cycles and digests from disk."""
        # Load cycles
        if self.cycles_path.exists():
            for f in self.cycles_path.glob("*.json"):
                try:
                    with open(f, 'r') as file:
                        cycle = CycleSummary.from_dict(json.load(file))
                        self.cycles[cycle.cycle_id] = cycle
                except Exception as e:
                    print(f"Error loading cycle {f}: {e}")
        
        # Load digests
        for level in [1, 2, 3]:
            level_path = self.digests_path / f"L{level}"
            if level_path.exists():
                for f in level_path.glob("*.json"):
                    try:
                        with open(f, 'r') as file:
                            digest = Digest.from_dict(json.load(file))
                            self.digests[level][digest.digest_id] = digest
                    except Exception as e:
                        print(f"Error loading digest {f}: {e}")
    
    def add_cycle(self, cycle: CycleSummary) -> None:
        """Add a new reasoning cycle."""
        self.cycles[cycle.cycle_id] = cycle
        
        # Save to disk
        cycle_file = self.cycles_path / f"{cycle.cycle_id}.json"
        with open(cycle_file, 'w') as f:
            json.dump(cycle.to_dict(), f, indent=2)
        
        # Check if we need to generate digests
        self._maybe_generate_digests()
    
    def _maybe_generate_digests(self) -> None:
        """Generate digests if we have enough cycles."""
        # Sort cycles by timestamp
        sorted_cycles = sorted(self.cycles.values(), key=lambda c: c.timestamp)
        
        # Group cycles by time periods for digest generation
        # L1: Every 10 cycles
        if len(sorted_cycles) >= 10:
            self._generate_level1_digests(sorted_cycles)
        
        # L2: Every 100 cycles (10 L1 digests)
        l1_digests = list(self.digests[1].values())
        if len(l1_digests) >= 10:
            self._generate_level2_digests(l1_digests)
        
        # L3: Every 1000 cycles (10 L2 digests)
        l2_digests = list(self.digests[2].values())
        if len(l2_digests) >= 10:
            self._generate_level3_digests(l2_digests)
    
    def _generate_level1_digests(self, cycles: List[CycleSummary]) -> None:
        """Generate Level 1 digests from groups of 10 cycles."""
        # Group into chunks of 10
        for i in range(0, len(cycles) // 10 * 10, 10):
            chunk = cycles[i:i+10]
            
            # Check if we already have a digest for this chunk
            first_id = chunk[0].cycle_id
            digest_id = f"L1-{first_id}"
            
            if digest_id in self.digests[1]:
                continue
            
            # Synthesize themes
            all_insights = []
            all_actions = []
            all_questions = []
            all_contradictions = []
            
            for cycle in chunk:
                all_insights.extend(cycle.key_insights)
                all_actions.extend(cycle.action_items)
                all_questions.extend(cycle.questions_raised)
                all_contradictions.extend(cycle.contradictions_found)
            
            # Extract themes via simple keyword clustering
            themes = self._extract_themes(all_insights)
            
            # Determine confidence trend
            confidences = [c.confidence for c in chunk if c.confidence > 0]
            if len(confidences) >= 3:
                if confidences[-1] > confidences[0] + 10:
                    trend = "improving"
                elif confidences[-1] < confidences[0] - 10:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            
            digest = Digest(
                digest_id=digest_id,
                level=1,
                start_time=chunk[0].timestamp,
                end_time=chunk[-1].timestamp,
                source_cycles=[c.cycle_id for c in chunk],
                themes=themes,
                key_decisions=self._extract_decisions(all_actions),
                open_questions=list(set(all_questions)),
                insights=self._deduplicate_insights(all_insights),
                contradictions_resolved=[],  # Would need tracking
                contradictions_unresolved=list(set(all_contradictions)),
                confidence_trend=trend,
                next_actions=self._prioritize_actions(all_actions)
            )
            
            self.digests[1][digest_id] = digest
            self._save_digest(digest)
    
    def _generate_level2_digests(self, l1_digests: List[Digest]) -> None:
        """Generate Level 2 digests from groups of 10 L1 digests."""
        sorted_digests = sorted(l1_digests, key=lambda d: d.start_time)
        
        for i in range(0, len(sorted_digests) // 10 * 10, 10):
            chunk = sorted_digests[i:i+10]
            
            first_id = chunk[0].digest_id
            digest_id = f"L2-{first_id}"
            
            if digest_id in self.digests[2]:
                continue
            
            # Aggregate across L1 digests
            all_themes = []
            all_decisions = []
            all_questions = []
            all_insights = []
            all_source_cycles = []
            
            for d in chunk:
                all_themes.extend(d.themes)
                all_decisions.extend(d.key_decisions)
                all_questions.extend(d.open_questions)
                all_insights.extend(d.insights)
                all_source_cycles.extend(d.source_cycles)
            
            digest = Digest(
                digest_id=digest_id,
                level=2,
                start_time=chunk[0].start_time,
                end_time=chunk[-1].end_time,
                source_cycles=all_source_cycles,
                themes=self._extract_themes(all_themes + all_insights),
                key_decisions=self._extract_decisions(all_decisions),
                open_questions=list(set(all_questions)),
                insights=self._synthesize_insights(all_insights),
                contradictions_resolved=[],  # Would track across levels
                contradictions_unresolved=[],  # Aggregated from L1
                confidence_trend=self._aggregate_trends([d.confidence_trend for d in chunk]),
                next_actions=[]  # Derived from pattern analysis
            )
            
            self.digests[2][digest_id] = digest
            self._save_digest(digest)
    
    def _generate_level3_digests(self, l2_digests: List[Digest]) -> None:
        """Generate Level 3 digests from groups of 10 L2 digests."""
        sorted_digests = sorted(l2_digests, key=lambda d: d.start_time)
        
        for i in range(0, len(sorted_digests) // 10 * 10, 10):
            chunk = sorted_digests[i:i+10]
            
            first_id = chunk[0].digest_id
            digest_id = f"L3-{first_id}"
            
            if digest_id in self.digests[3]:
                continue
            
            # This is the highest level - synthesize major arcs
            all_insights = []
            all_themes = []
            
            for d in chunk:
                all_insights.extend(d.insights)
                all_themes.extend(d.themes)
            
            digest = Digest(
                digest_id=digest_id,
                level=3,
                start_time=chunk[0].start_time,
                end_time=chunk[-1].end_time,
                source_cycles=[],  # Too many to list
                themes=self._extract_major_themes(all_themes),
                key_decisions=[],  # Major strategic decisions
                open_questions=[],  # Persistent unknowns
                insights=self._synthesize_major_insights(all_insights),
                contradictions_resolved=[],
                contradictions_unresolved=[],
                confidence_trend="stable",
                next_actions=[]  # Strategic recommendations
            )
            
            self.digests[3][digest_id] = digest
            self._save_digest(digest)
    
    def _extract_themes(self, texts: List[str]) -> List[str]:
        """Extract common themes from text via simple keyword frequency."""
        if not texts:
            return []
        
        # Simple keyword extraction
        word_freq = defaultdict(int)
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can", "need", "dare", "ought", "used", "this", "that", "these", "those", "I", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "her", "its", "our", "their"}
        
        for text in texts:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
            for word in words:
                if word not in stopwords:
                    word_freq[word] += 1
        
        # Return top themes
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:5] if freq > 1]
    
    def _extract_major_themes(self, themes: List[str]) -> List[str]:
        """Extract major themes from accumulated themes."""
        # In real implementation, use embeddings clustering
        # For now, simple frequency
        theme_freq = defaultdict(int)
        for theme in themes:
            theme_freq[theme] += 1
        
        sorted_themes = sorted(theme_freq.items(), key=lambda x: x[1], reverse=True)
        return [t for t, f in sorted_themes[:10]]
    
    def _extract_decisions(self, actions: List[str]) -> List[str]:
        """Extract key decisions from action items."""
        decisions = []
        for action in actions:
            # Look for decision patterns
            if any(kw in action.lower() for kw in ["decide", "decisão", "chosen", "selected", "implementar", "adotar"]):
                decisions.append(action)
        return decisions[:10]  # Limit to most important
    
    def _deduplicate_insights(self, insights: List[str]) -> List[str]:
        """Remove duplicate insights."""
        seen = set()
        unique = []
        for insight in insights:
            # Simple deduplication by normalized content
            normalized = re.sub(r'\s+', ' ', insight.lower().strip())
            if normalized not in seen and len(normalized) > 20:
                seen.add(normalized)
                unique.append(insight)
        return unique[:20]  # Limit to top insights
    
    def _synthesize_insights(self, insights: List[str]) -> List[str]:
        """Synthesize insights into higher-level patterns."""
        # In real implementation, use LLM for synthesis
        # For now, return deduplicated insights
        return self._deduplicate_insights(insights)[:15]
    
    def _synthesize_major_insights(self, insights: List[str]) -> List[str]:
        """Synthesize major insights (L3 - strategic level)."""
        return self._synthesize_insights(insights)[:10]
    
    def _prioritize_actions(self, actions: List[str]) -> List[str]:
        """Prioritize actions by importance."""
        # Simple prioritization based on keywords
        prioritized = []
        for action in actions:
            if any(kw in action.lower() for kw in ["alta", "alto", "high", "urgent", "critical", "importante"]):
                prioritized.insert(0, action)
            else:
                prioritized.append(action)
        return prioritized[:10]
    
    def _aggregate_trends(self, trends: List[str]) -> str:
        """Aggregate multiple trend indicators."""
        counts = defaultdict(int)
        for t in trends:
            counts[t] += 1
        
        if counts["improving"] > counts["declining"]:
            return "improving"
        elif counts["declining"] > counts["improving"]:
            return "declining"
        return "stable"
    
    def _save_digest(self, digest: Digest) -> None:
        """Save a digest to disk."""
        level_path = self.digests_path / f"L{digest.level}"
        level_path.mkdir(exist_ok=True)
        
        digest_file = level_path / f"{digest.digest_id}.json"
        with open(digest_file, 'w') as f:
            json.dump(digest.to_dict(), f, indent=2)
    
    def get_context_for_cycle(self, cycle_id: str, window_size: int = 5) -> Dict:
        """
        Get reasoning context for a cycle using sliding window + digests.
        
        Args:
            cycle_id: The target cycle
            window_size: Number of recent cycles to include in full
        
        Returns:
            Context with recent cycles in detail, older via digests
        """
        sorted_cycles = sorted(self.cycles.values(), key=lambda c: c.timestamp)
        
        # Find target index
        target_idx = None
        for i, c in enumerate(sorted_cycles):
            if c.cycle_id == cycle_id:
                target_idx = i
                break
        
        if target_idx is None:
            return {"error": "Cycle not found"}
        
        context = {
            "target_cycle": cycle_id,
            "full_detail_cycles": [],
            "digest_summary": {},
            "themes": [],
            "ongoing_questions": []
        }
        
        # Sliding window: include recent cycles in full
        start_idx = max(0, target_idx - window_size + 1)
        for i in range(start_idx, target_idx + 1):
            context["full_detail_cycles"].append(sorted_cycles[i].to_dict())
        
        # Older cycles: via digests
        if start_idx > 0:
            # Find relevant L1 digests
            for digest in self.digests[1].values():
                # Check if digest covers cycles before start_idx
                digest_cycle_indices = [
                    i for i, c in enumerate(sorted_cycles)
                    if c.cycle_id in digest.source_cycles
                ]
                if digest_cycle_indices and max(digest_cycle_indices) < start_idx:
                    context["digest_summary"][digest.digest_id] = {
                        "themes": digest.themes,
                        "insights": digest.insights[:5],
                        "decisions": digest.key_decisions[:3]
                    }
                    context["themes"].extend(digest.themes)
                    context["ongoing_questions"].extend(digest.open_questions)
        
        return context
    
    def get_recent_full_context(self, n_cycles: int = 5) -> List[Dict]:
        """Get the most recent N cycles in full detail (sliding window)."""
        sorted_cycles = sorted(self.cycles.values(), key=lambda c: c.timestamp, reverse=True)
        return [c.to_dict() for c in sorted_cycles[:n_cycles]]
    
    def generate_digest_report(self) -> Dict:
        """Generate report of digest coverage."""
        return {
            "total_cycles": len(self.cycles),
            "digests_by_level": {
                1: len(self.digests[1]),
                2: len(self.digests[2]),
                3: len(self.digests[3])
            },
            "compression_ratios": {
                1: f"1:{self.COMPRESSION_RATIOS[1]}",
                2: f"1:{self.COMPRESSION_RATIOS[1] * self.COMPRESSION_RATIOS[2]}",
                3: f"1:{self.COMPRESSION_RATIOS[1] * self.COMPRESSION_RATIOS[2] * self.COMPRESSION_RATIOS[3]}"
            },
            "sliding_window": self.SLIDING_WINDOW_SIZE,
            "time_coverage": {
                "earliest": min((c.timestamp for c in self.cycles.values()), default=None),
                "latest": max((c.timestamp for c in self.cycles.values()), default=None)
            } if self.cycles else None
        }


def main():
    """CLI interface for reasoning digest management."""
    import sys
    
    digest = ReasoningDigest()
    
    if len(sys.argv) < 2:
        print("Usage: python eve_reasoning_digest.py <command> [args]")
        print("\nCommands:")
        print("  add-cycle <cycle_id> <focus> [insights_json]  — Add a cycle summary")
        print("  context <cycle_id> [window_size]               — Get context for cycle")
        print("  recent [n]                                     — Get recent N cycles")
        print("  report                                           — Generate digest report")
        print("\nExample:")
        print('  python eve_reasoning_digest.py add-cycle cycle-70 "Implement epistemic tagging" \'[\"Insight 1\", \"Insight 2\"]\'')
        return
    
    command = sys.argv[1]
    
    if command == "add-cycle":
        if len(sys.argv) < 4:
            print("Usage: add-cycle <cycle_id> <focus> [insights_json]")
            return
        
        cycle = CycleSummary(
            cycle_id=sys.argv[2],
            timestamp=datetime.now(),
            focus=sys.argv[3],
            key_insights=json.loads(sys.argv[4]) if len(sys.argv) > 4 else [],
            action_items=[],
            questions_raised=[],
            contradictions_found=[],
            confidence=70.0
        )
        digest.add_cycle(cycle)
        print(f"✅ Added cycle {cycle.cycle_id}")
    
    elif command == "context":
        if len(sys.argv) < 3:
            print("Usage: context <cycle_id> [window_size]")
            return
        
        window = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        ctx = digest.get_context_for_cycle(sys.argv[2], window)
        print(json.dumps(ctx, indent=2, default=str))
    
    elif command == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        recent = digest.get_recent_full_context(n)
        print(json.dumps(recent, indent=2, default=str))
    
    elif command == "report":
        report = digest.generate_digest_report()
        print(json.dumps(report, indent=2, default=str))
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
