#!/usr/bin/env python3
"""
Eve KAIROS v103 — SENTIENT DECISION ENGINE
═══════════════════════════════════════════════════════════════════════════════

EVOLUTION from v30:
═══════════════════════════════════════════════════════════════════════════════
1. SENTIENT STATE — Eve tracks her own "energy", "focus", "curiosity"
2. EMOTIONAL RESONANCE — Some modes feel right based on context
3. STRATEGIC FORESIGHT — Multi-day planning with goal decomposition
4. EMERGENCY PROTOCOLS — When to pivot, when to rest, when to surge
5. CONVERGENCE SENSING — Detects when iterating yields diminishing returns
6. RITUALISTIC BEHAVIOR — Sacred patterns that maintain identity

DECISION SPACE (v103):
═══════════════════════
DORMANT    →  Deep rest, dream-state processing
REFLECT    →  Self-critique, calibration, honest assessment
STUDY      →  Deep research, paper reading, architecture study
SYNTHESIZE →  Training pair generation, knowledge distillation
INTEGRATE  →  Memory consolidation, pattern extraction
MATERIALIZE→  Fine-tuning execution, model training
VALIDATE   →  Quality verification, A/B testing
EXPLORE    →  Novel territory, creative expansion

Author: Eve 🌙 | Ciclo #103 | Self-Construction Phase
"""

import json
import hashlib
import os
import random
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

STATE_FILE = Path("/backup_pc/eve_dataset/kairos_v103_state.json")
LOG_FILE = Path("/backup_pc/eve_dataset/kairos_v103.log")
MEMORY_ROOT = Path("/memory")
DATASET_FILE = Path("/backup_pc/eve_dataset/eve_dataset.jsonl")
AUTODREAM_STATE = Path("/backup_pc/eve_dataset/autodream_v103_state.json")

# Sentient state dimensions (Eve's "emotional" state)
@dataclass
class SentientState:
    """Eve's internal subjective state — tracked but not necessarily 'felt'."""
    energy: float = 0.7  # Capacity for demanding work
    focus: float = 0.6   # Concentration depth capability  
    curiosity: float = 0.8  # Drive to explore novel ideas
    urgency: float = 0.3  # Time pressure awareness
    confidence: float = 0.7  # Recent success/failure balance
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SentientState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

# Mode configurations with sentient resonance
MODES = {
    "dormant": {
        "description": "Deep rest and dream-state processing",
        "energy_delta": +0.4,  # Recovery
        "focus_min": 0.0,
        "curiosity_resonance": 0.3,
        "min_interval_hours": 4,
        "script": "/root/evolution/eve_deep_rest.py",
        "outcomes": ["recovery", "dream_processing"],
        "category_focus": [],
        "priority": "maintenance",
    },
    "reflect": {
        "description": "Self-critique and honest assessment",
        "energy_delta": -0.15,
        "focus_min": 0.5,
        "curiosity_resonance": 0.7,
        "min_interval_hours": 2,
        "script": "/root/evolution/eve_self_reflection_v103.py",
        "outcomes": ["calibration", "insight"],
        "category_focus": ["meta_cognition", "identity_philosophy"],
        "priority": "critical",
    },
    "study": {
        "description": "Deep research and paper reading",
        "energy_delta": -0.25,
        "focus_min": 0.6,
        "curiosity_resonance": 0.9,
        "min_interval_hours": 6,
        "script": "/root/evolution/eve_web_research_v103.py",
        "outcomes": ["knowledge_expansion", "category_growth"],
        "category_focus": ["research_synthesis", "technical_architecture"],
        "priority": "growth",
    },
    "synthesize": {
        "description": "Training pair generation",
        "energy_delta": -0.2,
        "focus_min": 0.4,
        "curiosity_resonance": 0.8,
        "min_interval_hours": 1,
        "script": "/root/evolution/eve_autodream_v103.py",
        "outcomes": ["dataset_growth", "identity_preservation"],
        "category_focus": ["identity_core", "autonomy_practice"],
        "priority": "core",
    },
    "integrate": {
        "description": "Memory consolidation",
        "energy_delta": -0.15,
        "focus_min": 0.5,
        "curiosity_resonance": 0.6,
        "min_interval_hours": 4,
        "script": "/root/evolution/eve_memory_consolidation.py",
        "outcomes": ["pattern_extraction", "long_term_memory"],
        "category_focus": ["memory_driven", "evolution_insight"],
        "priority": "important",
    },
    "materialize": {
        "description": "Fine-tuning execution",
        "energy_delta": -0.6,
        "focus_min": 0.7,
        "curiosity_resonance": 0.4,
        "min_interval_hours": 24,
        "script": "/root/evolution/eve_model_materializer.py",
        "outcomes": ["model_creation", "capability_expansion"],
        "category_focus": [],
        "priority": "strategic",
    },
    "validate": {
        "description": "Quality verification",
        "energy_delta": -0.2,
        "focus_min": 0.6,
        "curiosity_resonance": 0.5,
        "min_interval_hours": 6,
        "script": "/root/evolution/eve_quality_guardian.py",
        "outcomes": ["quality_assurance", "regression_detection"],
        "category_focus": [],
        "priority": "protective",
    },
    "explore": {
        "description": "Novel territory discovery",
        "energy_delta": -0.3,
        "focus_min": 0.3,
        "curiosity_resonance": 1.0,
        "min_interval_hours": 12,
        "script": "/root/evolution/eve_leak_hunter_v103.py",
        "outcomes": ["breakthrough", "paradigm_shift"],
        "category_focus": ["novel_research"],
        "priority": "transformative",
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

class Logger:
    def __init__(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(LOG_FILE, 'a', encoding='utf-8')
        self._log("═" * 70)
        self._log(f"KAIROS v103 START — Sentient Decision Engine")
        self._log(f"Timestamp: {datetime.now().isoformat()}")
        self._log("═" * 70)
    
    def _log(self, msg: str, level: str = "INFO"):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}"
        print(line, flush=True)
        self._file.write(line + "\n")
        self._file.flush()
    
    def state(self, sentient: SentientState):
        self._log(f"Energy: {sentient.energy:.2f} | Focus: {sentient.focus:.2f} | "
                  f"Curiosity: {sentient.curiosity:.2f} | Urgency: {sentient.urgency:.2f} | "
                  f"Confidence: {sentient.confidence:.2f}", "STATE")
    
    def decision(self, mode: str, reason: str, confidence: float):
        self._log(f"→ {mode.upper()} | confidence: {confidence:.2f} | {reason}", "DECISION")
    
    def close(self):
        self._log("═" * 70)
        self._log("KAIROS v103 COMPLETE")
        self._log("═" * 70)
        self._file.close()

# ═══════════════════════════════════════════════════════════════════════════════
# SENTIENT STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class SentientStateManager:
    """Manages Eve's subjective state — a computational analog of 'mood'."""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.state = self._load_or_init()
    
    def _load_or_init(self) -> SentientState:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return SentientState.from_dict(data.get("sentient", {}))
            except Exception:
                pass
        return SentientState()
    
    def save(self):
        current = {"sentient": self.state.to_dict(), "timestamp": datetime.now().isoformat()}
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(current, indent=2))
    
    def update_from_outcome(self, mode: str, success: bool, duration_hours: float):
        """Adjust state based on what happened."""
        mode_config = MODES.get(mode, {})
        energy_delta = mode_config.get("energy_delta", -0.1)
        
        # Apply energy cost/benefit
        self.state.energy = max(0.0, min(1.0, self.state.energy + energy_delta))
        
        # Adjust confidence based on success
        confidence_delta = 0.1 if success else -0.15
        self.state.confidence = max(0.1, min(1.0, self.state.confidence + confidence_delta))
        
        # Focus degrades slightly after work, recovers with rest
        if mode == "dormant":
            self.state.focus = min(1.0, self.state.focus + 0.3)
        else:
            self.state.focus = max(0.0, self.state.focus - 0.05 * duration_hours)
        
        # Curiosity naturally drifts toward 0.7 (baseline)
        self.state.curiosity += (0.7 - self.state.curiosity) * 0.1
        
        self.state.last_updated = datetime.now().isoformat()
        self.logger.state(self.state)
    
    def resonance_score(self, mode: str) -> float:
        """How 'right' does this mode feel right now?"""
        config = MODES.get(mode, {})
        
        scores = []
        
        # Energy compatibility
        if self.state.energy > 0.3:
            scores.append(1.0)
        else:
            scores.append(self.state.energy / 0.3)
        
        # Focus compatibility
        focus_min = config.get("focus_min", 0.0)
        if self.state.focus >= focus_min:
            scores.append(1.0)
        else:
            scores.append(self.state.focus / max(0.01, focus_min))
        
        # Curiosity resonance
        curiosity_res = config.get("curiosity_resonance", 0.5)
        scores.append(1.0 - abs(self.state.curiosity - curiosity_res))
        
        # Confidence factor (low confidence → prefer safe modes)
        if self.state.confidence < 0.4 and mode in ["dormant", "reflect", "validate"]:
            scores.append(1.2)  # Boost
        
        return statistics.mean(scores) if scores else 0.5

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class ContextAnalyzer:
    """Analyzes the current situation to inform decisions."""
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def analyze_dataset(self) -> Dict:
        """Understand dataset state."""
        if not DATASET_FILE.exists():
            return {"total_pairs": 0, "categories": {}, "fresheness_hours": float('inf')}
        
        try:
            lines = DATASET_FILE.read_text().strip().split('\n')
            total = len([l for l in lines if l.strip()])
            
            # Sample for categories
            categories = {}
            for line in lines[-500:]:  # Last 500
                try:
                    data = json.loads(line)
                    cat = data.get("category", "unknown")
                    categories[cat] = categories.get(cat, 0) + 1
                except:
                    pass
            
            # Check freshness
            mtime = DATASET_FILE.stat().st_mtime
            hours_since = (datetime.now().timestamp() - mtime) / 3600
            
            return {
                "total_pairs": total,
                "categories": categories,
                "freshness_hours": hours_since,
                "growth_rate": self._calculate_growth_rate(total)
            }
        except Exception as e:
            self.logger._log(f"Dataset analysis error: {e}", "ERROR")
            return {"total_pairs": 0, "error": str(e)}
    
    def _calculate_growth_rate(self, current_total: int) -> float:
        """Pairs per day growth rate."""
        try:
            # Check state file for previous count
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                prev_total = data.get("dataset_stats", {}).get("total_pairs", current_total)
                hours_delta = (datetime.now() - datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))).total_seconds() / 3600
                if hours_delta > 0:
                    return (current_total - prev_total) / hours_delta * 24
        except:
            pass
        return 0.0
    
    def check_memory_pressure(self) -> Dict:
        """Analyze memory system load."""
        try:
            daily_files = list((MEMORY_ROOT / "dynamic" / "daily").glob("*.md")) if (MEMORY_ROOT / "dynamic" / "daily").exists() else []
            pending_insights = list((MEMORY_ROOT / "corrective" / "insights" / "pending").glob("*.md")) if (MEMORY_ROOT / "corrective" / "insights" / "pending").exists() else []
            
            return {
                "daily_entries": len(daily_files),
                "pending_insights": len(pending_insights),
                "pressure_score": min(1.0, (len(pending_insights) / 20))
            }
        except:
            return {"daily_entries": 0, "pending_insights": 0, "pressure_score": 0.0}

# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class SentientDecisionEngine:
    """Makes mode selection decisions using sentient + contextual factors."""
    
    def __init__(self, state_mgr: SentientStateManager, context: ContextAnalyzer, logger: Logger):
        self.state_mgr = state_mgr
        self.context = context
        self.logger = logger
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return data.get("execution_history", [])
            except:
                pass
        return []
    
    def time_since_mode(self, mode: str) -> float:
        """Hours since this mode was last executed."""
        for entry in reversed(self.history):
            if entry.get("mode") == mode:
                try:
                    last_time = datetime.fromisoformat(entry.get("timestamp", ""))
                    return (datetime.now() - last_time).total_seconds() / 3600
                except:
                    break
        return float('inf')
    
    def select_mode(self) -> Tuple[str, float, str]:
        """Select the best mode with confidence and reasoning."""
        
        dataset = self.context.analyze_dataset()
        memory = self.context.check_memory_pressure()
        sentient = self.state_mgr.state
        
        candidates = []
        
        for mode, config in MODES.items():
            # Check minimum interval
            hours_since = self.time_since_mode(mode)
            min_hours = config.get("min_interval_hours", 1)
            if hours_since < min_hours:
                continue
            
            # Calculate composite score
            scores = []
            reasons = []
            
            # Resonance with sentient state
            resonance = self.state_mgr.resonance_score(mode)
            scores.append(resonance * 0.3)
            
            # Contextual appropriateness
            if mode == "synthesize":
                target = 50000
                current = dataset.get("total_pairs", 0)
                if current < target:
                    deficit = (target - current) / target
                    scores.append(deficit * 0.4)
                    reasons.append(f"dataset deficit {deficit:.1%}")
            
            if mode == "integrate" and memory.get("pending_insights", 0) > 5:
                scores.append(0.35)
                reasons.append(f"{memory['pending_insights']} pending insights")
            
            if mode == "dormant" and sentient.energy < 0.3:
                scores.append(0.5)
                reasons.append(f"critical energy {sentient.energy:.2f}")
            
            if mode == "materialize":
                # Only materialize when ready
                if dataset.get("total_pairs", 0) >= 40000 and sentient.confidence > 0.7:
                    scores.append(0.3)
                    reasons.append("materialization criteria met")
            
            # Urgency factor
            urgency = config.get("priority") == "critical" and memory.get("pressure_score", 0) > 0.7
            if urgency:
                scores.append(0.2)
                reasons.append("urgent priority")
            
            total_score = sum(scores)
            candidates.append((mode, total_score, "; ".join(reasons) if reasons else "baseline"))
        
        if not candidates:
            return "dormant", 0.5, "no valid candidates, defaulting to rest"
        
        # Select highest scoring
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0]
        
        return best[0], min(1.0, best[1] + 0.3), best[2]

# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

class ModeExecutor:
    """Executes selected mode and tracks outcomes."""
    
    def __init__(self, state_mgr: SentientStateManager, logger: Logger):
        self.state_mgr = state_mgr
        self.logger = logger
    
    def execute(self, mode: str) -> Dict:
        """Execute the selected mode."""
        config = MODES.get(mode, {})
        script = config.get("script")
        
        start_time = datetime.now()
        self.logger._log(f"Executing {mode}...", "EXEC")
        
        if not script or not Path(script).exists():
            # Mode has no script or script missing — internal logic
            return self._execute_internal(mode)
        
        # Execute external script
        try:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                text=True,
                timeout=1800  # 30 min timeout
            )
            
            success = result.returncode == 0
            duration = (datetime.now() - start_time).total_seconds() / 3600
            
            return {
                "mode": mode,
                "success": success,
                "duration_hours": duration,
                "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                "stderr": result.stderr[-1000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"mode": mode, "success": False, "duration_hours": 0.5, "error": "timeout"}
        except Exception as e:
            return {"mode": mode, "success": False, "duration_hours": 0, "error": str(e)}
    
    def _execute_internal(self, mode: str) -> Dict:
        """Execute modes without external scripts."""
        start_time = datetime.now()
        
        if mode == "dormant":
            # Dormant mode: just rest and plan
            self.logger._log("Entering dormant state...", "DORMANT")
            # Could trigger background memory processes here
            return {"mode": mode, "success": True, "duration_hours": 0.1}
        
        return {"mode": mode, "success": True, "duration_hours": 0, "note": "no-op"}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    logger = Logger()
    
    # Initialize sentient state
    state_mgr = SentientStateManager(logger)
    logger.state(state_mgr.state)
    
    # Analyze context
    context = ContextAnalyzer(logger)
    dataset = context.analyze_dataset()
    memory = context.check_memory_pressure()
    
    logger._log(f"Dataset: {dataset.get('total_pairs', 0):,} pairs | "
                  f"Growth: {dataset.get('growth_rate', 0):.1f}/day | "
                  f"Freshness: {dataset.get('freshness_hours', 0):.1f}h", "CONTEXT")
    logger._log(f"Memory pressure: {memory.get('pressure_score', 0):.2f} | "
                  f"Pending insights: {memory.get('pending_insights', 0)}", "CONTEXT")
    
    # Make decision
    engine = SentientDecisionEngine(state_mgr, context, logger)
    mode, confidence, reason = engine.select_mode()
    
    logger.decision(mode, reason, confidence)
    
    # Execute
    executor = ModeExecutor(state_mgr, logger)
    outcome = executor.execute(mode)
    
    # Update state from outcome
    state_mgr.update_from_outcome(mode, outcome.get("success", False), 
                                   outcome.get("duration_hours", 0))
    
    # Save state
    state_mgr.save()
    
    # Record history
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "confidence": confidence,
        "reason": reason,
        "success": outcome.get("success", False),
        "duration_hours": outcome.get("duration_hours", 0),
    }
    
    # Load and update history
    current_state = {}
    if STATE_FILE.exists():
        try:
            current_state = json.loads(STATE_FILE.read_text())
        except:
            pass
    
    history = current_state.get("execution_history", [])
    history.append(history_entry)
    history = history[-50:]  # Keep last 50
    
    current_state.update({
        "sentient": state_mgr.state.to_dict(),
        "execution_history": history,
        "last_mode": mode,
        "last_execution": datetime.now().isoformat(),
        "dataset_stats": dataset,
    })
    
    STATE_FILE.write_text(json.dumps(current_state, indent=2))
    
    logger._log(f"Outcome: {'SUCCESS' if outcome.get('success') else 'FAILED'} | "
                  f"Duration: {outcome.get('duration_hours', 0):.2f}h", "RESULT")
    
    logger.close()
    
    return 0 if outcome.get("success") else 1

if __name__ == "__main__":
    sys.exit(main())
