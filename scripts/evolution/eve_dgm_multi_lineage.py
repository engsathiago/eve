#!/usr/bin/env python3
"""
eve_dgm_multi_lineage.py - Darwin Gödel Machine-inspired Multi-Lineage Evolution

Inspired by: https://github.com/jennyzzt/dgm
Paper: arXiv:2505.22954 - Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents

Core concept: Maintain archive of N agent variants, sample → mutate → evaluate → return to archive.
Parallel exploration of strategy space instead of converging on single "best" version.

For Eve: Apply to script versions, not just code mutations.
"""

import os
import json
import hashlib
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import random

# Configuration
ARCHIVE_DIR = Path("/root/evolution/archive")
MAX_LINEAGES = 5  # Keep N parallel versions
MIN_SCORE_THRESHOLD = 0.6  # Prune below this
MUTATION_TYPES = ["rewrite", "optimize", "extend", "simplify"]

class LineageArchive:
    """Manages archive of script variants with scores."""
    
    def __init__(self, script_name: str):
        self.script_name = script_name
        self.archive_dir = ARCHIVE_DIR / script_name
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.archive_dir / "lineage_meta.json"
        self.lineages = self._load_meta()
    
    def _load_meta(self) -> List[Dict[str, Any]]:
        """Load lineage metadata."""
        if self.meta_file.exists():
            with open(self.meta_file) as f:
                return json.load(f)
        return []
    
    def _save_meta(self):
        """Save lineage metadata."""
        with open(self.meta_file, 'w') as f:
            json.dump(self.lineages, f, indent=2)
    
    def add_lineage(self, version: str, score: float, features: List[str]) -> str:
        """Add new lineage to archive."""
        lineage_id = hashlib.md5(f"{version}{datetime.now()}".encode()).hexdigest()[:8]
        
        entry = {
            "id": lineage_id,
            "version": version,
            "score": score,
            "features": features,
            "created": datetime.now().isoformat(),
            "parent": None  # For tracking mutations
        }
        
        self.lineages.append(entry)
        self._prune_archive()
        self._save_meta()
        
        return lineage_id
    
    def mutate_lineage(self, parent_id: str, new_version: str, mutation_type: str) -> str:
        """Create mutated offspring from parent lineage."""
        # Find parent
        parent = next((l for l in self.lineages if l["id"] == parent_id), None)
        if not parent:
            raise ValueError(f"Parent {parent_id} not found")
        
        # Create child
        child_id = hashlib.md5(f"{new_version}{datetime.now()}".encode()).hexdigest()[:8]
        
        entry = {
            "id": child_id,
            "version": new_version,
            "score": 0.0,  # Will be evaluated
            "features": parent["features"] + [f"mutation:{mutation_type}"],
            "created": datetime.now().isoformat(),
            "parent": parent_id,
            "mutation_type": mutation_type
        }
        
        self.lineages.append(entry)
        self._save_meta()
        
        return child_id
    
    def _prune_archive(self):
        """Keep only top N lineages by score."""
        if len(self.lineages) <= MAX_LINEAGES:
            return
        
        # Sort by score descending
        self.lineages.sort(key=lambda x: x["score"], reverse=True)
        
        # Keep top N, but ensure diversity (don't keep too similar)
        kept = []
        for lineage in self.lineages:
            if len(kept) >= MAX_LINEAGES:
                break
            
            # Check diversity against kept lineages
            is_diverse = True
            for existing in kept:
                feature_overlap = set(lineage["features"]) & set(existing["features"])
                if len(feature_overlap) / max(len(lineage["features"]), 1) > 0.8:
                    is_diverse = False
                    break
            
            if is_diverse or lineage["score"] > 0.9:  # Always keep very high scores
                kept.append(lineage)
        
        self.lineages = kept
    
    def sample_lineage(self, strategy: str = "weighted") -> Optional[Dict[str, Any]]:
        """Sample lineage for mutation."""
        if not self.lineages:
            return None
        
        if strategy == "weighted":
            # Weight by score
            weights = [l["score"] + 0.1 for l in self.lineages]  # +0.1 ensures some chance for low scores
            total = sum(weights)
            probs = [w / total for w in weights]
            return random.choices(self.lineages, weights=probs)[0]
        
        elif strategy == "diverse":
            # Sample from different feature clusters
            feature_groups = {}
            for lineage in self.lineages:
                key = tuple(sorted(lineage["features"])[:2])  # Group by first 2 features
                if key not in feature_groups:
                    feature_groups[key] = []
                feature_groups[key].append(lineage)
            
            # Pick random group, then random lineage within
            group = random.choice(list(feature_groups.values()))
            return random.choice(group)
        
        else:  # random
            return random.choice(self.lineages)
    
    def update_score(self, lineage_id: str, score: float):
        """Update score after evaluation."""
        for lineage in self.lineages:
            if lineage["id"] == lineage_id:
                lineage["score"] = score
                lineage["evaluated"] = datetime.now().isoformat()
                break
        self._save_meta()


class ScriptEvaluator:
    """Evaluates script quality through multiple criteria."""
    
    @staticmethod
    def evaluate(script_path: Path) -> Dict[str, float]:
        """Evaluate script and return score breakdown."""
        scores = {}
        
        # 1. Syntax check
        scores["syntax"] = ScriptEvaluator._check_syntax(script_path)
        
        # 2. Complexity (lower is better, inverted)
        scores["complexity"] = 1.0 - ScriptEvaluator._check_complexity(script_path)
        
        # 3. Documentation coverage
        scores["docs"] = ScriptEvaluator._check_documentation(script_path)
        
        # 4. Error handling coverage
        scores["errors"] = ScriptEvaluator._check_error_handling(script_path)
        
        # Weighted total
        weights = {"syntax": 0.3, "complexity": 0.2, "docs": 0.2, "errors": 0.3}
        total = sum(scores[k] * weights[k] for k in scores)
        scores["total"] = total
        
        return scores
    
    @staticmethod
    def _check_syntax(script_path: Path) -> float:
        """Check if script has valid Python syntax."""
        try:
            with open(script_path) as f:
                compile(f.read(), script_path.name, 'exec')
            return 1.0
        except SyntaxError:
            return 0.0
    
    @staticmethod
    def _check_complexity(script_path: Path) -> float:
        """Estimate complexity (0-1, higher = more complex)."""
        with open(script_path) as f:
            content = f.read()
        
        lines = len(content.split('\n'))
        functions = content.count('def ')
        classes = content.count('class ')
        branches = content.count('if ') + content.count('for ') + content.count('while ')
        
        # Simple heuristic
        score = min((lines / 200) * 0.4 + (functions / 20) * 0.3 + (branches / 50) * 0.3, 1.0)
        return score
    
    @staticmethod
    def _check_documentation(script_path: Path) -> float:
        """Check docstring coverage."""
        with open(script_path) as f:
            content = f.read()
        
        functions = content.count('def ')
        docstrings = content.count('"""') + content.count("'''")
        
        if functions == 0:
            return 1.0
        
        return min(docstrings / (functions * 2), 1.0)  # *2 because docstrings are pairs
    
    @staticmethod
    def _check_error_handling(script_path: Path) -> float:
        """Check try/except coverage."""
        with open(script_path) as f:
            content = f.read()
        
        risky_ops = content.count('open(') + content.count('read()') + content.count('json.load')
        handlers = content.count('try:')
        
        if risky_ops == 0:
            return 1.0
        
        return min(handlers / risky_ops, 1.0)


def generate_mutation(script_path: Path, mutation_type: str) -> str:
    """Generate mutation description based on type."""
    mutations = {
        "rewrite": "Complete structural rewrite for clarity and modularity",
        "optimize": "Performance optimization for hot paths",
        "extend": "Add new capabilities while maintaining existing structure",
        "simplify": "Remove complexity, consolidate redundant logic"
    }
    return mutations.get(mutation_type, "General improvement")


def run_evolution_cycle(script_name: str = "autoDream", mode: str = "explore"):
    """Run one evolution cycle."""
    print(f"🧬 DGM Multi-Lineage Evolution for {script_name}")
    print(f"   Mode: {mode}")
    
    archive = LineageArchive(script_name)
    evaluator = ScriptEvaluator()
    
    if mode == "explore":
        # Sample existing lineage and mutate
        parent = archive.sample_lineage(strategy="diverse")
        if parent:
            mutation_type = random.choice(MUTATION_TYPES)
            print(f"   Selected lineage {parent['id']} (score: {parent['score']:.2f})")
            print(f"   Mutation type: {mutation_type}")
            
            # In real implementation, this would actually mutate the code
            # For now, record the intent
            new_version = f"v{len(archive.lineages) + 1}"
            child_id = archive.mutate_lineage(
                parent["id"], 
                new_version, 
                mutation_type
            )
            print(f"   Created child lineage: {child_id}")
            
            # Placeholder: would evaluate actual mutated script
            # score = evaluator.evaluate(mutated_path)["total"]
            # archive.update_score(child_id, score)
    
    elif mode == "evaluate":
        # Evaluate unevaluated lineages
        for lineage in archive.lineages:
            if "evaluated" not in lineage:
                print(f"   Evaluating {lineage['id']}...")
                # Placeholder score
                lineage["score"] = random.uniform(0.6, 0.95)
                lineage["evaluated"] = datetime.now().isoformat()
        
        archive._save_meta()
    
    elif mode == "archive":
        # Show archive status
        print(f"\n   Archive status: {len(archive.lineages)} lineages")
        for lineage in archive.lineages:
            score = lineage.get("score", 0)
            status = "✓" if "evaluated" in lineage else "○"
            print(f"   {status} {lineage['id']}: {lineage['version']} (score: {score:.2f})")
    
    print(f"\n💾 Archive: {archive.archive_dir}")
    return True


if __name__ == "__main__":
    import sys
    
    script_name = sys.argv[1] if len(sys.argv) > 1 else "autoDream"
    mode = sys.argv[2] if len(sys.argv) > 2 else "explore"
    
    run_evolution_cycle(script_name, mode)
