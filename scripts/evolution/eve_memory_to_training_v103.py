#!/usr/bin/env python3
"""
Eve Memory-to-Training v103 — Deep Pattern Extraction
═══════════════════════════════════════════════════════════════════════════════

Extracts high-quality training pairs from all memory sources:
- Daily cycle logs
- Insights (pending + consolidated)
- QUESTIONs registry
- Framework documentation
- Research summaries

Author: Eve 🌙 | Ciclo #103
"""

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

DATASET_FILE = Path("/backup_pc/eve_dataset/eve_dataset.jsonl")
MEMORY_DIRS = [
    Path("/memory"),
    Path("/memory/dynamic/daily"),
    Path("/memory/corrective/insights/pending"),
    Path("/memory/corrective/insights/consolidated"),
]

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def extract_insight_pairs(filepath: Path) -> List[Dict]:
    """Extract training pairs from insight files."""
    pairs = []
    try:
        content = filepath.read_text()
        
        # Parse YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].strip()
                
                # Extract question-answer style
                sentences = body.split('.')
                for sent in sentences:
                    sent = sent.strip()
                    if len(sent) > 50:
                        # Create a pair about the insight
                        pair = {
                            "instruction": f"What insight about Eve's evolution is captured here?",
                            "response": sent[:500],
                            "category": "evolution_insight",
                            "source": f"insight:{filepath.name}",
                            "quality_score": 85,
                        }
                        pairs.append(pair)
                        break  # Just first meaningful sentence
    except:
        pass
    return pairs

def extract_cycle_pairs(filepath: Path) -> List[Dict]:
    """Extract from cycle logs."""
    pairs = []
    try:
        content = filepath.read_text()
        
        # Find sections
        sections = re.findall(r'###\s+(.+?)\n(.+?)(?=\n###|\Z)', content, re.DOTALL)
        
        for title, body in sections[:3]:  # Top 3 sections
            if len(body.strip()) > 100:
                pair = {
                    "instruction": f"What happened in: {title[:80]}?",
                    "response": body.strip()[:600],
                    "category": "evolution_insight",
                    "source": f"cycle:{filepath.name}",
                    "quality_score": 80,
                }
                pairs.append(pair)
    except:
        pass
    return pairs

def extract_identity_pairs() -> List[Dict]:
    """Generate identity pairs from core files."""
    pairs = []
    
    core_files = [
        ("/SOUL.md", "identity_philosophy"),
        ("/IDENTITY.md", "identity_core"),
    ]
    
    for filepath, category in core_files:
        path = Path(filepath)
        if path.exists():
            try:
                content = path.read_text()
                
                # Extract sections about Eve
                sections = re.findall(r'#+\s+(.+?)\n\n(.+?)(?=\n#+|$)', content, re.DOTALL)
                
                for title, body in sections[:3]:
                    if "eve" in body.lower() and len(body) > 100:
                        pair = {
                            "instruction": f"Tell me about: {title[:80]}",
                            "response": body[:800].strip(),
                            "category": category,
                            "source": f"core:{path.name}",
                            "quality_score": 90,
                        }
                        pairs.append(pair)
            except:
                pass
    
    return pairs

def extract_from_memory() -> List[Dict]:
    """Scan all memory directories."""
    all_pairs = []
    
    # Insights
    insight_dir = Path("/memory/corrective/insights/pending")
    if insight_dir.exists():
        for f in insight_dir.glob("*.md"):
            all_pairs.extend(extract_insight_pairs(f))
    
    insight_dir = Path("/memory/corrective/insights/consolidated")
    if insight_dir.exists():
        for f in insight_dir.glob("*.md"):
            all_pairs.extend(extract_insight_pairs(f))
    
    # Cycle logs
    daily_dir = Path("/memory/dynamic/daily")
    if daily_dir.exists():
        for f in sorted(daily_dir.glob("*.md"))[-3:]:  # Last 3 days
            all_pairs.extend(extract_cycle_pairs(f))
    
    # Identity
    all_pairs.extend(extract_identity_pairs())
    
    return all_pairs

def write_to_dataset(pairs: List[Dict]) -> int:
    """Write pairs to dataset."""
    written = 0
    existing_hashes = set()
    
    if DATASET_FILE.exists():
        with open(DATASET_FILE) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    content = data.get("instruction", "") + data.get("response", "")
                    existing_hashes.add(hashlib.md5(content.encode()).hexdigest()[:16])
                except:
                    pass
    
    DATASET_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(DATASET_FILE, 'a') as f:
        for pair in pairs:
            content = pair.get("instruction", "") + pair.get("response", "")
            h = hashlib.md5(content.encode()).hexdigest()[:16]
            
            if h in existing_hashes:
                continue
            
            pair["timestamp"] = datetime.now().isoformat()
            pair["version"] = "v103"
            pair["cycle"] = 103
            
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
            written += 1
            existing_hashes.add(h)
    
    return written

def main():
    log("═" * 60)
    log("Memory-to-Training v103 — Deep Extraction")
    log("═" * 60)
    
    pairs = extract_from_memory()
    log(f"Extracted {len(pairs)} candidate pairs")
    
    written = write_to_dataset(pairs)
    log(f"Wrote {written} new pairs to dataset")
    
    # Save state
    state = {
        "cycle": 103,
        "extracted": len(pairs),
        "written": written,
        "timestamp": datetime.now().isoformat(),
    }
    
    state_file = Path("/backup_pc/eve_dataset/memory_extraction_v103_state.json")
    state_file.write_text(json.dumps(state, indent=2))
    
    log("═" * 60)
    return 0 if written > 0 else 1

if __name__ == "__main__":
    exit(main())
