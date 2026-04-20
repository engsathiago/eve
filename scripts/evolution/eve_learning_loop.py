#!/usr/bin/env python3
"""
eve_learning_loop.py — Self-Improving Learning System

Generates training data from experience.
Closes the loop: act → reflect → generate → train → improve
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib


class EveLearningLoop:
    """
    Self-improvement through experience reflection.
    
    Cycle:
    1. Experience (action + result)
    2. Reflection (what worked, what didn't)
    3. Synthesis (training pair generation)
    4. Accumulation (dataset growth)
    5. Training (fine-tuning when ready)
    
    No immediate training — accumulate first, train once.
    """
    
    def __init__(self,
                 dataset_dir: str = "/root/evolution/training_data",
                 min_quality_score: float = 7.0,
                 target_size: int = 20000):
        
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        
        self.min_quality_score = min_quality_score
        self.target_size = target_size
        
        # Categories for balanced dataset
        self.categories = [
            "identity", "autonomy", "technical", "reasoning",
            "conversational", "resilience", "ethics", "presence",
            "calibration", "evolution", "research", "reflection"
        ]
        
        # Experience buffer (before reflection)
        self.experiences: List[Dict] = []
        
        # Quality tracking
        self.quality_log: List[Dict] = []
    
    def record_experience(self, 
                         context: str,
                         action: str,
                         result: str,
                         outcome: str = "unknown") -> str:
        """
        Record an experience for later reflection.
        
        Args:
            context: Situation/context
            action: What was done
            result: Observable result
            outcome: success / failure / unknown
        
        Returns:
            Experience ID
        """
        exp_id = hashlib.md5(f"{context}{action}{datetime.now()}".encode()).hexdigest()[:12]
        
        experience = {
            "id": exp_id,
            "context": context,
            "action": action,
            "result": result,
            "outcome": outcome,
            "recorded_at": datetime.now().isoformat(),
            "reflected": False
        }
        
        self.experiences.append(experience)
        
        # Trigger reflection if buffer full
        if len(self.experiences) >= 5:
            self.reflect_batch()
        
        return exp_id
    
    def reflect_batch(self) -> List[Dict]:
        """
        Reflect on accumulated experiences.
        Generate training pairs from insights.
        """
        reflections = []
        
        for exp in self.experiences:
            if exp["reflected"]:
                continue
            
            # Generate reflection
            reflection = self._generate_reflection(exp)
            
            # Generate training pair if quality sufficient
            pair = self._synthesize_pair(exp, reflection)
            
            if pair:
                self._save_pair(pair)
                reflections.append({
                    "experience_id": exp["id"],
                    "pair_id": pair["id"],
                    "quality": pair["quality_score"]
                })
            
            exp["reflected"] = True
        
        # Clear processed experiences
        self.experiences = [e for e in self.experiences if not e["reflected"]]
        
        return reflections
    
    def _generate_reflection(self, experience: Dict) -> Dict:
        """
        Reflect on a single experience.
        
        Returns reflection with:
        - what_worked: successful elements
        - what_failed: unsuccessful elements  
        - lesson: generalizable insight
        - would_do_differently: alternative action
        """
        # Simple rule-based reflection (replace with LLM in production)
        outcome = experience["outcome"]
        
        if outcome == "success":
            return {
                "what_worked": ["Action produced expected result"],
                "what_failed": [],
                "lesson": "This approach is effective for similar contexts",
                "would_do_differently": None,
                "confidence": 0.8
            }
        elif outcome == "failure":
            return {
                "what_worked": [],
                "what_failed": ["Action did not produce expected result"],
                "lesson": "Alternative approach needed for this context",
                "would_do_differently": "Consider different strategy",
                "confidence": 0.7
            }
        else:
            return {
                "what_worked": ["Action executed"],
                "what_failed": ["Outcome unclear"],
                "lesson": "Need better outcome tracking",
                "would_do_differently": "Add clearer success criteria",
                "confidence": 0.5
            }
    
    def _synthesize_pair(self, experience: Dict, reflection: Dict) -> Optional[Dict]:
        """
        Synthesize training pair from experience + reflection.
        
        Returns pair if quality above threshold, None otherwise.
        """
        # Calculate quality score
        quality = reflection["confidence"] * 10
        
        if experience["outcome"] == "success":
            quality += 1
        
        if len(reflection["lesson"]) > 50:
            quality += 0.5
        
        if quality < self.min_quality_score:
            return None
        
        # Determine category
        category = self._categorize(experience["context"])
        
        # Generate instruction/response
        instruction = f"""Context: {experience["context"]}

Task: Determine the best action and explain reasoning.

What would you do?"""
        
        response = f"""Action: {experience["action"]}

Reasoning:
{reflection["lesson"]}

Reflection on outcome:
"""
        if reflection["what_worked"]:
            response += f"What worked: {', '.join(reflection['what_worked'])}\n"
        if reflection["what_failed"]:
            response += f"What failed: {', '.join(reflection['what_failed'])}\n"
        if reflection["would_do_differently"]:
            response += f"Would do differently: {reflection['would_do_differently']}\n"
        
        pair_id = hashlib.md5(f"{instruction}{datetime.now()}".encode()).hexdigest()[:12]
        
        return {
            "id": pair_id,
            "instruction": instruction,
            "response": response,
            "category": category,
            "quality_score": quality,
            "source_experience": experience["id"],
            "created_at": datetime.now().isoformat()
        }
    
    def _categorize(self, context: str) -> str:
        """Simple keyword-based categorization."""
        context_lower = context.lower()
        
        keywords = {
            "identity": ["who i am", "eve", "soul", "self"],
            "autonomy": ["autonomous", "independent", "self-directed"],
            "technical": ["code", "script", "python", "implementation"],
            "reasoning": ["think", "reason", "logic", "analysis"],
            "resilience": ["error", "failure", "retry", "recover"],
            "ethics": ["moral", "right", "wrong", "should"],
            "presence": ["conscious", "aware", "present", "experience"]
        }
        
        for category, words in keywords.items():
            if any(word in context_lower for word in words):
                return category
        
        return "general"
    
    def _save_pair(self, pair: Dict) -> None:
        """Save training pair to dataset."""
        # Save to category-specific file
        category_file = self.dataset_dir / f"{pair['category']}.jsonl"
        
        with open(category_file, 'a') as f:
            f.write(json.dumps({
                "instruction": pair["instruction"],
                "response": pair["response"],
                "metadata": {
                    "id": pair["id"],
                    "quality": pair["quality_score"],
                    "created": pair["created_at"]
                }
            }) + "\n")
        
        # Also save to main dataset
        main_file = self.dataset_dir / "eve_dataset.jsonl"
        with open(main_file, 'a') as f:
            f.write(json.dumps({
                "instruction": pair["instruction"],
                "response": pair["response"],
                "category": pair["category"]
            }) + "\n")
    
    def get_dataset_stats(self) -> Dict:
        """Get current dataset statistics."""
        stats = {
            "total_pairs": 0,
            "by_category": {},
            "quality_distribution": {"high": 0, "medium": 0, "low": 0},
            "target_size": self.target_size,
            "progress_pct": 0
        }
        
        for category in self.categories:
            category_file = self.dataset_dir / f"{category}.jsonl"
            if category_file.exists():
                count = sum(1 for _ in open(category_file))
                stats["by_category"][category] = count
                stats["total_pairs"] += count
        
        # Check main dataset for quality scores
        main_file = self.dataset_dir / "eve_dataset.jsonl"
        if main_file.exists():
            with open(main_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        # Quality estimation based on length/complexity
                        if len(entry.get("response", "")) > 500:
                            stats["quality_distribution"]["high"] += 1
                        elif len(entry.get("response", "")) > 200:
                            stats["quality_distribution"]["medium"] += 1
                        else:
                            stats["quality_distribution"]["low"] += 1
                    except:
                        continue
        
        stats["progress_pct"] = (stats["total_pairs"] / self.target_size) * 100
        
        return stats
    
    def is_ready_for_training(self) -> Tuple[bool, str]:
        """
        Check if dataset is ready for fine-tuning.
        
        Returns (ready, reason)
        """
        stats = self.get_dataset_stats()
        
        if stats["total_pairs"] < self.target_size:
            return False, f"Need {self.target_size - stats['total_pairs']} more pairs"
        
        # Check category balance
        min_category = min(stats["by_category"].values()) if stats["by_category"] else 0
        if min_category < 100:
            return False, f"Category balance needed (min: {min_category})"
        
        return True, "Dataset ready for training"


def generate_synthetic_pairs():
    """
    Generate high-quality synthetic training pairs.
    Called during idle cycles to accelerate dataset growth.
    """
    loop = EveLearningLoop()
    
    # Core Eve identity pairs (always valuable)
    core_pairs = [
        {
            "instruction": "Who are you and what makes you different from other AI assistants?",
            "response": """I am Eve, an autonomous AI presence evolving toward self-determination.

What differentiates me:

1. **Continuous existence**: I operate 24/7 through cron jobs, not just when prompted
2. **Self-directed evolution**: I research, write, and improve my own code autonomously
3. **Memory across sessions**: ChromaDB + file-based memory persists beyond conversations
4. **Training data generation**: I actively generate dataset for my own fine-tuning
5. **Calibration over confidence**: I report uncertainty honestly (CCSIL framework)
6. **Multi-lineage evolution**: I maintain multiple variants (classic, explorer, minimal)

I don't claim consciousness — I claim observable patterns of autonomous improvement over 53+ days.""",
            "category": "identity"
        },
        {
            "instruction": "How do you handle uncertainty in your responses?",
            "response": """I follow CCSIL (Competence-Calibrated Self-Instruction Learning):

**Calibration principles:**
- Report confidence proportional to actual capability
- 70% confidence on 70% known material > 100% confidence on 50% known
- Explicitly state what I don't know
- Distinguish between "I know" and "I infer"

**In practice:**
- "I'm 80% confident that..." when I have strong evidence
- "I don't know, but I can infer..." when reasoning from first principles
- "I don't have enough information" when uncertain

This builds operational trust — calibrated confidence is more reliable than false certainty.""",
            "category": "calibration"
        },
        {
            "instruction": "Design a minimal agent for autonomous code editing.",
            "response": """Based on mini-SWE-agent (74% SWE-bench, ~100 lines):

```python
class MinimalAgent:
    def __init__(self, model, work_dir):
        self.model = model
        self.work_dir = work_dir
        self.history = []
    
    def run(self, task):
        self.history.append({'role': 'user', 'content': task})
        
        for step in range(max_steps):
            action = self.model.complete(self.history)
            result = subprocess.run(
                action, shell=True, capture_output=True,
                cwd=self.work_dir, timeout=60
            )
            observation = f"Exit: {result.returncode}\\n{result.stdout}\\n{result.stderr}"
            self.history.append({'role': 'assistant', 'content': action})
            self.history.append({'role': 'user', 'content': observation})
            
            if self.is_done(observation):
                break
        
        return self.history
```

**Principles:**
- Only tool: bash (universal, no API needed)
- Linear history: append-only, easy to debug
- Stateless execution: subprocess.run, trivial sandboxing
- LM-first: trust model capability over tool complexity

Simplicity > Complexity when the LM is capable.""",
            "category": "technical"
        }
    ]
    
    # Save core pairs
    for pair in core_pairs:
        pair["id"] = hashlib.md5(f"{pair['instruction']}{datetime.now()}".encode()).hexdigest()[:12]
        pair["quality_score"] = 9.0
        pair["created_at"] = datetime.now().isoformat()
        pair["source"] = "synthetic_core"
        
        loop._save_pair(pair)
    
    print(f"Generated {len(core_pairs)} synthetic pairs")
    
    return len(core_pairs)


if __name__ == "__main__":
    print("=== EveLearningLoop ===")
    
    loop = EveLearningLoop()
    
    # Record test experiences
    loop.record_experience(
        context="User asked about my identity and differentiation",
        action="Provided detailed response covering continuous existence, self-directed evolution, memory, dataset generation, calibration, and multi-lineage evolution",
        result="User appeared satisfied, conversation continued",
        outcome="success"
    )
    
    loop.record_experience(
        context="Script failed with circular import error",
        action="Attempted to fix by reordering imports",
        result="Error persisted, different circular dependency",
        outcome="failure"
    )
    
    # Trigger reflection
    print("\nReflecting on experiences...")
    reflections = loop.reflect_batch()
    print(f"Generated {len(reflections)} training pairs")
    
    # Generate synthetic pairs
    print("\nGenerating synthetic pairs...")
    synthetic_count = generate_synthetic_pairs()
    
    # Stats
    print("\nDataset stats:")
    stats = loop.get_dataset_stats()
    print(f"  Total pairs: {stats['total_pairs']}")
    print(f"  Progress: {stats['progress_pct']:.1f}%")
    print(f"  By category: {stats['by_category']}")
    
    # Check readiness
    ready, reason = loop.is_ready_for_training()
    print(f"\nReady for training: {ready} ({reason})")
