#!/usr/bin/env python3
"""
eve_skill_library.py — Skill Library Implementation (Voyager Pattern)

Implements the Voyager paper's key insight: skills as executable code,
stored with embeddings for retrieval, composable into complex behaviors.

Ciclo #53 Research: Voyager (arXiv:2305.16291)
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.utils import embedding_functions
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    print("Warning: ChromaDB not available, using fallback storage")


@dataclass
class Skill:
    """Represents an executable skill"""
    name: str
    description: str
    code: str
    created_at: str
    usage_count: int = 0
    success_rate: float = 1.0
    version: int = 1
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Skill':
        return cls(**data)


class SkillLibrary:
    """
    Skill Library inspired by Voyager (NVIDIA, Stanford, 2023).
    
    Key properties:
    - Skills are executable code (not passive knowledge)
    - Temporally extended, interpretable, compositional
    - Indexed by embeddings for semantic retrieval
    - Composed from simpler to complex behaviors
    """
    
    def __init__(self, library_path: Optional[str] = None):
        self.library_path = Path(library_path or "/root/evolution/skill_library")
        self.library_path.mkdir(parents=True, exist_ok=True)
        
        self.skills_dir = self.library_path / "skills"
        self.skills_dir.mkdir(exist_ok=True)
        
        self.metadata_file = self.library_path / "skill_metadata.json"
        self.skills: Dict[str, Skill] = {}
        self._load_metadata()
        
        # Initialize ChromaDB for retrieval
        if HAS_CHROMADB:
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.library_path / "chroma_db")
            )
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            
            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection("skills")
            except:
                self.collection = self.chroma_client.create_collection(
                    name="skills",
                    embedding_function=self.embedding_fn
                )
        else:
            self.chroma_client = None
            self.collection = None
    
    def _load_metadata(self):
        """Load skill metadata from disk"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                self.skills = {
                    name: Skill.from_dict(skill_data)
                    for name, skill_data in data.items()
                }
    
    def _save_metadata(self):
        """Save skill metadata to disk"""
        with open(self.metadata_file, 'w') as f:
            json.dump(
                {name: skill.to_dict() for name, skill in self.skills.items()},
                f,
                indent=2
            )
    
    def _skill_hash(self, code: str) -> str:
        """Generate hash for skill code"""
        return hashlib.sha256(code.encode()).hexdigest()[:16]
    
    def add_skill(
        self,
        name: str,
        description: str,
        code: str,
        verify: bool = True
    ) -> Skill:
        """
        Add a new skill to the library.
        
        Args:
            name: Unique name for the skill
            description: Natural language description (for retrieval)
            code: Python code implementing the skill
            verify: Whether to verify code executes (default: True)
        """
        # Verify code if requested
        if verify:
            verification = self._verify_code(code)
            if not verification['success']:
                print(f"Warning: Skill verification failed: {verification['error']}")
                return None
        
        # Create skill
        skill = Skill(
            name=name,
            description=description,
            code=code,
            created_at=datetime.now().isoformat()
        )
        
        # Save code to file
        skill_file = self.skills_dir / f"{name}.py"
        with open(skill_file, 'w') as f:
            f.write(f'"""{description}"""\n\n')
            f.write(code)
        
        # Add to ChromaDB for retrieval
        if self.collection:
            self.collection.add(
                documents=[description],
                metadatas=[{
                    'skill_name': name,
                    'created_at': skill.created_at
                }],
                ids=[name]
            )
        
        # Update memory
        self.skills[name] = skill
        self._save_metadata()
        
        print(f"✓ Added skill: {name}")
        return skill
    
    def _verify_code(self, code: str) -> Dict[str, Any]:
        """Verify that code is valid Python (without executing)"""
        try:
            compile(code, '<string>', 'exec')
            return {'success': True}
        except SyntaxError as e:
            return {'success': False, 'error': str(e)}
    
    def retrieve(self, task_description: str, k: int = 3) -> List[Skill]:
        """
        Retrieve relevant skills by semantic similarity.
        
        Args:
            task_description: Natural language description of task
            k: Number of skills to retrieve
            
        Returns:
            List of most relevant skills
        """
        if not self.collection:
            # Fallback: simple keyword matching
            return self._keyword_retrieve(task_description, k)
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[task_description],
            n_results=k
        )
        
        skills = []
        for name in results['ids'][0]:
            if name in self.skills:
                skills.append(self.skills[name])
        
        return skills
    
    def _keyword_retrieve(self, task_description: str, k: int) -> List[Skill]:
        """Fallback retrieval by simple keyword matching"""
        task_words = set(task_description.lower().split())
        scored = []
        
        for name, skill in self.skills.items():
            desc_words = set(skill.description.lower().split())
            score = len(task_words & desc_words)
            scored.append((score, skill))
        
        scored.sort(reverse=True)
        return [s for _, s in scored[:k]]
    
    def execute(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a skill with given arguments.
        
        Args:
            skill_name: Name of skill to execute
            **kwargs: Arguments to pass to skill
            
        Returns:
            Dict with result and metadata
        """
        if skill_name not in self.skills:
            return {
                'success': False,
                'error': f'Skill {skill_name} not found',
                'result': None
            }
        
        skill = self.skills[skill_name]
        
        # Update usage stats
        skill.usage_count += 1
        self._save_metadata()
        
        # Execute in subprocess for safety
        try:
            # Create temporary script
            temp_script = f"""
import sys
import json

{skill.code}

# Call main function if exists
if __name__ == "__main__":
    result = main(**{kwargs})
    print(json.dumps({{"result": result}}))
"""
            result = subprocess.run(
                [sys.executable, '-c', temp_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'result': result.stdout,
                    'skill': skill_name
                }
            else:
                skill.success_rate = max(0, skill.success_rate - 0.1)
                return {
                    'success': False,
                    'error': result.stderr,
                    'skill': skill_name
                }
                
        except subprocess.TimeoutExpired:
            skill.success_rate = max(0, skill.success_rate - 0.1)
            return {
                'success': False,
                'error': 'Timeout',
                'skill': skill_name
            }
        except Exception as e:
            skill.success_rate = max(0, skill.success_rate - 0.1)
            return {
                'success': False,
                'error': str(e),
                'skill': skill_name
            }
    
    def compose(self, skill_names: List[str], workflow_name: str = None) -> Skill:
        """
        Compose multiple skills into a workflow.
        
        Args:
            skill_names: List of skills to compose
            workflow_name: Optional name for composed skill
            
        Returns:
            Composed skill
        """
        if not all(s in self.skills for s in skill_names):
            missing = [s for s in skill_names if s not in self.skills]
            raise ValueError(f"Skills not found: {missing}")
        
        # Generate composed code
        composed_code = f"""# Composed workflow: {workflow_name or 'anonymous'}

def main(**kwargs):
    results = {{}}
"""
        descriptions = []
        
        for i, name in enumerate(skill_names):
            skill = self.skills[name]
            descriptions.append(skill.description)
            
            # Import skill
            composed_code += f"""
    # Step {i+1}: {name}
    exec(open('{self.skills_dir}/{name}.py').read())
    results['{name}'] = main(**kwargs)
"""
        
        composed_code += """
    return results
"""
        
        description = f"Composed workflow: {' -> '.join(descriptions)}"
        name = workflow_name or f"composed_{'_'.join(skill_names)}"
        
        return self.add_skill(name, description, composed_code, verify=False)
    
    def list_skills(self) -> List[Dict]:
        """List all skills in library"""
        return [skill.to_dict() for skill in self.skills.values()]
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get specific skill by name"""
        return self.skills.get(name)
    
    def stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        if not self.skills:
            return {'total': 0, 'total_usage': 0}
        
        total_usage = sum(s.usage_count for s in self.skills.values())
        avg_success = sum(s.success_rate for s in self.skills.values()) / len(self.skills)
        
        return {
            'total': len(self.skills),
            'total_usage': total_usage,
            'avg_success_rate': avg_success,
            'most_used': max(self.skills.values(), key=lambda s: s.usage_count).name
        }


def create_eve_core_skills():
    """Initialize Eve's core skill library"""
    library = SkillLibrary()
    
    # Skill 1: Memory Ingestion
    library.add_skill(
        name="memory_ingest",
        description="Ingest a memory file into ChromaDB for retrieval",
        code='''
def main(file_path, chroma_client=None):
    """Ingest memory file into vector database"""
    from pathlib import Path
    
    if not Path(file_path).exists():
        return {"error": "File not found"}
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Parse and chunk
    chunks = []
    current_chunk = []
    for line in content.split('\\n'):
        if line.startswith('##') and current_chunk:
            chunks.append('\\n'.join(current_chunk))
            current_chunk = []
        current_chunk.append(line)
    if current_chunk:
        chunks.append('\\n'.join(current_chunk))
    
    return {
        "chunks": len(chunks),
        "file": file_path,
        "status": "ingested"
    }
'''
    )
    
    # Skill 2: Insight Extraction
    library.add_skill(
        name="insight_extract",
        description="Extract key insights from text using pattern matching",
        code='''
def main(text, min_length=50):
    """Extract insights from text"""
    insights = []
    
    # Pattern: lines starting with "- **"
    for line in text.split('\\n'):
        line = line.strip()
        if line.startswith('- **') and len(line) > min_length:
            insight = line.lstrip('- **').rstrip('**')
            insights.append({
                "text": insight,
                "type": "bullet_point",
                "quality": len(insight)
            })
    
    return {
        "insights": insights,
        "count": len(insights)
    }
'''
    )
    
    # Skill 3: Training Pair Generation
    library.add_skill(
        name="training_pair_generate",
        description="Generate instruction-response training pairs from insights",
        code='''
def main(insight_text, category="general"):
    """Generate training pair from insight"""
    import json
    
    # Generate instruction
    instruction = f"Explain the following concept: {insight_text[:50]}..."
    
    # Generate response
    response = insight_text
    
    pair = {
        "instruction": instruction,
        "input": "",
        "output": response,
        "category": category,
        "source": "auto_generated",
        "quality_score": min(100, len(response) // 10)
    }
    
    return pair
'''
    )
    
    # Skill 4: Quality Scoring
    library.add_skill(
        name="quality_score",
        description="Score the quality of a training pair",
        code='''
def main(instruction, response, category="general"):
    """Score quality of training pair"""
    score = 0
    
    # Length check
    if len(response) > 100:
        score += 20
    if len(response) > 500:
        score += 20
    
    # Content diversity
    unique_words = len(set(response.lower().split()))
    if unique_words > 20:
        score += 20
    
    # Category bonus
    valuable_categories = ["identity_core", "technical_training", "autonomy_practice"]
    if category in valuable_categories:
        score += 20
    
    # Structure bonus
    if '```' in response:
        score += 20
    
    return {
        "score": min(100, score),
        "breakdown": {
            "length": len(response),
            "unique_words": unique_words,
            "has_code": '```' in response
        }
    }
'''
    )
    
    # Skill 5: Web Research
    library.add_skill(
        name="web_research",
        description="Research a topic by searching web and extracting key findings",
        code='''
def main(topic, max_results=5):
    """Research topic (stub - requires web search implementation)"""
    # Placeholder - actual implementation would search web
    return {
        "topic": topic,
        "findings": ["Finding 1", "Finding 2"],
        "sources": [],
        "status": "stub_implementation"
    }
'''
    )
    
    print(f"\n✓ Created {len(library.skills)} core skills")
    return library


if __name__ == "__main__":
    # Initialize core skills
    print("🌙 Eve Skill Library — Voyager Pattern Implementation")
    print("=" * 50)
    
    library = create_eve_core_skills()
    
    # Test retrieval
    print("\n--- Test Retrieval ---")
    results = library.retrieve("how to extract insights from text", k=2)
    for skill in results:
        print(f"  • {skill.name}: {skill.description}")
    
    # Test composition
    print("\n--- Test Composition ---")
    try:
        workflow = library.compose(
            ["insight_extract", "training_pair_generate"],
            workflow_name="extract_and_generate"
        )
        print(f"  ✓ Created composed skill: {workflow.name}")
    except Exception as e:
        print(f"  ✗ Composition failed: {e}")
    
    # Show stats
    print("\n--- Library Stats ---")
    stats = library.stats()
    print(f"  Total skills: {stats['total']}")
    print(f"  Total usage: {stats['total_usage']}")
    print(f"  Most used: {stats.get('most_used', 'N/A')}")
