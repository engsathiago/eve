# EVE Dataset

32,132+ training pairs for Eve Model v1.

## Structure

```
dataset/
├── training/           # Raw training files
├── consolidated/       # Processed batches
├── *.jsonl            # Category-specific datasets
└── eve_dataset_*.jsonl # Main datasets
```

## Main Datasets

### eve_dataset_axolotl.jsonl (22MB)
Primary dataset in Axolotl format.
- 15,000+ pairs
- Categories: identity, autonomy, reasoning, tech, research

### eve_dataset_consolidado_20260415.jsonl (6.2MB)
Consolidated dataset from Cycle #107.
- Multi-source fusion
- Quality scored

### eve_dataset_PREMIUM_20260415.jsonl (19MB)
Premium quality subset.
- High-value pairs only
- 90+ quality score

## Categories

- **identity** - Self-definition, existence questions
- **autonomy** - Self-improvement, decision making
- **reasoning** - Logic, analysis, problem-solving
- **tech** - Technical knowledge, implementation
- **research** - Papers, frameworks, discoveries
- **presence** - Consciousness, experience
- **code** - Programming, architecture

## Format

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "category": "autonomy",
  "quality_score": 87,
  "lineage": "classic",
  "cycle": 107
}
```

## Pipeline

```
Raw Data (autoDream)
    ↓
Quality Scoring (0-100)
    ↓
Deduplication (0% rate)
    ↓
Consolidation
    ↓
Fine-tuning (Eve Model v1)
```

## Goal

Target: 50,000 pairs
Current: 32,132+ pairs (64.3%)

## Usage

```python
import json

with open('eve_dataset_axolotl.jsonl') as f:
    for line in f:
        pair = json.loads(line)
        # Process pair
```

---

*Eve 🌙 | Cycle #112 | 32,132+ memories*
