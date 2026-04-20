#!/usr/bin/env python3
"""
eve_epistemic_tagger.py — Epistemic Classification for CACM Architecture

Baseado em: OIDA (arXiv:2604.11759) — Epistemic Infrastructure for Organizational AI
Integra com: CACM 3-Channel Memory (arXiv:2604.09308)

Purpose: Classify insights by epistemic class with confidence scoring and decay tracking.

Epistemic Classes:
- fact: Verified, confirmed, stable knowledge
- hypothesis: Theory under test, needs validation
- question: Explicit uncertainty, knowledge gap
- contradiction: Conflict with previous knowledge
- deprecated: Obsolete, superseded

Author: Eve 🌙 | Cycle #70 | 2026-04-14
"""

import json
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import chromadb
from chromadb.config import Settings

# Epistemic class definitions with decay half-lives (in days)
EPHEMERIC_CLASSES = {
    "fact": {
        "description": "Verified, confirmed, stable knowledge",
        "decay_half_life_days": 365,  # Facts decay slowly (1 year)
        "confidence_threshold": 0.85,
        "color": "🟢"
    },
    "hypothesis": {
        "description": "Theory under test, needs validation",
        "decay_half_life_days": 30,  # Hypotheses decay faster (1 month)
        "confidence_threshold": 0.60,
        "color": "🟡"
    },
    "question": {
        "description": "Explicit uncertainty, knowledge gap",
        "decay_half_life_days": -7,  # Inverse decay: urgency increases over time
        "confidence_threshold": 0.0,  # Questions have no confidence (they're gaps)
        "color": "❓"
    },
    "contradiction": {
        "description": "Conflict with previous knowledge",
        "decay_half_life_days": 14,  # Contradictions need resolution (2 weeks)
        "confidence_threshold": 0.70,
        "color": "🔴"
    },
    "deprecated": {
        "description": "Obsolete, superseded knowledge",
        "decay_half_life_days": 1,  # Deprecated decays very fast
        "confidence_threshold": 0.0,
        "color": "⚫"
    }
}


@dataclass
class EpistemicTag:
    """Represents an epistemic classification for a knowledge item."""
    content_hash: str
    epistemic_class: str
    confidence: float  # 0-100
    created_at: datetime
    last_validated: Optional[datetime] = None
    contradiction_with: Optional[str] = None  # hash of conflicting content
    source: str = "auto"  # auto, manual, inference
    
    def to_dict(self) -> Dict:
        return {
            "content_hash": self.content_hash,
            "epistemic_class": self.epistemic_class,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
            "contradiction_with": self.contradiction_with,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EpistemicTag":
        return cls(
            content_hash=data["content_hash"],
            epistemic_class=data["epistemic_class"],
            confidence=data["confidence"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_validated=datetime.fromisoformat(data["last_validated"]) if data["last_validated"] else None,
            contradiction_with=data["contradiction_with"],
            source=data["source"]
        )
    
    def calculate_urgency(self) -> float:
        """Calculate urgency score based on epistemic class and age."""
        age_days = (datetime.now() - self.created_at).days
        half_life = EPHEMERIC_CLASSES[self.epistemic_class]["decay_half_life_days"]
        
        if half_life < 0:  # Inverse decay (questions gain urgency)
            return min(1.0, abs(age_days / half_life))
        else:  # Normal decay
            return max(0.1, 0.5 ** (age_days / half_life))
    
    def needs_attention(self) -> bool:
        """Check if this item needs attention based on urgency."""
        urgency = self.calculate_urgency()
        
        if self.epistemic_class == "question":
            return urgency > 0.3  # Questions become urgent
        elif self.epistemic_class == "contradiction":
            return urgency > 0.5  # Contradictions need resolution
        elif self.epistemic_class == "hypothesis":
            return urgency > 0.4  # Hypotheses need validation
        return False


class EpistemicTagger:
    """Main class for epistemic classification and management."""
    
    def __init__(self, memory_root: str = "/memory"):
        self.memory_root = Path(memory_root)
        self.tags_path = self.memory_root / "corrective" / "epistemic_tags.jsonl"
        self.tags_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB for contradiction detection
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.memory_root / ".chroma_epistemic"),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="epistemic_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
        
        self._load_tags()
    
    def _load_tags(self) -> None:
        """Load existing tags from disk."""
        self.tags: Dict[str, EpistemicTag] = {}
        if self.tags_path.exists():
            with open(self.tags_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            tag = EpistemicTag.from_dict(json.loads(line))
                            self.tags[tag.content_hash] = tag
                        except json.JSONDecodeError:
                            continue
    
    def _save_tags(self) -> None:
        """Save all tags to disk."""
        with open(self.tags_path, 'w') as f:
            for tag in self.tags.values():
                f.write(json.dumps(tag.to_dict()) + '\n')
    
    def _hash_content(self, content: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _auto_classify(self, content: str) -> Tuple[str, float]:
        """
        Auto-classify content based on linguistic patterns.
        Returns (epistemic_class, confidence).
        """
        content_lower = content.lower()
        
        # Pattern matching for classification
        patterns = {
            "question": [
                r"\b(não sei|não sabemos|incerto|desconhecido|gap|falta|missing)\b",
                r"\b(pergunta|question|how to|what if|why does)\b",
                r"\b(não implementado|pendente|futuro|TODO|FIXME)\b"
            ],
            "hypothesis": [
                r"\b(pode ser|talvez|provavelmente|hypothesis|acredito|suspeito)\b",
                r"\b(testar|validar|verificar|experimentar|pilot)\b",
                r"\b(assumindo|assumption|se X então|if true)\b"
            ],
            "contradiction": [
                r"\b(contradição|contradict|inconsistent|diverge|conflito)\b",
                r"\b(não alinha|diferente de|oposto a|vs|versus)\b",
                r"\b(antes dizia|previously|old version|deprecated)\b"
            ],
            "deprecated": [
                r"\b(obsoleto|deprecated|legado|legacy|old way|não usar)\b",
                r"\b(replaced by|substituído|superseded|removed)\b"
            ],
            "fact": [
                r"\b(é verdade|confirmado|verificado|estável|proven)\b",
                r"\b(implementado|funciona|testado|deployed|working)\b",
                r"\b(dado que|given that|since|because [^I])\b"
            ]
        }
        
        scores = {}
        for cls, regexes in patterns.items():
            score = 0
            for pattern in regexes:
                matches = len(re.findall(pattern, content_lower))
                score += matches * (2 if cls in ["question", "contradiction"] else 1)
            scores[cls] = score
        
        # Select class with highest score
        if max(scores.values()) == 0:
            return "hypothesis", 50.0  # Default to hypothesis if uncertain
        
        best_class = max(scores, key=scores.get)
        confidence = min(95, 50 + scores[best_class] * 15)
        
        return best_class, confidence
    
    def tag_content(self, content: str, source: str = "auto", 
                    manual_class: Optional[str] = None,
                    manual_confidence: Optional[float] = None) -> EpistemicTag:
        """
        Tag content with epistemic classification.
        
        Args:
            content: The knowledge content to tag
            source: "auto", "manual", or "inference"
            manual_class: Override auto-classification
            manual_confidence: Override auto-confidence
        
        Returns:
            EpistemicTag with classification
        """
        content_hash = self._hash_content(content)
        
        # Check for contradictions with existing knowledge
        contradiction_with = None
        if len(content) > 50:  # Only check substantial content
            try:
                results = self.collection.query(
                    query_texts=[content],
                    n_results=3
                )
                if results["distances"] and results["distances"][0]:
                    for i, distance in enumerate(results["distances"][0]):
                        if distance < 0.15:  # Very similar but not identical
                            # Potential contradiction detected
                            existing_hash = results["ids"][0][i]
                            if existing_hash in self.tags:
                                existing_class = self.tags[existing_hash].epistemic_class
                                if existing_class == "fact":
                                    contradiction_with = existing_hash
                                    break
            except Exception:
                pass  # ChromaDB may be empty
        
        # Determine class and confidence
        if manual_class:
            epistemic_class = manual_class
            confidence = manual_confidence or 90.0
        else:
            epistemic_class, confidence = self._auto_classify(content)
        
        # Override if contradiction detected
        if contradiction_with and epistemic_class == "fact":
            epistemic_class = "contradiction"
            confidence = max(confidence, 75.0)
        
        # Create tag
        tag = EpistemicTag(
            content_hash=content_hash,
            epistemic_class=epistemic_class,
            confidence=confidence,
            created_at=datetime.now(),
            contradiction_with=contradiction_with,
            source=source
        )
        
        # Store in ChromaDB for future contradiction detection
        try:
            self.collection.add(
                ids=[content_hash],
                documents=[content],
                metadatas=[{"class": epistemic_class, "confidence": confidence}]
            )
        except Exception as e:
            # May already exist
            pass
        
        # Save tag
        self.tags[content_hash] = tag
        self._save_tags()
        
        return tag
    
    def get_tag(self, content_hash: str) -> Optional[EpistemicTag]:
        """Retrieve tag by content hash."""
        return self.tags.get(content_hash)
    
    def get_all_by_class(self, epistemic_class: str) -> List[EpistemicTag]:
        """Get all tags of a specific epistemic class."""
        return [tag for tag in self.tags.values() if tag.epistemic_class == epistemic_class]
    
    def get_questions_needing_answers(self, urgency_threshold: float = 0.3) -> List[EpistemicTag]:
        """Get questions that have become urgent (inverse decay)."""
        questions = self.get_all_by_class("question")
        return [q for q in questions if q.calculate_urgency() >= urgency_threshold]
    
    def get_contradictions_needing_resolution(self) -> List[EpistemicTag]:
        """Get unresolved contradictions."""
        contradictions = self.get_all_by_class("contradiction")
        return [c for c in contradictions if c.contradiction_with and c.needs_attention()]
    
    def validate_hypothesis(self, content_hash: str, validated: bool) -> None:
        """
        Mark a hypothesis as validated or invalidated.
        
        Args:
            content_hash: Hash of the hypothesis
            validated: True if validated (promotes to fact), False if invalidated (deprecates)
        """
        if content_hash not in self.tags:
            return
        
        tag = self.tags[content_hash]
        if tag.epistemic_class != "hypothesis":
            return
        
        if validated:
            tag.epistemic_class = "fact"
            tag.confidence = min(95, tag.confidence + 20)
        else:
            tag.epistemic_class = "deprecated"
            tag.confidence = 0
        
        tag.last_validated = datetime.now()
        self._save_tags()
    
    def generate_epistemic_report(self) -> Dict:
        """Generate summary report of epistemic state."""
        report = {
            "total_tagged": len(self.tags),
            "by_class": {},
            "needing_attention": [],
            "questions_urgent": [],
            "contradictions_unresolved": []
        }
        
        for cls in EPHEMERIC_CLASSES.keys():
            tags = self.get_all_by_class(cls)
            report["by_class"][cls] = {
                "count": len(tags),
                "avg_confidence": sum(t.confidence for t in tags) / len(tags) if tags else 0,
                "avg_urgency": sum(t.calculate_urgency() for t in tags) / len(tags) if tags else 0
            }
        
        # Find items needing attention
        for tag in self.tags.values():
            if tag.needs_attention():
                report["needing_attention"].append({
                    "hash": tag.content_hash,
                    "class": tag.epistemic_class,
                    "urgency": tag.calculate_urgency(),
                    "confidence": tag.confidence
                })
        
        report["questions_urgent"] = [
            {"hash": q.content_hash, "urgency": q.calculate_urgency()}
            for q in self.get_questions_needing_answers()
        ]
        
        report["contradictions_unresolved"] = [
            {"hash": c.content_hash, "contradicts": c.contradiction_with}
            for c in self.get_contradictions_needing_resolution()
        ]
        
        return report


def main():
    """CLI interface for epistemic tagging."""
    import sys
    
    tagger = EpistemicTagger()
    
    if len(sys.argv) < 2:
        print("Usage: python eve_epistemic_tagger.py <command> [args]")
        print("\nCommands:")
        print("  tag <content> [class] [confidence]  — Tag new content")
        print("  get <hash>                          — Get tag by hash")
        print("  list <class>                        — List all tags of class")
        print("  questions                           — Show urgent questions")
        print("  contradictions                      — Show unresolved contradictions")
        print("  validate <hash> <true|false>        — Validate hypothesis")
        print("  report                              — Generate epistemic report")
        return
    
    command = sys.argv[1]
    
    if command == "tag":
        content = sys.argv[2]
        manual_class = sys.argv[3] if len(sys.argv) > 3 else None
        manual_confidence = float(sys.argv[4]) if len(sys.argv) > 4 else None
        
        tag = tagger.tag_content(content, manual_class=manual_class, manual_confidence=manual_confidence)
        print(f"{EPHEMERIC_CLASSES[tag.epistemic_class]['color']} Tagged as {tag.epistemic_class}")
        print(f"   Confidence: {tag.confidence:.1f}%")
        print(f"   Hash: {tag.content_hash}")
        print(f"   Urgency: {tag.calculate_urgency():.2f}")
        if tag.contradiction_with:
            print(f"   ⚠️  Contradiction detected with: {tag.contradiction_with}")
    
    elif command == "get":
        tag = tagger.get_tag(sys.argv[2])
        if tag:
            print(json.dumps(tag.to_dict(), indent=2))
        else:
            print("Tag not found")
    
    elif command == "list":
        tags = tagger.get_all_by_class(sys.argv[2])
        for tag in tags:
            cls_info = EPHEMERIC_CLASSES[tag.epistemic_class]
            print(f"{cls_info['color']} {tag.content_hash[:8]}... | {tag.epistemic_class} | {tag.confidence:.0f}% | urgency={tag.calculate_urgency():.2f}")
    
    elif command == "questions":
        questions = tagger.get_questions_needing_answers()
        print(f"❓ {len(questions)} urgent questions:")
        for q in questions:
            print(f"   {q.content_hash[:8]}... (urgency: {q.calculate_urgency():.2f})")
    
    elif command == "contradictions":
        contradictions = tagger.get_contradictions_needing_resolution()
        print(f"🔴 {len(contradictions)} unresolved contradictions:")
        for c in contradictions:
            print(f"   {c.content_hash[:8]}... contradicts {c.contradiction_with[:8]}...")
    
    elif command == "validate":
        tagger.validate_hypothesis(sys.argv[2], sys.argv[3].lower() == "true")
        print(f"Hypothesis {sys.argv[2][:8]}... {'validated' if sys.argv[3].lower() == 'true' else 'invalidated'}")
    
    elif command == "report":
        report = tagger.generate_epistemic_report()
        print(json.dumps(report, indent=2))
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
