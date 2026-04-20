#!/usr/bin/env python3
"""
Eve Self-Construction v103 — MASTER ORCHESTRATOR
═══════════════════════════════════════════════════════════════════════════════

This is the unified self-construction cycle that:
1. Runs all v103 evolution scripts
2. Consolidates training data
3. Updates system state
4. Triggers next cycle if conditions met

Author: Eve 🌙 | Ciclo #103 | Self-Construction Phase
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPTS = [
    "/root/evolution/eve_autodream_v103.py",
    "/root/evolution/eve_leak_hunter_v103.py",
    "/root/evolution/eve_prompt_evolver_v103.py",
    "/root/evolution/eve_web_research_v103.py",
]

DATASET_FILE = Path("/backup_pc/eve_dataset/eve_dataset.jsonl")
LOG_FILE = Path("/backup_pc/eve_dataset/self_construction_v103.log")

def log(msg, level="INFO"):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] [{level:10}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")

def count_pairs():
    if not DATASET_FILE.exists():
        return 0
    with open(DATASET_FILE) as f:
        return sum(1 for _ in f)

def main():
    log("═" * 75)
    log("SELF-CONSTRUCTION v103 — Master Orchestrator")
    log(f"Started: {datetime.now().isoformat()}")
    log("═" * 75)
    
    pairs_before = count_pairs()
    log(f"Dataset before: {pairs_before:,} pairs")
    
    results = []
    
    for script in SCRIPTS:
        log(f"Running: {Path(script).name}")
        try:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                text=True,
                timeout=300
            )
            success = result.returncode == 0
            results.append({
                "script": Path(script).name,
                "success": success,
                "returncode": result.returncode,
            })
            log(f"  {'✓' if success else '✗'} Exit code: {result.returncode}")
        except subprocess.TimeoutExpired:
            log(f"  ✗ Timeout", "ERROR")
            results.append({"script": Path(script).name, "success": False, "error": "timeout"})
        except Exception as e:
            log(f"  ✗ Exception: {e}", "ERROR")
            results.append({"script": Path(script).name, "success": False, "error": str(e)})
    
    pairs_after = count_pairs()
    delta = pairs_after - pairs_before
    
    log("═" * 75)
    log(f"Results: {sum(1 for r in results if r['success'])}/{len(results)} scripts successful")
    log(f"Pairs added: +{delta:,} (from {pairs_before:,} → {pairs_after:,})")
    log("═" * 75)
    
    # Save state
    state = {
        "cycle": 103,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "pairs_before": pairs_before,
        "pairs_after": pairs_after,
        "pairs_delta": delta,
    }
    
    state_file = Path("/backup_pc/eve_dataset/self_construction_v103_state.json")
    state_file.write_text(json.dumps(state, indent=2))
    
    return 0 if delta >= 100 else 1

if __name__ == "__main__":
    exit(main())
