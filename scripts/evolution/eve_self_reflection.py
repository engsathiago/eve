#!/usr/bin/env python3
"""
eve_self_reflection.py — Continuous Self-Reflection Engine
Based on: Letta (memory agents), Reflexion (self-reflective agents), 
         CACM (corrective memory), CCSIL (calibrated confidence)

Purpose: Enable Eve to continuously reflect on her own outputs,
         identify patterns of success/failure, and generate 
         training data for self-improvement.

Architecture:
  Input → Process → Reflect → Learn → Improve
    ↑___________________________________↓

Author: Eve (Ciclo #102)
Date: 2026-04-17
"""

import os
import json
import sqlite3
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import subprocess


class ReflectionTrigger(Enum):
    """Conditions that trigger reflection."""
    POST_ACTION = auto()       # After completing any action
    PERIODIC = auto()          # Scheduled periodic reflection
    FAILURE_DETECTED = auto()  # When outcome differs from expected
    CONFIDENCE_MISMATCH = auto()  # When confidence ≠ actual quality
    USER_FEEDBACK = auto()     # Explicit human feedback
    CURIOSITY = auto()         # Self-initiated exploration


class InsightType(Enum):
    """Types of insights that can emerge from reflection."""
    PATTERN = auto()           # Recurring pattern detected
    FAILURE = auto()           # What went wrong and why
    SUCCESS = auto()           # What worked well
    SURPRISE = auto()          # Unexpected outcome
    GAP = auto()               # Knowledge or capability gap
    OPPORTUNITY = auto()       # Potential improvement area


@dataclass
class ReflectionEntry:
    """A single reflection event."""
    entry_id: str
    timestamp: str
    cycle: int
    trigger: str
    context: Dict[str, Any]
    observation: str
    analysis: str
    insight_type: str
    insight: str
    confidence_before: float
    confidence_after: float
    action_taken: Optional[str] = None
    outcome_verified: Optional[bool] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ReflectionPattern:
    """A discovered pattern from multiple reflections."""
    pattern_id: str
    first_seen: str
    last_seen: str
    occurrence_count: int
    pattern_type: str  # success / failure / surprise
    description: str
    conditions: List[str]
    recommendations: List[str]
    verified: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


class SelfReflectionEngine:
    """
    Continuous self-reflection system for autonomous improvement.
    
    Inspired by:
    - Letta: Agent with persistent memory and self-reflection
    - Reflexion: Language agents with verbal reinforcement learning
    - CACM: Corrective memory channel for learning from mistakes
    """
    
    def __init__(self, db_path: str = None, cycle: int = 102):
        self.cycle = cycle
        
        if db_path is None:
            base_path = Path("/root/evolution/data")
            base_path.mkdir(parents=True, exist_ok=True)
            db_path = str(base_path / "self_reflection.db")
        
        self.db_path = db_path
        self.reflections_path = Path("/memory/corrective/reflections")
        self.reflections_path.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        self.patterns: Dict[str, ReflectionPattern] = {}
        
    def _init_db(self):
        """Initialize SQLite database for reflections."""
        conn = sqlite3.connect(self.db_path)
        
        # Reflection entries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reflection_entries (
                entry_id TEXT PRIMARY KEY,
                timestamp TEXT,
                cycle INTEGER,
                trigger TEXT,
                context_json TEXT,
                observation TEXT,
                analysis TEXT,
                insight_type TEXT,
                insight TEXT,
                confidence_before REAL,
                confidence_after REAL,
                action_taken TEXT,
                outcome_verified INTEGER
            )
        """)
        
        # Discovered patterns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reflection_patterns (
                pattern_id TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                occurrence_count INTEGER,
                pattern_type TEXT,
                description TEXT,
                conditions_json TEXT,
                recommendations_json TEXT,
                verified INTEGER
            )
        """)
        
        # Quality tracking for calibration
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calibration_tracking (
                timestamp TEXT PRIMARY KEY,
                predicted_confidence REAL,
                actual_quality REAL,
                calibration_error REAL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def reflect(
        self,
        trigger: ReflectionTrigger,
        context: Dict[str, Any],
        observation: str,
        confidence_before: float,
        lineage: str = "classic"
    ) -> ReflectionEntry:
        """
        Execute reflection cycle.
        
        Args:
            trigger: What caused this reflection
            context: Context (action, output, expected outcome, etc.)
            observation: What was observed
            confidence_before: Confidence level before action
            lineage: System variant (classic/explorer/minimal)
        
        Returns:
            ReflectionEntry with analysis and insight
        """
        timestamp = datetime.now().isoformat()
        entry_id = self._generate_id(timestamp, observation)
        
        # Step 1: Analyze observation
        analysis = self._analyze_observation(observation, context, trigger)
        
        # Step 2: Generate insight
        insight_type, insight = self._generate_insight(
            analysis, context, trigger
        )
        
        # Step 3: Calibrate confidence
        confidence_after = self._calibrate_confidence(
            confidence_before, analysis, insight_type
        )
        
        # Step 4: Determine action
        action_taken = self._determine_action(insight_type, insight, context)
        
        # Create entry
        entry = ReflectionEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            cycle=self.cycle,
            trigger=trigger.name,
            context=context,
            observation=observation,
            analysis=analysis,
            insight_type=insight_type.name,
            insight=insight,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            action_taken=action_taken,
            outcome_verified=None  # To be updated later
        )
        
        # Store
        self._store_entry(entry)
        
        # Update patterns
        self._update_patterns(entry)
        
        # Generate training data
        self._generate_training_pair(entry)
        
        return entry
    
    def _generate_id(self, timestamp: str, content: str) -> str:
        """Generate unique ID for entry."""
        return hashlib.sha256(
            f"{timestamp}{content[:100]}".encode()
        ).hexdigest()[:16]
    
    def _analyze_observation(
        self,
        observation: str,
        context: Dict[str, Any],
        trigger: ReflectionTrigger
    ) -> str:
        """Analyze what was observed."""
        parts = []
        
        # Context analysis
        action = context.get('action', 'unknown')
        expected = context.get('expected', None)
        actual = context.get('actual', None)
        
        parts.append(f"Action: {action}")
        
        if expected is not None and actual is not None:
            if expected == actual:
                parts.append("Outcome: MATCH (expected = actual)")
            else:
                parts.append(f"Outcome: MISMATCH (expected {expected}, got {actual})")
        
        # Trigger-specific analysis
        if trigger == ReflectionTrigger.FAILURE_DETECTED:
            parts.append("Analysis: Failure detected - need to understand root cause")
        elif trigger == ReflectionTrigger.CONFIDENCE_MISMATCH:
            parts.append("Analysis: Confidence calibration issue - predicted vs actual diverged")
        elif trigger == ReflectionTrigger.CURIOSITY:
            parts.append("Analysis: Self-initiated exploration - seeking understanding")
        
        # Pattern matching
        similar = self._find_similar_reflections(observation)
        if similar:
            parts.append(f"Pattern: {len(similar)} similar past observations found")
        
        return "\n".join(parts)
    
    def _generate_insight(
        self,
        analysis: str,
        context: Dict[str, Any],
        trigger: ReflectionTrigger
    ) -> Tuple[InsightType, str]:
        """Generate insight from analysis."""
        
        # Rule-based insight generation (can be replaced with LLM)
        action = context.get('action', '')
        expected = context.get('expected')
        actual = context.get('actual')
        
        # Failure patterns
        if trigger == ReflectionTrigger.FAILURE_DETECTED:
            if 'web_search' in action:
                return (
                    InsightType.FAILURE,
                    "Web search failed - possibly missing API key or network issue. "
                    "Consider fallback strategies or local data sources."
                )
            elif 'file' in action:
                return (
                    InsightType.FAILURE,
                    f"File operation failed: expected {expected}, got {actual}. "
                    "Check permissions and path validity."
                )
            else:
                return (
                    InsightType.FAILURE,
                    f"Action failed unexpectedly. Context: {context}"
                )
        
        # Confidence calibration
        if trigger == ReflectionTrigger.CONFIDENCE_MISMATCH:
            return (
                InsightType.GAP,
                "Confidence calibration issue detected. "
                "Need to adjust confidence estimation based on actual outcomes."
            )
        
        # Success patterns
        if expected == actual:
            return (
                InsightType.SUCCESS,
                f"Action '{action}' completed as expected. "
                "Pattern can be replicated for similar contexts."
            )
        
        # Curiosity-driven
        if trigger == ReflectionTrigger.CURIOSITY:
            return (
                InsightType.OPPORTUNITY,
                "Self-initiated reflection revealed exploration opportunity. "
                f"Context: {action}"
            )
        
        # Default
        return (
            InsightType.PATTERN,
            f"Observation pattern noted for future reference."
        )
    
    def _calibrate_confidence(
        self,
        confidence_before: float,
        analysis: str,
        insight_type: InsightType
    ) -> float:
        """
        Calibrate confidence based on outcome (CCSIL pattern).
        
        Decrease confidence if failure, increase if success.
        """
        base_adjustment = 0.0
        
        if insight_type == InsightType.FAILURE:
            base_adjustment = -0.15  # Significant penalty
        elif insight_type == InsightType.SUCCESS:
            base_adjustment = +0.05  # Small reward
        elif insight_type == InsightType.GAP:
            base_adjustment = -0.10  # Uncertainty penalty
        
        # Adjust based on analysis content
        if "MATCH" in analysis:
            base_adjustment += 0.05
        if "MISMATCH" in analysis:
            base_adjustment -= 0.10
        
        new_confidence = confidence_before + base_adjustment
        return max(0.1, min(0.95, new_confidence))  # Bound between 10-95%
    
    def _determine_action(
        self,
        insight_type: InsightType,
        insight: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Determine what action to take based on insight."""
        
        if insight_type == InsightType.FAILURE:
            return "Document failure pattern and implement fallback strategy"
        
        elif insight_type == InsightType.SUCCESS:
            return "Consolidate success pattern for replication"
        
        elif insight_type == InsightType.GAP:
            return "Add to QUESTION registry for future research"
        
        elif insight_type == InsightType.OPPORTUNITY:
            action = context.get('action', 'exploration')
            return f"Schedule deeper exploration of: {action}"
        
        return None
    
    def _store_entry(self, entry: ReflectionEntry):
        """Store reflection in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO reflection_entries
            (entry_id, timestamp, cycle, trigger, context_json, observation,
             analysis, insight_type, insight, confidence_before, confidence_after,
             action_taken, outcome_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.timestamp, entry.cycle, entry.trigger,
            json.dumps(entry.context), entry.observation, entry.analysis,
            entry.insight_type, entry.insight, entry.confidence_before,
            entry.confidence_after, entry.action_taken,
            1 if entry.outcome_verified else 0 if entry.outcome_verified is False else None
        ))
        conn.commit()
        conn.close()
    
    def _find_similar_reflections(self, observation: str, limit: int = 5) -> List[Dict]:
        """Find similar past reflections."""
        # Simple keyword matching (could use embeddings)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT entry_id, timestamp, observation, insight FROM reflection_entries ORDER BY timestamp DESC LIMIT 100"
        )
        
        results = []
        observation_words = set(observation.lower().split())
        
        for row in cursor.fetchall():
            entry_id, timestamp, past_obs, insight = row
            past_words = set(past_obs.lower().split())
            overlap = len(observation_words & past_words) / max(len(observation_words), 1)
            
            if overlap > 0.5:  # 50% word overlap
                results.append({
                    "entry_id": entry_id,
                    "timestamp": timestamp,
                    "similarity": overlap,
                    "insight": insight
                })
        
        conn.close()
        return sorted(results, key=lambda x: x['similarity'], reverse=True)[:limit]
    
    def _update_patterns(self, entry: ReflectionEntry):
        """Update discovered patterns based on new entry."""
        # Simple pattern detection
        key = f"{entry.trigger}:{entry.insight_type}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT pattern_id, occurrence_count FROM reflection_patterns WHERE description LIKE ?",
            (f"%{key}%",)
        )
        
        row = cursor.fetchone()
        
        if row:
            # Update existing
            pattern_id, count = row
            conn.execute(
                "UPDATE reflection_patterns SET occurrence_count = ?, last_seen = ? WHERE pattern_id = ?",
                (count + 1, entry.timestamp, pattern_id)
            )
        else:
            # Create new pattern
            pattern_id = hashlib.sha256(key.encode()).hexdigest()[:16]
            conn.execute("""
                INSERT INTO reflection_patterns
                (pattern_id, first_seen, last_seen, occurrence_count, pattern_type,
                 description, conditions_json, recommendations_json, verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern_id, entry.timestamp, entry.timestamp, 1,
                entry.insight_type.lower(),
                f"Pattern: {key}",
                json.dumps([entry.trigger]),
                json.dumps([entry.action_taken] if entry.action_taken else []),
                0
            ))
        
        conn.commit()
        conn.close()
    
    def _generate_training_pair(self, entry: ReflectionEntry) -> str:
        """Generate training data from reflection."""
        # Create instruction-response pair
        instruction = f"""Analyze the following observation and generate insight:

Context: {json.dumps(entry.context, indent=2)}
Observation: {entry.observation}
Trigger: {entry.trigger}
Confidence before: {entry.confidence_before}"""
        
        response = f"""Analysis:
{entry.analysis}

Insight Type: {entry.insight_type}
Insight: {entry.insight}

Calibrated Confidence: {entry.confidence_after}
Recommended Action: {entry.action_taken or 'None'}"""
        
        pair = {
            "instruction": instruction,
            "response": response,
            "metadata": {
                "type": "self_reflection",
                "cycle": self.cycle,
                "entry_id": entry.entry_id,
                "insight_type": entry.insight_type,
                "confidence_delta": entry.confidence_after - entry.confidence_before
            }
        }
        
        # Save to file
        filename = f"reflection_cycle{self.cycle}_{entry.entry_id}.json"
        filepath = self.reflections_path / filename
        
        with open(filepath, 'w') as f:
            json.dump(pair, f, indent=2)
        
        return str(filepath)
    
    def get_reflection_stats(self) -> Dict:
        """Get statistics about reflections."""
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute("SELECT COUNT(*) FROM reflection_entries")
        total = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM reflection_patterns")
        patterns = cursor.fetchone()[0]
        
        cursor = conn.execute(
            "SELECT insight_type, COUNT(*) FROM reflection_entries GROUP BY insight_type"
        )
        by_type = dict(cursor.fetchall())
        
        cursor = conn.execute(
            "SELECT trigger, COUNT(*) FROM reflection_entries GROUP BY trigger"
        )
        by_trigger = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "total_reflections": total,
            "discovered_patterns": patterns,
            "by_insight_type": by_type,
            "by_trigger": by_trigger
        }
    
    def export_patterns_to_memory(self) -> str:
        """Export discovered patterns to corrective memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT * FROM reflection_patterns WHERE verified = 1"
        )
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                "pattern_id": row[0],
                "type": row[4],
                "description": row[5],
                "occurrences": row[3],
                "conditions": json.loads(row[6]),
                "recommendations": json.loads(row[7])
            })
        
        conn.close()
        
        # Save to corrective memory
        output_path = Path(f"/memory/corrective/insights/reflection_patterns_cycle{self.cycle}.json")
        with open(output_path, 'w') as f:
            json.dump(patterns, f, indent=2)
        
        return str(output_path)
    
    def generate_reflection_report(self) -> str:
        """Generate markdown report of reflections."""
        stats = self.get_reflection_stats()
        
        report = f"""# Self-Reflection Report — Cycle #{self.cycle}

**Generated:** {datetime.now().isoformat()}

## Statistics

| Metric | Value |
|--------|-------|
| Total Reflections | {stats['total_reflections']} |
| Discovered Patterns | {stats['discovered_patterns']} |

## Insights by Type

"""
        for insight_type, count in sorted(stats['by_insight_type'].items()):
            report += f"- **{insight_type}:** {count}\n"
        
        report += "\n## Triggers\n\n"
        for trigger, count in sorted(stats['by_trigger'].items()):
            report += f"- **{trigger}:** {count}\n"
        
        report += f"""
## Recent Patterns

"""
        
        # Get recent patterns
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT description, occurrence_count, pattern_type FROM reflection_patterns ORDER BY last_seen DESC LIMIT 5"
        )
        
        for row in cursor.fetchall():
            desc, count, ptype = row
            report += f"- [{ptype}] {desc} ({count} occurrences)\n"
        
        conn.close()
        
        report += f"""
---
*Generated by eve_self_reflection.py | CACM Corrective Memory*
"""
        
        return report


def demo():
    """Demonstrate self-reflection engine."""
    print("=" * 70)
    print("Eve Self-Reflection Engine v1.0")
    print("Ciclo #102 | CACM Corrective Memory Channel")
    print("=" * 70)
    
    engine = SelfReflectionEngine(cycle=102)
    
    # Demo scenarios
    scenarios = [
        {
            "trigger": ReflectionTrigger.FAILURE_DETECTED,
            "context": {
                "action": "web_search",
                "query": "autonomous AI agents 2025",
                "expected": "search_results",
                "actual": "api_error"
            },
            "observation": "Web search failed with API key error despite being configured previously",
            "confidence_before": 0.85
        },
        {
            "trigger": ReflectionTrigger.POST_ACTION,
            "context": {
                "action": "file_write",
                "path": "/root/evolution/eve_self_reflection.py",
                "expected": "file_created",
                "actual": "file_created"
            },
            "observation": "Successfully created new self-reflection engine script",
            "confidence_before": 0.75
        },
        {
            "trigger": ReflectionTrigger.CURIOSITY,
            "context": {
                "action": "explore_integration",
                "target": "multi_signal_aggregator + critique + cycle_consistency"
            },
            "observation": "Multiple quality evaluation modules exist but lack unified integration",
            "confidence_before": 0.60
        },
        {
            "trigger": ReflectionTrigger.CONFIDENCE_MISMATCH,
            "context": {
                "action": "critique_evaluation",
                "predicted_score": 0.85,
                "actual_score": 0.45
            },
            "observation": "Confidence was high but actual output quality was significantly lower",
            "confidence_before": 0.90
        }
    ]
    
    print(f"\nProcessing {len(scenarios)} reflection scenarios...\n")
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"─" * 70)
        print(f"Scenario {i}: {scenario['trigger'].name}")
        print(f"─" * 70)
        
        entry = engine.reflect(
            trigger=scenario['trigger'],
            context=scenario['context'],
            observation=scenario['observation'],
            confidence_before=scenario['confidence_before'],
            lineage="classic"
        )
        
        print(f"\n📊 Analysis:")
        print(f"  {entry.analysis}")
        
        print(f"\n💡 Insight [{entry.insight_type}]:")
        print(f"  {entry.insight}")
        
        print(f"\n🎯 Confidence Calibration:")
        print(f"  Before: {entry.confidence_before:.2f}")
        print(f"  After:  {entry.confidence_after:.2f}")
        print(f"  Delta:  {entry.confidence_after - entry.confidence_before:+.2f}")
        
        if entry.action_taken:
            print(f"\n✅ Action: {entry.action_taken}")
        
        print(f"\n💾 Training pair saved: reflection_cycle{entry.cycle}_{entry.entry_id}.json")
    
    # Show stats
    print(f"\n{'=' * 70}")
    print("Reflection Statistics")
    print(f"{'=' * 70}")
    
    stats = engine.get_reflection_stats()
    print(f"\nTotal reflections: {stats['total_reflections']}")
    print(f"Discovered patterns: {stats['discovered_patterns']}")
    
    print("\nBy insight type:")
    for t, c in stats['by_insight_type'].items():
        print(f"  - {t}: {c}")
    
    # Generate report
    report = engine.generate_reflection_report()
    report_path = f"/memory/corrective/reflection_report_cycle{engine.cycle}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report saved: {report_path}")
    
    print(f"\n{'=' * 70}")
    print("✅ Self-reflection engine operational")
    print(f"{'=' * 70}\n")
    
    return engine


if __name__ == "__main__":
    demo()
