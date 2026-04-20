#!/usr/bin/env python3
"""
eve_multi_signal_aggregator.py
Multi-signal quality aggregation engine for Eve.

Combines critique, cycle-consistency, and consequential learning
into unified quality scores with calibrated confidence.

Based on: BEAM (bi-level optimization), CACM (3-channel memory),
         RationalRewards (multi-dimensional evaluation)
"""

import json
import sqlite3
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import os


class SignalSource(Enum):
    """Types of quality signals."""
    CRITIQUE = "critique"
    CYCLE_CONSISTENCY = "cycle_consistency"
    CONSEQUENTIAL = "consequential"


class Decision(Enum):
    """Quality-based decisions."""
    ACCEPT = "accept"
    REVIEW = "review"  # Human review suggested
    REVISE = "revise"  # Auto-revision recommended
    REJECT = "reject"


@dataclass
class Signal:
    """A quality signal from any source."""
    source: SignalSource
    value: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        assert 0.0 <= self.value <= 1.0, "Signal value must be in [0, 1]"
        assert 0.0 <= self.confidence <= 1.0, "Confidence must be in [0, 1]"


@dataclass
class TaskProfile:
    """Weight configuration for a task type."""
    name: str
    weights: Dict[SignalSource, float]
    description: str = ""
    
    def __post_init__(self):
        total = sum(self.weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights must sum to 1.0, got {total}"


# Pre-defined task profiles based on paper research and empirical testing
TASK_PROFILES = {
    "code": TaskProfile(
        name="code",
        weights={
            SignalSource.CRITIQUE: 0.40,
            SignalSource.CYCLE_CONSISTENCY: 0.20,
            SignalSource.CONSEQUENTIAL: 0.40
        },
        description="Code generation: results matter most"
    ),
    "research": TaskProfile(
        name="research",
        weights={
            SignalSource.CRITIQUE: 0.35,
            SignalSource.CYCLE_CONSISTENCY: 0.45,
            SignalSource.CONSEQUENTIAL: 0.20
        },
        description="Research tasks: reasoning quality is critical"
    ),
    "writing": TaskProfile(
        name="writing",
        weights={
            SignalSource.CRITIQUE: 0.50,
            SignalSource.CYCLE_CONSISTENCY: 0.30,
            SignalSource.CONSEQUENTIAL: 0.20
        },
        description="Writing tasks: output quality dominates"
    ),
    "agentic": TaskProfile(
        name="agentic",
        weights={
            SignalSource.CRITIQUE: 0.25,
            SignalSource.CYCLE_CONSISTENCY: 0.25,
            SignalSource.CONSEQUENTIAL: 0.50
        },
        description="Agent actions: real-world impact is king"
    ),
    "learning": TaskProfile(
        name="learning",
        weights={
            SignalSource.CRITIQUE: 0.30,
            SignalSource.CYCLE_CONSISTENCY: 0.40,
            SignalSource.CONSEQUENTIAL: 0.30
        },
        description="Learning tasks: balanced evaluation"
    )
}


@dataclass
class QualityDecision:
    """Final quality decision with full context."""
    decision: Decision
    quality_score: float
    confidence: float
    individual_signals: Dict[SignalSource, Signal]
    aggregated_score: float
    justification: str
    recommended_action: str
    timestamp: datetime


class ReliabilityTracker:
    """Tracks historical accuracy of each signal source."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_path = Path("/root/evolution/data")
            base_path.mkdir(parents=True, exist_ok=True)
            db_path = str(base_path / "signal_reliability.db")
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_accuracy (
                source TEXT PRIMARY KEY,
                total_predictions INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize default values
        for source in SignalSource:
            conn.execute("""
                INSERT OR IGNORE INTO signal_accuracy (source)
                VALUES (?)
            """, (source.value,))
        
        conn.commit()
        conn.close()
    
    def update_accuracy(self, source: SignalSource, was_correct: bool):
        """Update accuracy tracking for a signal source."""
        conn = sqlite3.connect(self.db_path)
        
        if was_correct:
            conn.execute("""
                UPDATE signal_accuracy
                SET correct_predictions = correct_predictions + 1,
                    total_predictions = total_predictions + 1,
                    last_updated = CURRENT_TIMESTAMP
                WHERE source = ?
            """, (source.value,))
        else:
            conn.execute("""
                UPDATE signal_accuracy
                SET total_predictions = total_predictions + 1,
                    last_updated = CURRENT_TIMESTAMP
                WHERE source = ?
            """, (source.value,))
        
        conn.commit()
        conn.close()
    
    def get_reliability(self, source: SignalSource, default: float = 0.8) -> float:
        """Get reliability score for a signal source."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT total_predictions, correct_predictions
            FROM signal_accuracy WHERE source = ?
        """, (source.value,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
            return default
        
        total, correct = row
        return correct / total
    
    def get_all_reliabilities(self) -> Dict[SignalSource, float]:
        """Get reliability scores for all sources."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT source, total_predictions, correct_predictions
            FROM signal_accuracy
        """)
        
        results = {}
        for row in cursor.fetchall():
            source_val, total, correct = row
            source = SignalSource(source_val)
            results[source] = correct / total if total > 0 else 0.8
        
        conn.close()
        return results


class MultiSignalAggregator:
    """
    Aggregates multiple quality signals into unified score.
    
    Combines:
    - Internal quality (critique)
    - Reasoning quality (cycle-consistency)
    - Outcome quality (consequential)
    
    Into calibrated quality decisions.
    """
    
    # Decision thresholds based on CCSIL calibration principles
    THRESHOLDS = {
        Decision.ACCEPT: 0.75,
        Decision.REVIEW: 0.50,
        Decision.REVISE: 0.30,
        Decision.REJECT: 0.0
    }
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_path = Path("/root/evolution/data")
            base_path.mkdir(parents=True, exist_ok=True)
            db_path = str(base_path / "multi_signal.db")
        self.db_path = db_path
        self.reliability = ReliabilityTracker()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_assessments (
                id TEXT PRIMARY KEY,
                task_type TEXT,
                quality_score REAL,
                confidence REAL,
                decision TEXT,
                signals_json TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def aggregate(
        self,
        signals: List[Signal],
        task_type: str = "learning",
        custom_weights: Optional[Dict[SignalSource, float]] = None
    ) -> QualityDecision:
        """
        Aggregate multiple signals into quality decision.
        
        Args:
            signals: List of quality signals
            task_type: Type of task (code, research, writing, agentic, learning)
            custom_weights: Optional custom weights (overrides task profile)
        
        Returns:
            QualityDecision with aggregated score and recommendation
        """
        if not signals:
            raise ValueError("At least one signal required")
        
        # Get weights
        if custom_weights:
            weights = custom_weights
        elif task_type in TASK_PROFILES:
            weights = TASK_PROFILES[task_type].weights
        else:
            weights = TASK_PROFILES["learning"].weights
        
        # Calculate reliability-weighted scores
        signal_map = {s.source: s for s in signals}
        weighted_scores = []
        total_confidence = 0.0
        
        for signal in signals:
            weight = weights.get(signal.source, 0.33)
            reliability = self.reliability.get_reliability(signal.source)
            
            # Weighted score: value × weight × reliability
            weighted_score = signal.value * weight * reliability
            weighted_scores.append(weighted_score)
            
            # Confidence contribution
            total_confidence += signal.confidence * weight
        
        # Aggregate score (sum of weighted scores, normalized by total weight)
        total_weight = sum(weights.get(s.source, 0.33) for s in signals)
        aggregated_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.5
        
        # Final quality score (bounded)
        quality_score = max(0.0, min(1.0, aggregated_score))
        
        # Confidence calibration
        confidence = min(1.0, total_confidence / total_weight) if total_weight > 0 else 0.5
        
        # Make decision
        decision = self._make_decision(quality_score)
        
        # Generate justification
        justification = self._generate_justification(
            decision, quality_score, signal_map, weights
        )
        
        # Recommended action
        recommended_action = self._get_recommended_action(decision, task_type)
        
        return QualityDecision(
            decision=decision,
            quality_score=quality_score,
            confidence=confidence,
            individual_signals=signal_map,
            aggregated_score=aggregated_score,
            justification=justification,
            recommended_action=recommended_action,
            timestamp=datetime.now()
        )
    
    def _make_decision(self, score: float) -> Decision:
        """Map score to decision."""
        if score >= self.THRESHOLDS[Decision.ACCEPT]:
            return Decision.ACCEPT
        elif score >= self.THRESHOLDS[Decision.REVIEW]:
            return Decision.REVIEW
        elif score >= self.THRESHOLDS[Decision.REVISE]:
            return Decision.REVISE
        else:
            return Decision.REJECT
    
    def _generate_justification(
        self,
        decision: Decision,
        score: float,
        signals: Dict[SignalSource, Signal],
        weights: Dict[SignalSource, float]
    ) -> str:
        """Generate human-readable justification."""
        parts = [f"Decision: {decision.value.upper()} (score: {score:.3f})"]
        
        parts.append("\nSignal breakdown:")
        for source, signal in signals.items():
            w = weights.get(source, 0.33)
            reliability = self.reliability.get_reliability(source)
            parts.append(
                f"  - {source.value}: {signal.value:.3f} "
                f"(weight: {w:.2f}, reliability: {reliability:.2f}, confidence: {signal.confidence:.2f})"
            )
        
        # Identify limiting factors
        weakest = min(signals.items(), key=lambda x: x[1].value)
        parts.append(f"\nLimiting factor: {weakest[0].value} "
                    f"(score: {weakest[1].value:.3f})")
        
        # Signal agreement analysis
        values = [s.value for s in signals.values()]
        variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
        if variance > 0.1:
            parts.append(f"\n⚠️ High signal variance ({variance:.3f}): signals disagree")
        else:
            parts.append(f"\n✓ Signal agreement: consistent quality indicators")
        
        return "\n".join(parts)
    
    def _get_recommended_action(self, decision: Decision, task_type: str) -> str:
        """Get recommended action based on decision."""
        actions = {
            Decision.ACCEPT: "Proceed with deployment/execution",
            Decision.REVIEW: "Request human review before proceeding",
            Decision.REVISE: "Auto-revise using critique feedback",
            Decision.REJECT: "Discard and regenerate from scratch"
        }
        
        base = actions.get(decision, "Unknown action")
        
        if decision == Decision.REVISE:
            if task_type == "code":
                base += "; focus on fixing execution errors"
            elif task_type == "research":
                base += "; focus on reasoning consistency"
            elif task_type == "writing":
                base += "; focus on coherence and completeness"
        
        return base
    
    def store_assessment(self, assessment: QualityDecision) -> str:
        """Store quality assessment in database."""
        conn = sqlite3.connect(self.db_path)
        
        assessment_id = hashlib.sha256(
            f"{assessment.timestamp.isoformat()}".encode()
        ).hexdigest()[:16]
        
        signals_json = json.dumps({
            k.value: {
                "value": v.value,
                "confidence": v.confidence,
                "metadata": v.metadata
            }
            for k, v in assessment.individual_signals.items()
        })
        
        conn.execute("""
            INSERT INTO quality_assessments
            (id, task_type, quality_score, confidence, decision, signals_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            assessment_id,
            assessment.decision.value,
            assessment.quality_score,
            assessment.confidence,
            assessment.decision.value,
            signals_json
        ))
        
        conn.commit()
        conn.close()
        
        return assessment_id
    
    def get_historical_stats(self, source: SignalSource = None) -> Dict:
        """Get historical statistics."""
        conn = sqlite3.connect(self.db_path)
        
        if source:
            cursor = conn.execute("""
                SELECT COUNT(*), AVG(quality_score), AVG(confidence)
                FROM quality_assessments
                WHERE signals_json LIKE ?
            """, (f'%{source.value}%',))
        else:
            cursor = conn.execute("""
                SELECT COUNT(*), AVG(quality_score), AVG(confidence)
                FROM quality_assessments
            """)
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "count": row[0] or 0,
            "avg_quality": row[1] or 0.0,
            "avg_confidence": row[2] or 0.0
        }
    
    def get_decision_distribution(self) -> Dict[str, int]:
        """Get distribution of decisions made."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT decision, COUNT(*) 
            FROM quality_assessments 
            GROUP BY decision
        """)
        
        results = {}
        for row in cursor.fetchall():
            results[row[0]] = row[1]
        
        conn.close()
        return results
    
    def export_training_data(self, output_path: str = None) -> str:
        """Export quality assessments as training data."""
        if output_path is None:
            output_path = "/root/evolution/data/quality_training_data.jsonl"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT task_type, quality_score, confidence, decision, signals_json
            FROM quality_assessments
            ORDER BY timestamp DESC
        """)
        
        count = 0
        with open(output_path, 'w') as f:
            for row in cursor.fetchall():
                task_type, quality, confidence, decision, signals_json = row
                
                # Create training example
                example = {
                    "instruction": f"Evaluate {task_type} task quality",
                    "input": json.loads(signals_json),
                    "output": {
                        "decision": decision,
                        "quality_score": quality,
                        "confidence": confidence
                    },
                    "metadata": {
                        "type": "quality_assessment",
                        "sources": list(json.loads(signals_json).keys())
                    }
                }
                
                f.write(json.dumps(example) + '\n')
                count += 1
        
        conn.close()
        return output_path


def create_sample_signals() -> List[Signal]:
    """Create sample signals for testing."""
    now = datetime.now()
    
    return [
        Signal(
            source=SignalSource.CRITIQUE,
            value=0.85,  # Good critique score
            confidence=0.90,
            timestamp=now,
            metadata={
                "accuracy": 0.90,
                "completeness": 0.85,
                "relevance": 0.88
            }
        ),
        Signal(
            source=SignalSource.CYCLE_CONSISTENCY,
            value=0.78,  # Decent reasoning
            confidence=0.85,
            timestamp=now,
            metadata={
                "forward_score": 0.80,
                "backward_score": 0.76,
                "consistency": 0.78
            }
        ),
        Signal(
            source=SignalSource.CONSEQUENTIAL,
            value=0.92,  # Excellent real-world outcome
            confidence=0.95,
            timestamp=now,
            metadata={
                "outcome_type": "FILE_CREATED",
                "irreversibility": 0.70,
                "quality": "real"
            }
        )
    ]


def test_signal_conflicts():
    """Test behavior with conflicting signals."""
    now = datetime.now()
    
    # High critique, low consequential
    conflicting_signals = [
        Signal(
            source=SignalSource.CRITIQUE,
            value=0.95,
            confidence=0.90,
            timestamp=now,
            metadata={}
        ),
        Signal(
            source=SignalSource.CYCLE_CONSISTENCY,
            value=0.88,
            confidence=0.85,
            timestamp=now,
            metadata={}
        ),
        Signal(
            source=SignalSource.CONSEQUENTIAL,
            value=0.35,  # Bad outcome
            confidence=0.95,
            timestamp=now,
            metadata={"error_occurred": True}
        )
    ]
    
    return conflicting_signals


def main():
    """Test the multi-signal aggregator."""
    print("=" * 70)
    print("Eve Multi-Signal Quality Aggregator — Test Run")
    print("=" * 70)
    
    aggregator = MultiSignalAggregator()
    
    # Test different task types
    test_cases = [
        ("code", "Code generation task"),
        ("research", "Research analysis task"),
        ("writing", "Content writing task"),
        ("agentic", "Autonomous agent action"),
        ("learning", "Self-improvement learning")
    ]
    
    signals = create_sample_signals()
    
    for task_type, description in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Task Type: {task_type.upper()}")
        print(f"Description: {description}")
        print(f"{'─' * 70}")
        
        # Get profile
        profile = TASK_PROFILES.get(task_type, TASK_PROFILES["learning"])
        print(f"Weights: {profile.description}")
        print(f"  - Critique: {profile.weights[SignalSource.CRITIQUE]:.2f}")
        print(f"  - Cycle-Consistency: {profile.weights[SignalSource.CYCLE_CONSISTENCY]:.2f}")
        print(f"  - Consequential: {profile.weights[SignalSource.CONSEQUENTIAL]:.2f}")
        
        # Aggregate
        decision = aggregator.aggregate(signals, task_type=task_type)
        
        print(f"\n📊 Result:")
        print(f"  Quality Score: {decision.quality_score:.4f}")
        print(f"  Confidence: {decision.confidence:.4f}")
        print(f"  Decision: {decision.decision.value.upper()}")
        print(f"  Action: {decision.recommended_action}")
        
        print(f"\n📝 Justification:")
        for line in decision.justification.split('\n'):
            print(f"    {line}")
        
        # Store assessment
        assessment_id = aggregator.store_assessment(decision)
        print(f"\n💾 Stored as assessment: {assessment_id}")
    
    # Test conflicting signals
    print(f"\n{'=' * 70}")
    print("Conflicting Signals Test (High critique + Low consequential)")
    print(f"{'=' * 70}")
    
    conflicting = test_signal_conflicts()
    conflict_decision = aggregator.aggregate(conflicting, task_type="code")
    
    print(f"\nTask Type: CODE (weights: 0.4 / 0.2 / 0.4)")
    print(f"Quality Score: {conflict_decision.quality_score:.4f}")
    print(f"Decision: {conflict_decision.decision.value.upper()}")
    print(f"\nJustification:")
    for line in conflict_decision.justification.split('\n'):
        print(f"  {line}")
    
    # Show historical stats
    print(f"\n{'=' * 70}")
    print("Historical Statistics")
    print(f"{'=' * 70}")
    
    for source in SignalSource:
        stats = aggregator.get_historical_stats(source)
        print(f"\n{source.value}:")
        print(f"  Assessments: {stats['count']}")
        print(f"  Avg Quality: {stats['avg_quality']:.4f}")
        print(f"  Avg Confidence: {stats['avg_confidence']:.4f}")
    
    # Decision distribution
    print(f"\n{'=' * 70}")
    print("Decision Distribution")
    print(f"{'=' * 70}")
    
    dist = aggregator.get_decision_distribution()
    for decision, count in sorted(dist.items()):
        print(f"  {decision.upper()}: {count}")
    
    # Export training data
    print(f"\n{'=' * 70}")
    export_path = aggregator.export_training_data()
    print(f"📤 Training data exported to: {export_path}")
    
    print(f"\n{'=' * 70}")
    print("✅ All tests passed. Multi-signal aggregation operational.")
    print(f"{'=' * 70}\n")
    
    return True


if __name__ == "__main__":
    main()
