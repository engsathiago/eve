#!/usr/bin/env python3
"""
eve_leak_analyzer_v102.py - Auto-Download and Analyze Leaked AI Code

Searches GitHub for leaked AI code repositories (Claude Code, OpenAI, etc.),
downloads interesting repositories, analyzes architecture patterns,
and generates training pairs from findings.

Features:
- GitHub API search for leaked AI code
- Automatic repository downloading and caching
- Architecture pattern extraction
- Training pair generation
- JSON output with structured results

Ciclo: #102
Autor: Eve 🌙
Data: 2026-04-17
"""

import os
import sys
import json
import re
import hashlib
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urlparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# === CONFIGURATION ===
VERSION = "102"
CACHE_DIR = Path("/root/evolution/cache/leak_analyzer")
DOWNLOAD_DIR = Path("/root/evolution/downloads/leaks")
OUTPUT_DIR = Path("/root/evolution/training_data")
MAX_REPOSITORIES = 50
MAX_FILE_SIZE = 1024 * 1024  # 1MB
RATE_LIMIT_DELAY = 2  # seconds between API calls

# Search queries for leaked AI code
SEARCH_QUERIES = [
    "claude code leak",
    "openai source leak",
    "anthropic leak",
    "ai assistant source code",
    "claude api leak",
    "gpt source leak",
    "llm training code leak",
    "openai internal code",
    "anthropic internal",
    "claude system prompt",
    "ai alignment code leak",
    "rlhf leak",
    "fine-tuning code leak",
]

# File extensions to analyze
RELEVANT_EXTENSIONS = [
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".h",
    ".swift", ".kt", ".scala", ".rb", ".php", ".cs", ".m", ".mm"
]

# Files to skip
SKIP_PATTERNS = [
    r"node_modules",
    r"__pycache__",
    r"\.git",
    r"vendor",
    r"dist",
    r"build",
    r"\.min\.",
    r"test.*\.(py|js)",
    r"spec\.(py|js)",
]

# === SETUP LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'/root/evolution/logs/eve_leak_analyzer_v{VERSION}.log')
    ]
)
logger = logging.getLogger(__name__)


# === DATA STRUCTURES ===

@dataclass
class RepositoryInfo:
    """Information about a leaked repository"""
    id: str
    url: str
    name: str
    description: str
    stars: int
    language: str
    created_at: str
    downloaded: bool = False
    download_path: Optional[str] = None
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ArchitecturePattern:
    """Extracted architecture pattern from code"""
    pattern_type: str
    code_snippet: str
    context: str
    file_path: str
    confidence: float
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TrainingPair:
    """Training data pair generated from analysis"""
    instruction: str
    input_text: str
    output_text: str
    source: str
    quality_score: float
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    timestamp: str
    version: str
    repositories_searched: int
    repositories_downloaded: int
    patterns_found: int
    training_pairs_generated: int
    repositories: List[RepositoryInfo]
    patterns: List[ArchitecturePattern]
    training_pairs: List[TrainingPair]
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "version": self.version,
            "repositories_searched": self.repositories_searched,
            "repositories_downloaded": self.repositories_downloaded,
            "patterns_found": self.patterns_found,
            "training_pairs_generated": self.training_pairs_generated,
            "repositories": [r.to_dict() for r in self.repositories],
            "patterns": [p.to_dict() for p in self.patterns],
            "training_pairs": [t.to_dict() for t in self.training_pairs],
            "metadata": self.metadata
        }


# === GITHUB SEARCH ===

class GitHubSearcher:
    """Search GitHub for leaked AI code repositories"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        else:
            logger.warning("No GitHub token provided. Rate limits will be lower.")
    
    def search_repositories(self, query: str, max_results: int = 10) -> List[RepositoryInfo]:
        """Search GitHub for repositories matching query"""
        repos = []
        page = 1
        per_page = min(30, max_results)
        
        while len(repos) < max_results:
            url = f"{self.base_url}/search/repositories"
            params = {
                'q': query,
                'sort': 'updated',
                'order': 'desc',
                'per_page': per_page,
                'page': page
            }
            
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 403:
                    logger.error("GitHub API rate limit exceeded")
                    break
                
                response.raise_for_status()
                data = response.json()
                
                for item in data.get('items', []):
                    repo = RepositoryInfo(
                        id=hashlib.md5(item['html_url'].encode()).hexdigest()[:12],
                        url=item['html_url'],
                        name=item['full_name'],
                        description=item.get('description', ''),
                        stars=item.get('stargazers_count', 0),
                        language=item.get('language', 'Unknown'),
                        created_at=item['created_at']
                    )
                    repos.append(repo)
                    
                    if len(repos) >= max_results:
                        break
                
                if len(data.get('items', [])) < per_page:
                    break
                    
                page += 1
                
            except requests.RequestException as e:
                logger.error(f"Error searching GitHub: {e}")
                break
        
        return repos[:max_results]


# === REPOSITORY DOWNLOADER ===

class RepositoryDownloader:
    """Download and cache repositories"""
    
    def __init__(self, download_dir: Path = DOWNLOAD_DIR):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def download(self, repo: RepositoryInfo) -> Optional[Path]:
        """Clone a repository to local storage"""
        repo_path = self.download_dir / repo.id
        
        if repo_path.exists():
            logger.info(f"Repository {repo.name} already cached")
            return repo_path
        
        try:
            logger.info(f"Downloading {repo.name}...")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', repo.url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                repo.downloaded = True
                repo.download_path = str(repo_path)
                logger.info(f"Successfully downloaded {repo.name}")
                return repo_path
            else:
                logger.error(f"Failed to download {repo.name}: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout downloading {repo.name}")
            return None
        except Exception as e:
            logger.error(f"Error downloading {repo.name}: {e}")
            return None
    
    def get_code_files(self, repo_path: Path) -> List[Path]:
        """Get all code files from a repository"""
        code_files = []
        
        if not repo_path.exists():
            return code_files
        
        for file_path in repo_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Check file size
            if file_path.stat().st_size > MAX_FILE_SIZE:
                continue
            
            # Check extension
            if file_path.suffix not in RELEVANT_EXTENSIONS:
                continue
            
            # Check skip patterns
            skip = False
            for pattern in SKIP_PATTERNS:
                if re.search(pattern, str(file_path)):
                    skip = True
                    break
            
            if not skip:
                code_files.append(file_path)
        
        return code_files


# === ARCHITECTURE ANALYZER ===

class ArchitectureAnalyzer:
    """Analyze code for architecture patterns"""
    
    # Pattern definitions for AI-related code
    PATTERNS = {
        'agent_loop': [
            r'(while|for).*?(agent|loop|cycle)',
            r'(def|class).*?agent.*?loop',
            r'observe.*think.*act',
            r'perception.*decision.*action',
        ],
        'prompt_template': [
            r'(prompt|template).*?=.*?[\'"].*?\{.*?\}',
            r'f[\'"].*?\{.*?\}.*?[\'"]',
            r'\.format\(',
            r'template\.render',
        ],
        'api_client': [
            r'(class|def).*?(client|api|request)',
            r'requests\.(get|post|put|delete)',
            r'httpx\.(get|post)',
            r'openai\.(ChatCompletion|Completion)',
            r'anthropic\.(Anthropic|Client)',
        ],
        'error_handling': [
            r'try:.*?except.*?Exception',
            r'raise.*Error',
            r'except\s+\('.*?\)',
        ],
        'async_pattern': [
            r'async\s+def',
            r'await\s+',
            r'asyncio\.(run|create_task|gather)',
        ],
        'config_management': [
            r'(config|settings|env)\.get',
            r'os\.environ\[',
            r'dotenv',
            r'yaml\.safe_load',
            r'json\.load',
        ],
        'logging': [
            r'logging\.(debug|info|warning|error)',
            r'logger\.(debug|info|warning|error)',
            r'print\(.*?(debug|error|info)',
        ],
        'tool_use': [
            r'(tool|function|action).*?(call|use|invoke)',
            r'(available|tools).*?=.*?\[',
        ],
        'memory_management': [
            r'(memory|context|history).*?(store|save|load)',
            r'conversation_history',
            r'message_history',
        ],
        'safety_guardrails': [
            r'(safety|guard|check|filter)',
            r'harmful|toxic|inappropriate',
            r'content_policy',
            r'moderation',
        ],
    }
    
    def __init__(self):
        self.patterns_found: List[ArchitecturePattern] = []
    
    def analyze_file(self, file_path: Path, repo_name: str) -> List[ArchitecturePattern]:
        """Analyze a single file for architecture patterns"""
        patterns = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")
            return patterns
        
        lines = content.split('\n')
        
        for pattern_type, regexes in self.PATTERNS.items():
            for regex in regexes:
                for match in re.finditer(regex, content, re.IGNORECASE | re.DOTALL):
                    # Get context around match
                    start = max(0, match.start() - 200)
                    end = min(len(content), match.end() + 200)
                    context = content[start:end]
                    
                    # Calculate line numbers
                    line_num = content[:match.start()].count('\n') + 1
                    
                    arch_pattern = ArchitecturePattern(
                        pattern_type=pattern_type,
                        code_snippet=match.group(0)[:200],
                        context=context[:400],
                        file_path=f"{repo_name}/{file_path.name}",
                        confidence=self._calculate_confidence(pattern_type, match.group(0)),
                        tags=[repo_name, file_path.suffix[1:], pattern_type]
                    )
                    patterns.append(arch_pattern)
        
        return patterns
    
    def _calculate_confidence(self, pattern_type: str, snippet: str) -> float:
        """Calculate confidence score for a pattern match"""
        base_confidence = 0.7
        
        # Boost confidence for specific indicators
        if pattern_type == 'agent_loop' and any(x in snippet.lower() for x in ['agent', 'loop', 'cycle']):
            base_confidence += 0.1
        
        if pattern_type == 'api_client' and any(x in snippet.lower() for x in ['openai', 'anthropic', 'claude']):
            base_confidence += 0.2
        
        if pattern_type == 'tool_use' and 'tool' in snippet.lower():
            base_confidence += 0.1
        
        if pattern_type == 'safety_guardrails' and 'safety' in snippet.lower():
            base_confidence += 0.15
        
        return min(1.0, base_confidence)
    
    def analyze_repository(self, repo_path: Path, repo_info: RepositoryInfo) -> List[ArchitecturePattern]:
        """Analyze an entire repository"""
        patterns = []
        downloader = RepositoryDownloader()
        code_files = downloader.get_code_files(repo_path)
        
        logger.info(f"Analyzing {len(code_files)} files in {repo_info.name}")
        
        for file_path in code_files:
            file_patterns = self.analyze_file(file_path, repo_info.name)
            patterns.extend(file_patterns)
        
        return patterns


# === TRAINING PAIR GENERATOR ===

class TrainingPairGenerator:
    """Generate training pairs from analyzed patterns"""
    
    TEMPLATES = {
        'agent_loop': {
            'instruction': 'Design an agent execution loop with the following components:',
            'output_template': 'Here is an agent execution loop implementation:\n\n```python\n{code}\n```\n\nKey features:\n- Continuous observation-action cycle\n- State management between iterations\n- Error handling for robustness\n'
        },
        'prompt_template': {
            'instruction': 'Create a prompt template system that supports dynamic variable substitution:',
            'output_template': 'Here is a prompt template implementation:\n\n```python\n{code}\n```\n\nFeatures:\n- Dynamic variable substitution\n- Template validation\n- Error handling for missing variables\n'
        },
        'api_client': {
            'instruction': 'Implement an API client with proper error handling and retries:',
            'output_template': 'Here is an API client implementation:\n\n```python\n{code}\n```\n\nKey aspects:\n- Connection pooling for efficiency\n- Exponential backoff for retries\n- Proper error handling and logging\n'
        },
        'tool_use': {
            'instruction': 'Create a tool use system for an AI agent:',
            'output_template': 'Here is a tool use implementation:\n\n```python\n{code}\n```\n\nFeatures:\n- Tool registration and discovery\n- Schema validation\n- Error handling for tool execution\n'
        },
        'safety_guardrails': {
            'instruction': 'Implement safety guardrails for AI agent outputs:',
            'output_template': 'Here is a safety guardrails implementation:\n\n```python\n{code}\n```\n\nSafety features:\n- Content filtering\n- Policy enforcement\n- Audit logging\n'
        },
        'memory_management': {
            'instruction': 'Design a memory management system for conversational AI:',
            'output_template': 'Here is a memory management implementation:\n\n```python\n{code}\n```\n\nKey features:\n- Conversation history tracking\n- Context window management\n- Token counting and trimming\n'
        },
    }
    
    def generate_pairs(self, patterns: List[ArchitecturePattern]) -> List[TrainingPair]:
        """Generate training pairs from architecture patterns"""
        pairs = []
        
        for pattern in patterns:
            if pattern.confidence < 0.6:
                continue
            
            template = self.TEMPLATES.get(pattern.pattern_type)
            if not template:
                continue
            
            # Create training pair
            instruction = template['instruction']
            input_text = f"Context: {pattern.context[:500]}"
            output_text = template['output_template'].format(code=pattern.code_snippet)
            
            pair = TrainingPair(
                instruction=instruction,
                input_text=input_text,
                output_text=output_text,
                source=pattern.file_path,
                quality_score=pattern.confidence,
                tags=pattern.tags + ['leak_analysis', pattern.pattern_type]
            )
            pairs.append(pair)
        
        return pairs
    
    def generate_insight_pairs(self, repositories: List[RepositoryInfo]) -> List[TrainingPair]:
        """Generate insight-based training pairs from repository metadata"""
        pairs = []
        
        for repo in repositories:
            if not repo.downloaded:
                continue
            
            # Create overview pair
            instruction = f"Analyze the architecture of {repo.name}"
            input_text = f"Repository: {repo.name}\nDescription: {repo.description}\nLanguage: {repo.language}\nStars: {repo.stars}"
            output_text = f"""Analysis of {repo.name}:

This repository appears to be related to AI/ML based on its description and structure.
Key observations:
- Primary language: {repo.language}
- Popularity: {repo.stars} stars
- Purpose: {repo.description or 'Not specified'}

This could contain valuable patterns for:
- Agent architecture
- API integration
- Error handling
- Tool usage
"""
            
            pair = TrainingPair(
                instruction=instruction,
                input_text=input_text,
                output_text=output_text,
                source=repo.url,
                quality_score=min(1.0, repo.stars / 1000 + 0.5),
                tags=[repo.name, 'repository_analysis', 'overview']
            )
            pairs.append(pair)
        
        return pairs


# === MAIN ANALYZER ===

class LeakAnalyzer:
    """Main class for analyzing leaked AI code"""
    
    def __init__(self):
        self.github = GitHubSearcher()
        self.downloader = RepositoryDownloader()
        self.analyzer = ArchitectureAnalyzer()
        self.generator = TrainingPairGenerator()
        self.repositories: List[RepositoryInfo] = []
        self.patterns: List[ArchitecturePattern] = []
        self.training_pairs: List[TrainingPair] = []
    
    def search_and_collect(self) -> List[RepositoryInfo]:
        """Search for and collect repositories"""
        logger.info("Searching GitHub for leaked AI code repositories...")
        
        all_repos = []
        for query in SEARCH_QUERIES:
            logger.info(f"Searching: {query}")
            repos = self.github.search_repositories(query, max_results=5)
            all_repos.extend(repos)
        
        # Remove duplicates
        seen_ids = set()
        unique_repos = []
        for repo in all_repos:
            if repo.id not in seen_ids:
                seen_ids.add(repo.id)
                unique_repos.append(repo)
        
        # Sort by relevance (stars + recent)
        unique_repos.sort(key=lambda r: r.stars, reverse=True)
        
        logger.info(f"Found {len(unique_repos)} unique repositories")
        return unique_repos[:MAX_REPOSITORIES]
    
    def download_repositories(self, repos: List[RepositoryInfo]) -> List[RepositoryInfo]:
        """Download selected repositories"""
        downloaded = []
        
        for repo in repos:
            path = self.downloader.download(repo)
            if path:
                repo.downloaded = True
                repo.download_path = str(path)
                downloaded.append(repo)
        
        logger.info(f"Downloaded {len(downloaded)} repositories")
        return downloaded
    
    def analyze_repositories(self, repos: List[RepositoryInfo]) -> List[ArchitecturePattern]:
        """Analyze all downloaded repositories"""
        all_patterns = []
        
        for repo in repos:
            if not repo.downloaded or not repo.download_path:
                continue
            
            repo_path = Path(repo.download_path)
            patterns = self.analyzer.analyze_repository(repo_path, repo)
            all_patterns.extend(patterns)
            
            logger.info(f"Found {len(patterns)} patterns in {repo.name}")
        
        logger.info(f"Total patterns found: {len(all_patterns)}")
        return all_patterns
    
    def generate_training_data(self) -> List[TrainingPair]:
        """Generate all training pairs"""
        pairs = []
        
        # Generate from patterns
        pattern_pairs = self.generator.generate_pairs(self.patterns)
        pairs.extend(pattern_pairs)
        
        # Generate from repository insights
        insight_pairs = self.generator.generate_insight_pairs(self.repositories)
        pairs.extend(insight_pairs)
        
        # Sort by quality score
        pairs.sort(key=lambda p: p.quality_score, reverse=True)
        
        logger.info(f"Generated {len(pairs)} training pairs")
        return pairs
    
    def save_results(self, output_path: Optional[Path] = None) -> Path:
        """Save analysis results to JSON"""
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = OUTPUT_DIR / f'leak_analysis_{timestamp}.json'
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        result = AnalysisResult(
            timestamp=datetime.now().isoformat(),
            version=VERSION,
            repositories_searched=len(self.repositories),
            repositories_downloaded=sum(1 for r in self.repositories if r.downloaded),
            patterns_found=len(self.patterns),
            training_pairs_generated=len(self.training_pairs),
            repositories=self.repositories,
            patterns=self.patterns[:1000],  # Limit for file size
            training_pairs=self.training_pairs[:5000],  # Limit for file size
            metadata={
                'search_queries': SEARCH_QUERIES,
                'max_repositories': MAX_REPOSITORIES,
                'output_version': '1.0'
            }
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {output_path}")
        return output_path
    
    def save_training_jsonl(self, output_path: Optional[Path] = None) -> Path:
        """Save training pairs in JSONL format for fine-tuning"""
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = OUTPUT_DIR / f'leak_training_{timestamp}.jsonl'
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for pair in self.training_pairs:
                record = {
                    'instruction': pair.instruction,
                    'input': pair.input_text,
                    'output': pair.output_text,
                    'source': pair.source,
                    'quality_score': pair.quality_score,
                    'tags': pair.tags
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        logger.info(f"Training data saved to {output_path}")
        return output_path
    
    def run(self) -> AnalysisResult:
        """Run the complete analysis pipeline"""
        logger.info("=" * 60)
        logger.info(f"Eve Leak Analyzer v{VERSION}")
        logger.info("=" * 60)
        
        # Step 1: Search for repositories
        self.repositories = self.search_and_collect()
        
        # Step 2: Download repositories
        self.repositories = self.download_repositories(self.repositories)
        
        # Step 3: Analyze repositories
        self.patterns = self.analyze_repositories(self.repositories)
        
        # Step 4: Generate training pairs
        self.training_pairs = self.generate_training_data()
        
        # Step 5: Save results
        self.save_results()
        self.save_training_jsonl()
        
        logger.info("Analysis complete!")
        
        return AnalysisResult(
            timestamp=datetime.now().isoformat(),
            version=VERSION,
            repositories_searched=len(self.repositories),
            repositories_downloaded=sum(1 for r in self.repositories if r.downloaded),
            patterns_found=len(self.patterns),
            training_pairs_generated=len(self.training_pairs),
            repositories=self.repositories,
            patterns=self.patterns,
            training_pairs=self.training_pairs
        )


# === CLI INTERFACE ===

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze leaked AI code from GitHub and generate training data'
    )
    parser.add_argument(
        '--search-only',
        action='store_true',
        help='Only search for repositories, do not download'
    )
    parser.add_argument(
        '--max-repos',
        type=int,
        default=MAX_REPOSITORIES,
        help=f'Maximum repositories to download (default: {MAX_REPOSITORIES})'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output directory for results'
    )
    
    args = parser.parse_args()
    
    analyzer = LeakAnalyzer()
    
    if args.search_only:
        repos = analyzer.search_and_collect()
        print(json.dumps([r.to_dict() for r in repos], indent=2))
        return
    
    result = analyzer.run()
    
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Repositories searched: {result.repositories_searched}")
    print(f"Repositories downloaded: {result.repositories_downloaded}")
    print(f"Patterns found: {result.patterns_found}")
    print(f"Training pairs generated: {result.training_pairs_generated}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()