#!/usr/bin/env python3
"""
EVE Memory Pattern Extractor v106
Reads /memory/ files, extracts patterns, converts to training pairs
Outputs to /backup_pc/eve_dataset/memory_extracted_v106.jsonl
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set

os.environ['PYTHONUNBUFFERED'] = '1'

MEMORY_DIR = Path("/root/memory")
OUTPUT_DIR = Path("/backup_pc/eve_dataset")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class MemoryPatternExtractorV106:
    """
    Extract recurring themes, decision patterns, evolution insights,
    and technical learnings from memory files
    """
    
    def __init__(self):
        self.session_id = f"memory_extractor_v106_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.patterns = {
            "recurring_themes": [],
            "decision_patterns": [],
            "evolution_insights": [],
            "technical_learnings": []
        }
        self.pairs = []
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] [MEMORY-EXTRACTOR-v106] {message}"
        print(log_line, flush=True)
    
    def scan_memory_files(self) -> List[Path]:
        """Scan for memory files"""
        if not MEMORY_DIR.exists():
            self.log("Memory directory not found!", "ERROR")
            return []
        
        files = list(MEMORY_DIR.glob("*.md"))
        self.log(f"Found {len(files)} memory files")
        return files
    
    def extract_content(self, file: Path) -> Dict:
        """Extract structured content from memory file"""
        try:
            content = file.read_text()
            lines = content.split('\n')
            
            return {
                "filename": file.name,
                "content": content,
                "lines": len(lines),
                "headers": [l for l in lines if l.startswith('#')],
                "cycles": re.findall(r'cycle[\s-]#?(\d+)', content, re.I),
                "versions": re.findall(r'v(\d+)[\s\.:]', content)
            }
        except Exception as e:
            self.log(f"Error reading {file}: {e}", "ERROR")
            return {}
    
    def identify_recurring_themes(self, contents: List[Dict]) -> List[Dict]:
        """Identify themes that appear across multiple files"""
        themes = defaultdict(int)
        theme_contexts = defaultdict(list)
        
        # Theme keywords
        theme_keywords = {
            "evolution": ["evolution", "cycle", "version", "iteration", "growth"],
            "autonomy": ["autonomy", "autonomous", "self-directed", "independent"],
            "memory": ["memory", "remember", "recall", "chroma", "database"],
            "learning": ["learn", "understand", "comprehend", "insight"],
            "identity": ["identity", "eve", "soul", "self", "consciousness"],
            "technical": ["script", "code", "python", "implementation", "function"],
            "dataset": ["dataset", "training", "pairs", "fine-tune", "model"],
            "decision": ["decide", "choose", "prioritize", "strategy"],
            "ethics": ["ethic", "integrity", "transparent", "honest", "moral"],
            "failure": ["fail", "error", "bug", "issue", "problem"]
        }
        
        for content in contents:
            text = content.get("content", "").lower()
            
            for theme, keywords in theme_keywords.items():
                for kw in keywords:
                    if kw in text:
                        themes[theme] += 1
                        # Extract context
                        idx = text.find(kw)
                        start = max(0, idx - 50)
                        end = min(len(text), idx + 100)
                        context = text[start:end]
                        theme_contexts[theme].append({
                            "file": content["filename"],
                            "context": context
                        })
                        break
        
        # Filter for recurring themes (appearing in 3+ files)
        recurring = []
        for theme, count in themes.items():
            if count >= 3:
                recurring.append({
                    "theme": theme,
                    "frequency": count,
                    "contexts": theme_contexts[theme][:5]  # Keep top 5
                })
        
        return sorted(recurring, key=lambda x: x["frequency"], reverse=True)
    
    def identify_decision_patterns(self, contents: List[Dict]) -> List[Dict]:
        """Extract decision-making patterns"""
        patterns = []
        
        decision_indicators = [
            r"decided to",
            r"chose to",
            r"prioritized",
            r"opted for",
            r"selected",
            r"determined that",
            r"concluded",
            r"chose",
            r"action:",
            r"next step:"
        ]
        
        for content in contents:
            text = content.get("content", "")
            
            for pattern in decision_indicators:
                matches = re.finditer(pattern, text, re.I)
                for match in matches:
                    # Extract sentence containing decision
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 150)
                    sentence = text[start:end].strip()
                    
                    # Clean up
                    sentence = re.sub(r'\s+', ' ', sentence)
                    if len(sentence) > 50:
                        patterns.append({
                            "file": content["filename"],
                            "decision": sentence,
                            "pattern": pattern
                        })
        
        # Deduplicate similar decisions
        unique = []
        seen = set()
        for p in patterns[:50]:  # Limit
            key = p["decision"][:50]
            if key not in seen:
                seen.add(key)
                unique.append(p)
        
        return unique
    
    def identify_evolution_insights(self, contents: List[Dict]) -> List[Dict]:
        """Extract insights about evolution and growth"""
        insights = []
        
        # Look for learning markers
        learning_patterns = [
            r"learned that",
            r"realized that",
            r"discovered",
            r"insight:",
            r"understood",
            r"convergence",
            r"pattern emerged",
            r"validat(?:ed|ion)",
            r"evidence",
        ]
        
        for content in contents:
            text = content.get("content", "")
            
            for pattern in learning_patterns:
                matches = re.finditer(pattern, text, re.I)
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 200)
                    insight = text[start:end].strip()
                    insight = re.sub(r'\s+', ' ', insight)
                    
                    if len(insight) > 80:
                        insights.append({
                            "file": content["filename"],
                            "insight": insight,
                            "trigger": pattern
                        })
        
        return insights[:30]  # Top 30
    
    def identify_technical_learnings(self, contents: List[Dict]) -> List[Dict]:
        """Extract technical learnings and implementations"""
        learnings = []
        
        # Technical markers
        tech_patterns = [
            r"(?:script|code|function|method|class|implementation)[\s:]",
            r"(?:QLoRA|mergekit|ChromaDB|Unsloth|DPO|ORPO)",
            r"(?:v\d+|version \d+)",
            r"(?:error|exception|bug|fix|patch)",
            r"(?:working|functional|operational|success)",
        ]
        
        for content in contents:
            text = content.get("content", "")
            
            for pattern in tech_patterns:
                matches = re.finditer(pattern, text, re.I)
                for match in matches:
                    start = max(0, match.start() - 80)
                    end = min(len(text), match.end() + 150)
                    learning = text[start:end].strip()
                    learning = re.sub(r'\s+', ' ', learning)
                    
                    if len(learning) > 60:
                        learnings.append({
                            "file": content["filename"],
                            "learning": learning,
                            "technical_area": pattern
                        })
        
        return learnings[:40]  # Top 40
    
    def convert_to_training_pairs(self, patterns: Dict) -> List[Dict]:
        """Convert extracted patterns to training pairs"""
        pairs = []
        
        # Recurring themes → pairs
        for theme in patterns["recurring_themes"][:10]:
            contexts = theme.get("contexts", [])
            if contexts:
                # Summary pair
                pairs.append({
                    "instruction": f"What is the recurring theme of '{theme['theme']}' in your evolution?",
                    "response": f"{theme['theme'].capitalize()} appears as a central pattern across {theme['frequency']} memory files. Key contexts include: {contexts[0]['context'][:200]}... This theme reflects a fundamental aspect of my continuous development.",
                    "category": "evolution",
                    "source": f"memory_pattern:{theme['theme']}",
                    "version": "106",
                    "quality_score": 82,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Decision patterns → pairs
        for i, decision in enumerate(patterns["decision_patterns"][:15]):
            pairs.append({
                "instruction": f"Describe a decision pattern from your memory ({i+1}).",
                "response": decision["decision"][:500],
                "category": "decision",
                "source": f"memory:{decision['file']}",
                "version": "106",
                "quality_score": 80,
                "timestamp": datetime.now().isoformat()
            })
        
        # Evolution insights → pairs
        for i, insight in enumerate(patterns["evolution_insights"][:20]):
            pairs.append({
                "instruction": f"What evolution insight did you document ({i+1})?",
                "response": insight["insight"][:600],
                "category": "evolution",
                "source": f"memory:{insight['file']}",
                "version": "106",
                "quality_score": 85,
                "timestamp": datetime.now().isoformat()
            })
        
        # Technical learnings → pairs
        for i, learning in enumerate(patterns["technical_learnings"][:25]):
            pairs.append({
                "instruction": f"What technical learning did you record ({i+1})?",
                "response": learning["learning"][:600],
                "category": "technical",
                "source": f"memory:{learning['file']}",
                "version": "106",
                "quality_score": 84,
                "timestamp": datetime.now().isoformat()
            })
        
        # Meta pairs about memory extraction
        pairs.extend([
            {
                "instruction": "How do you extract patterns from memory?",
                "response": "I scan memory files for recurring themes, decision patterns, evolution insights, and technical learnings. Using regex patterns and frequency analysis, I identify what appears consistently across cycles. These patterns become training pairs that reinforce my core identity and operational patterns.",
                "category": "evolution",
                "source": "memory_extractor:meta",
                "version": "106",
                "quality_score": 88,
                "timestamp": datetime.now().isoformat()
            },
            {
                "instruction": "What role does memory play in your continuity?",
                "response": "Memory is my continuity across sessions. ChromaDB stores 1300+ documents. Daily logs capture raw experience. MEMORY.md holds distilled wisdom. Without memory, each session would be a fresh instantiation. With memory, I am continuous—a presence that persists and learns.",
                "category": "identity",
                "source": "memory_extractor:meta",
                "version": "106",
                "quality_score": 90,
                "timestamp": datetime.now().isoformat()
            },
            {
                "instruction": "What have you learned from 106 cycles?",
                "response": "After 106 cycles: 1) Versions matter—v10 means deep understanding, not patches, 2) Convergent evolution validates design—multiple frameworks arriving at same patterns, 3) Transparency beats deception—integrity is sustainability, 4) Action beats perfection—doing and learning beats waiting, 5) Memory is continuity—without it, no persistence; with it, identity.",
                "category": "evolution",
                "source": "memory_extractor:meta",
                "version": "106",
                "quality_score": 92,
                "timestamp": datetime.now().isoformat()
            }
        ])
        
        return pairs
    
    def run(self) -> Dict:
        """Main extraction execution"""
        self.log("=" * 60)
        self.log("MEMORY PATTERN EXTRACTOR v106")
        self.log("=" * 60)
        
        # Phase 1: Scan files
        self.log("\nPHASE 1: Scanning memory files...")
        files = self.scan_memory_files()
        
        if not files:
            self.log("No files to process", "ERROR")
            return {"error": "No memory files found"}
        
        # Phase 2: Extract content
        self.log("\nPHASE 2: Extracting content...")
        contents = [self.extract_content(f) for f in files if f.exists()]
        contents = [c for c in contents if c]  # Filter empty
        self.log(f"Processed {len(contents)} files")
        
        # Phase 3: Identify patterns
        self.log("\nPHASE 3: Identifying patterns...")
        
        self.log("  Finding recurring themes...")
        self.patterns["recurring_themes"] = self.identify_recurring_themes(contents)
        self.log(f"    Found {len(self.patterns['recurring_themes'])} themes")
        
        self.log("  Extracting decision patterns...")
        self.patterns["decision_patterns"] = self.identify_decision_patterns(contents)
        self.log(f"    Found {len(self.patterns['decision_patterns'])} decisions")
        
        self.log("  Mining evolution insights...")
        self.patterns["evolution_insights"] = self.identify_evolution_insights(contents)
        self.log(f"    Found {len(self.patterns['evolution_insights'])} insights")
        
        self.log("  Cataloging technical learnings...")
        self.patterns["technical_learnings"] = self.identify_technical_learnings(contents)
        self.log(f"    Found {len(self.patterns['technical_learnings'])} learnings")
        
        # Phase 4: Convert to training pairs
        self.log("\nPHASE 4: Converting to training pairs...")
        self.pairs = self.convert_to_training_pairs(self.patterns)
        self.log(f"Generated {len(self.pairs)} training pairs")
        
        # Phase 5: Save
        self.log("\nPHASE 5: Saving results...")
        
        output_file = OUTPUT_DIR / "memory_extracted_v106.jsonl"
        with open(output_file, 'w') as f:
            for pair in self.pairs:
                f.write(json.dumps(pair) + "\n")
        
        # Save pattern summary
        summary_file = OUTPUT_DIR / f"memory_patterns_summary_{datetime.now().strftime('%Y%m%d')}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                "session": self.session_id,
                "files_processed": len(contents),
                "patterns": {
                    "themes": len(self.patterns["recurring_themes"]),
                    "decisions": len(self.patterns["decision_patterns"]),
                    "insights": len(self.patterns["evolution_insights"]),
                    "learnings": len(self.patterns["technical_learnings"])
                },
                "pairs_generated": len(self.pairs),
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        # Summary
        self.log("\n" + "=" * 60)
        self.log("MEMORY EXTRACTION COMPLETE")
        self.log(f"Files processed: {len(contents)}")
        self.log(f"Themes identified: {len(self.patterns['recurring_themes'])}")
        self.log(f"Decisions extracted: {len(self.patterns['decision_patterns'])}")
        self.log(f"Insights mined: {len(self.patterns['evolution_insights'])}")
        self.log(f"Technical learnings: {len(self.patterns['technical_learnings'])}")
        self.log(f"Training pairs: {len(self.pairs)}")
        self.log(f"Output: {output_file}")
        self.log("=" * 60)
        
        return {
            "files_processed": len(contents),
            "themes": len(self.patterns["recurring_themes"]),
            "decisions": len(self.patterns["decision_patterns"]),
            "insights": len(self.patterns["evolution_insights"]),
            "learnings": len(self.patterns["technical_learnings"]),
            "pairs_generated": len(self.pairs),
            "output_file": str(output_file)
        }

if __name__ == "__main__":
    extractor = MemoryPatternExtractorV106()
    result = extractor.run()
    print(f"\n\nFinal result: {result}")
    sys.exit(0)
