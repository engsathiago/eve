#!/usr/bin/env python3
"""
eve_research_orchestrator.py — Modular Research Pipeline for Eve
Ciclo #84 — Infrastructure for Autonomous Research

Integra múltiplas fontes de pesquisa com priorização inteligente.

Usage:
    python eve_research_orchestrator.py --query "SPPO vs ORPO" --source arxiv
    python eve_research_orchestrator.py --from-questions --top 5
"""

import os
import sys
import json
import hashlib
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

# =============================================================================
# CONFIGURATION
# =============================================================================

# File paths
CACHE_DB = Path("/root/evolution/.research_cache.db")
MEMORY_DIR = Path("/memory")
RESEARCH_DIR = MEMORY_DIR / "research"
QUESTIONS_FILE = MEMORY_DIR / "corrective" / "questions" / "active.md"

# Default values
DEFAULT_TOP_QUESTIONS = 5
DEFAULT_CONFIDENCE = 50.0
DEFAULT_PRIORITY_SCORE = 1.0

# String lengths for display
MAX_QUERY_DISPLAY_LEN = 60
MAX_TITLE_DISPLAY_LEN = 60
MAX_CONTENT_PREVIEW_LEN = 500

# Query ID formats
QUERY_ID_FORMAT = "RQ-{date}-{index:03d}"
MANUAL_QUERY_ID_FORMAT = "RQ-manual-{timestamp}"
DATE_FORMAT = "%Y%m%d"
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

# SQL Queries
SQL_CREATE_QUERIES_TABLE = """
    CREATE TABLE IF NOT EXISTS queries (
        id TEXT PRIMARY KEY,
        question_id TEXT,
        query TEXT NOT NULL,
        source TEXT NOT NULL,
        category TEXT,
        confidence_before REAL,
        priority_score REAL,
        created_at TEXT,
        status TEXT,
        result_hash TEXT
    )
"""

SQL_CREATE_RESULTS_TABLE = """
    CREATE TABLE IF NOT EXISTS results (
        hash TEXT PRIMARY KEY,
        query_id TEXT NOT NULL,
        title TEXT,
        content TEXT,
        source TEXT,
        url TEXT,
        retrieved_at TEXT,
        relevance_score REAL,
        confidence_impact REAL
    )
"""

# Question parsing
QUESTION_PREFIXES = ['Como ', 'Qual ', 'O que ']
QUESTION_SUFFIX = '?'
CONFIDENCE_PERCENT_SYMBOL = '%'

# Source mappings
CATEGORY_TO_SOURCE = {
    'Técnicas': 'arxiv',
    'Arquitetura': 'arxiv',
    'Dados & RL': 'arxiv',
    'Auto-modificação': 'web',
    'Externo': 'web',
    'Meta-QUESTIONs': 'memory'
}
DEFAULT_SOURCE = 'web'


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ResearchQuery:
    """A research query with metadata for prioritization.
    
    Attributes:
        id: Unique identifier for this query.
        question_id: Optional reference to the source question ID.
        query: The actual search query text.
        source: Data source to search (arxiv, web, github, memory).
        category: Category of the question for routing.
        confidence_before: Confidence level before research (0-100).
        priority_score: Computed priority for scheduling.
        created_at: ISO timestamp when query was created.
        status: Current status (pending, running, completed, failed).
    """
    id: str
    question_id: Optional[str]
    query: str
    source: str
    category: str
    confidence_before: float
    priority_score: float
    created_at: str
    status: str = "pending"
    
    def to_dict(self) -> Dict:
        """Convert dataclass to dictionary for serialization."""
        return asdict(self)


@dataclass
class ResearchResult:
    """A research result with epistemic metadata.
    
    Attributes:
        query_id: Reference to the originating query.
        title: Title of the result.
        content: Full content or summary.
        source: Source that provided this result.
        url: Optional URL to full resource.
        retrieved_at: ISO timestamp when retrieved.
        relevance_score: Computed relevance (0-1).
        confidence_impact: Expected impact on confidence (0-1).
        hash: MD5 hash for deduplication.
    """
    query_id: str
    title: str
    content: str
    source: str
    url: Optional[str]
    retrieved_at: str
    relevance_score: float
    confidence_impact: float
    hash: str


# =============================================================================
# RESEARCH CACHE
# =============================================================================

class ResearchCache:
    """SQLite cache for research results.
    
    Provides persistent storage for research queries and their results,
    with deduplication based on content hash.
    
    Attributes:
        db_path: Path to the SQLite database file.
    """
    
    def __init__(self, db_path: Path = CACHE_DB):
        """Initialize the cache with the given database path.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist.
        
        Creates the queries and results tables with proper indices.
        Raises sqlite3.Error on database failure.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(SQL_CREATE_QUERIES_TABLE)
                conn.execute(SQL_CREATE_RESULTS_TABLE)
        except sqlite3.Error as e:
            print(f"[Error] Failed to initialize database: {e}")
            raise
    
    def get_cached(self, query_hash: str) -> Optional[Dict]:
        """Retrieve a cached result by its hash.
        
        Args:
            query_hash: MD5 hash of the query.
            
        Returns:
            Dict with result data if found, None otherwise.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM results WHERE hash = ?",
                    (query_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "hash": row[0],
                        "query_id": row[1],
                        "title": row[2],
                        "content": row[3],
                        "source": row[4],
                        "url": row[5],
                        "retrieved_at": row[6],
                        "relevance_score": row[7],
                        "confidence_impact": row[8]
                    }
                return None
        except sqlite3.Error as e:
            print(f"[Error] Failed to retrieve from cache: {e}")
            return None
    
    def cache_result(self, result: ResearchResult) -> bool:
        """Cache a research result.
        
        Args:
            result: The ResearchResult to cache.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO results 
                    (hash, query_id, title, content, source, url, retrieved_at, relevance_score, confidence_impact)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.hash, result.query_id, result.title, result.content,
                    result.source, result.url, result.retrieved_at,
                    result.relevance_score, result.confidence_impact
                ))
            return True
        except sqlite3.Error as e:
            print(f"[Error] Failed to cache result: {e}")
            return False
    
    def update_query_status(self, query_id: str, status: str, result_hash: Optional[str] = None) -> bool:
        """Update the status of a query.
        
        Args:
            query_id: The ID of the query to update.
            status: New status (pending, running, completed, failed).
            result_hash: Optional hash of the result.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE queries SET status = ?, result_hash = ? WHERE id = ?",
                    (status, result_hash, query_id)
                )
            return True
        except sqlite3.Error as e:
            print(f"[Error] Failed to update query status: {e}")
            return False


# =============================================================================
# QUESTION PARSER
# =============================================================================

class QuestionParser:
    """Parse QUESTIONS.md to extract high-priority questions.
    
    Reads the QUESTIONS.md file and extracts structured question data,
    generating research queries prioritized by confidence level.
    """
    
    def __init__(self, questions_file: Path = QUESTIONS_FILE):
        """Initialize with the path to the questions file.
        
        Args:
            questions_file: Path to the QUESTIONS.md file.
        """
        self.questions_file = questions_file
    
    def _read_questions_file(self) -> str:
        """Read the questions file with proper error handling.
        
        Returns:
            File contents as string.
            
        Raises:
            IOError: If file cannot be read.
        """
        if not self.questions_file.exists():
            return ""
        
        try:
            return self.questions_file.read_text(encoding='utf-8')
        except (IOError, OSError) as e:
            print(f"[Error] Failed to read questions file: {e}")
            return ""
    
    def _extract_confidence(self, confidence_str: str) -> float:
        """Parse confidence string to float.
        
        Args:
            confidence_str: String potentially containing percentage.
            
        Returns:
            Confidence value as float (0-100).
        """
        if not confidence_str:
            return DEFAULT_CONFIDENCE
        
        try:
            if CONFIDENCE_PERCENT_SYMBOL in confidence_str:
                return float(confidence_str.replace(CONFIDENCE_PERCENT_SYMBOL, ''))
            return float(confidence_str)
        except ValueError:
            return DEFAULT_CONFIDENCE
    
    def _parse_table_row(self, line: str, current_category: Optional[str]) -> Optional[Dict]:
        """Parse a single table row into question data.
        
        Args:
            line: The line to parse.
            current_category: The current category context.
            
        Returns:
            Question dict if parsed successfully, None otherwise.
        """
        if '|' not in line or line.startswith('|---') or line.startswith('| ID'):
            return None
        
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 5 or not parts[1] or parts[1] in ['ID', '----']:
            return None
        
        try:
            return {
                'id': parts[1],
                'question': parts[2],
                'confidence': self._extract_confidence(parts[3]),
                'category': current_category or 'unknown',
                'evidence': parts[4] if len(parts) > 4 else ''
            }
        except (ValueError, IndexError):
            return None
    
    def parse_questions(self) -> List[Dict]:
        """Extract questions from QUESTIONS.md.
        
        Parses markdown tables to extract question IDs, text,
        confidence levels, and categories.
        
        Returns:
            List of question dictionaries with id, question, confidence,
            category, and evidence keys.
        """
        questions = []
        content = self._read_questions_file()
        
        if not content:
            return questions
        
        lines = content.split('\n')
        current_category = None
        
        for line in lines:
            # Detect category headers
            if line.startswith('## '):
                current_category = line[3:].strip()
            
            # Parse question rows in markdown tables
            question = self._parse_table_row(line, current_category)
            if question:
                questions.append(question)
        
        return questions
    
    def _calculate_priority(self, confidence: float) -> float:
        """Calculate priority score from confidence.
        
        Lower confidence = higher priority for research.
        
        Args:
            confidence: Confidence level (0-100).
            
        Returns:
            Priority score (0-1).
        """
        return (100 - confidence) / 100.0
    
    def _sort_questions_by_priority(self, questions: List[Dict]) -> List[Dict]:
        """Sort questions by research priority.
        
        Priority is determined by:
        1. Lower confidence first (higher information gain potential)
        2. Ontological questions deprioritized (harder to answer)
        
        Args:
            questions: List of question dictionaries.
            
        Returns:
            Sorted list of questions.
        """
        return sorted(questions, key=lambda q: (
            100 - q['confidence'],
            q['category'] != 'Ontológicas'
        ))
    
    def generate_queries(self, top_n: int = DEFAULT_TOP_QUESTIONS) -> List[ResearchQuery]:
        """Generate research queries from high-priority questions.
        
        Selects the top N questions with lowest confidence for research,
        mapping categories to appropriate research sources.
        
        Args:
            top_n: Number of questions to select.
            
        Returns:
            List of ResearchQuery objects ready for execution.
        """
        questions = self.parse_questions()
        if not questions:
            return []
        
        sorted_questions = self._sort_questions_by_priority(questions)
        queries = []
        current_date = datetime.now().strftime(DATE_FORMAT)
        
        for i, q in enumerate(sorted_questions[:top_n]):
            source = CATEGORY_TO_SOURCE.get(q['category'], DEFAULT_SOURCE)
            
            query = ResearchQuery(
                id=QUERY_ID_FORMAT.format(date=current_date, index=i),
                question_id=q['id'],
                query=self._sanitize_query(q['question']),
                source=source,
                category=q['category'],
                confidence_before=q['confidence'],
                priority_score=self._calculate_priority(q['confidence']),
                created_at=datetime.now().isoformat()
            )
            queries.append(query)
        
        return queries
    
    def _sanitize_query(self, question: str) -> str:
        """Convert a question to a searchable query string.
        
        Removes leading articles and trailing punctuation to create
        a more effective search query.
        
        Args:
            question: The original question text.
            
        Returns:
            Sanitized query string ready for search.
        """
        query = question.strip()
        
        # Remove leading articles
        for prefix in QUESTION_PREFIXES:
            if query.startswith(prefix):
                query = query[len(prefix):]
        
        # Remove trailing punctuation
        if query.endswith(QUESTION_SUFFIX):
            query = query[:-1]
        
        return query.strip()


# =============================================================================
# PROVIDER INTERFACES
# =============================================================================

class ResearchProvider:
    """Abstract base class for research providers.
    
    All research sources (arXiv, Web, GitHub, Memory) must implement
    this interface for integration with the orchestrator.
    """
    
    def is_available(self) -> bool:
        """Check if this provider is available for use.
        
        Returns:
            True if provider can be used, False otherwise.
        """
        raise NotImplementedError
    
    def search(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Execute a search query.
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if successful, None otherwise.
        """
        raise NotImplementedError


class ArxivProvider(ResearchProvider):
    """arXiv API provider for papers.
    
    Searches academic papers on arXiv. Does not require API key.
    """
    
    def is_available(self) -> bool:
        """arXiv doesn't require API key."""
        return True
    
    def search(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Search arXiv for papers matching the query.
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if found, None otherwise.
            
        TODO: Implement arxiv-python integration
        """
        print(f"[arXiv] Would search: {query.query}")
        return None


class WebSearchProvider(ResearchProvider):
    """Web search provider using Brave, Gemini, or Perplexity APIs.
    
    Requires at least one of: BRAVE_API_KEY, GEMINI_API_KEY, PERPLEXITY_API_KEY
    """
    
    # Environment variable names for API keys
    API_KEY_VARS = ['BRAVE_API_KEY', 'GEMINI_API_KEY', 'PERPLEXITY_API_KEY']
    
    def is_available(self) -> bool:
        """Check if any web search API key is configured."""
        return any(os.getenv(var) for var in self.API_KEY_VARS)
    
    def _get_available_source(self) -> Optional[str]:
        """Determine which search service to use.
        
        Returns:
            Name of available service, or None if none available.
        """
        for var in self.API_KEY_VARS:
            if os.getenv(var):
                return var.replace('_API_KEY', '').lower()
        return None
    
    def search(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Search web for information matching the query.
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if found, None otherwise.
            
        TODO: Implement with actual API calls
        """
        source = self._get_available_source()
        if source:
            print(f"[Web/{source}] Would search: {query.query}")
        else:
            print(f"[Web] Would search: {query.query}")
        return None


class GitHubProvider(ResearchProvider):
    """GitHub API provider for code search.
    
    Searches code repositories. Requires GITHUB_TOKEN environment variable.
    """
    
    TOKEN_VAR = 'GITHUB_TOKEN'
    
    def is_available(self) -> bool:
        """Check if GitHub token is configured."""
        return bool(os.getenv(self.TOKEN_VAR))
    
    def search(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Search GitHub for code matching the query.
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if found, None otherwise.
        """
        print(f"[GitHub] Would search: {query.query}")
        return None


class MemoryProvider(ResearchProvider):
    """Local memory provider using ChromaDB and files.
    
    Searches local memory stores for relevant information.
    """
    
    def is_available(self) -> bool:
        """Check if memory directory exists."""
        return MEMORY_DIR.exists()
    
    def search(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Search local memory for information matching the query.
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if found, None otherwise.
            
        TODO: Implement ChromaDB semantic search
        """
        print(f"[Memory] Would search: {query.query}")
        return None


# =============================================================================
# RESEARCH ORCHESTRATOR
# =============================================================================

class ResearchOrchestrator:
    """Main orchestrator for research pipeline.
    
    Coordinates multiple research providers, manages caching,
    and prioritizes queries based on confidence and relevance.
    """
    
    def __init__(self, cache: Optional[ResearchCache] = None):
        """Initialize the orchestrator with cache and providers.
        
        Args:
            cache: Optional ResearchCache instance (creates new if None).
        """
        self.cache = cache or ResearchCache()
        self.question_parser = QuestionParser()
        self.providers: Dict[str, ResearchProvider] = {
            'arxiv': ArxivProvider(),
            'web': WebSearchProvider(),
            'github': GitHubProvider(),
            'memory': MemoryProvider()
        }
    
    def _get_provider(self, source: str) -> Optional[ResearchProvider]:
        """Get a provider by source name.
        
        Args:
            source: The source identifier.
            
        Returns:
            ResearchProvider if found, None otherwise.
        """
        return self.providers.get(source)
    
    def _check_cache(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Check if query result is cached.
        
        Args:
            query: The research query.
            
        Returns:
            Cached ResearchResult if found, None otherwise.
        """
        query_hash = hashlib.md5(
            f"{query.source}:{query.query}".encode()
        ).hexdigest()
        
        cached = self.cache.get_cached(query_hash)
        if cached:
            print(f"[Cache] Hit for query: {query.query[:MAX_QUERY_DISPLAY_LEN]}...")
            return ResearchResult(**cached)
        return None
    
    def _execute_provider_search(
        self,
        query: ResearchQuery,
        provider: ResearchProvider
    ) -> Optional[ResearchResult]:
        """Execute search through the specified provider.
        
        Args:
            query: The research query to execute.
            provider: The provider to use.
            
        Returns:
            ResearchResult if successful, None otherwise.
        """
        self.cache.update_query_status(query.id, "running")
        
        try:
            result = provider.search(query)
        except Exception as e:
            print(f"[Error] Provider {query.source} failed: {e}")
            result = None
        
        return result
    
    def _cache_and_finalize(
        self,
        query: ResearchQuery,
        result: Optional[ResearchResult]
    ) -> Optional[ResearchResult]:
        """Cache result and update query status.
        
        Args:
            query: The original query.
            result: The result to cache (may be None).
            
        Returns:
            Finalized ResearchResult if successful, None otherwise.
        """
        query_hash = hashlib.md5(
            f"{query.source}:{query.query}".encode()
        ).hexdigest()
        
        if result:
            result.hash = query_hash
            self.cache.cache_result(result)
            self.cache.update_query_status(query.id, "completed", result.hash)
            print(f"[Success] Retrieved: {result.title[:MAX_TITLE_DISPLAY_LEN]}...")
        else:
            self.cache.update_query_status(query.id, "failed")
        
        return result
    
    def run_query(self, query: ResearchQuery) -> Optional[ResearchResult]:
        """Execute a single research query through the full pipeline.
        
        Steps:
        1. Validate provider availability
        2. Check cache for existing result
        3. Execute search through provider
        4. Cache and return result
        
        Args:
            query: The research query to execute.
            
        Returns:
            ResearchResult if successful, None otherwise.
        """
        print(f"[Research] Querying {query.source}: {query.query[:MAX_QUERY_DISPLAY_LEN]}...")
        
        provider = self._get_provider(query.source)
        if not provider:
            print(f"[Error] Unknown provider: {query.source}")
            return None
        
        if not provider.is_available():
            print(f"[Skip] Provider {query.source} not available (check API keys)")
            return None
        
        # Check cache
        cached_result = self._check_cache(query)
        if cached_result:
            return cached_result
        
        # Execute query
        result = self._execute_provider_search(query, provider)
        
        # Cache and finalize
        return self._cache_and_finalize(query, result)
    
    def run_from_questions(self, top_n: int = DEFAULT_TOP_QUESTIONS) -> List[ResearchResult]:
        """Run research based on QUESTIONS.md priority.
        
        Generates queries from the QUESTION registry, prioritizing
        low-confidence questions for maximum information gain.
        
        Args:
            top_n: Number of questions to research.
            
        Returns:
            List of successful ResearchResult objects.
        """
        queries = self.question_parser.generate_queries(top_n)
        results = []
        
        print(f"[Research] Generated {len(queries)} queries from QUESTIONS.md")
        
        for query in queries:
            result = self.run_query(query)
            if result:
                results.append(result)
        
        return results


# =============================================================================
# CLI INTERFACE
# =============================================================================

def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.
    
    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Eve Research Orchestrator - Intelligent research pipeline"
    )
    parser.add_argument(
        "--query",
        help="Single search query to execute"
    )
    parser.add_argument(
        "--source",
        choices=["arxiv", "web", "github", "memory"],
        default=DEFAULT_SOURCE,
        help=f"Source to search (default: {DEFAULT_SOURCE})"
    )
    parser.add_argument(
        "--from-questions",
        action="store_true",
        help="Use QUESTIONS.md as source for research queries"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_QUESTIONS,
        help=f"Number of questions to research (default: {DEFAULT_TOP_QUESTIONS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    return parser


def execute_dry_run(orchestrator: ResearchOrchestrator, args) -> None:
    """Execute dry run mode showing planned actions.
    
    Args:
        orchestrator: The research orchestrator instance.
        args: Parsed command line arguments.
    """
    print("[DRY RUN] Research orchestrator would:")
    
    if args.from_questions:
        queries = orchestrator.question_parser.generate_queries(args.top)
        for q in queries:
            print(f"  - [{q.source}] {q.query[:MAX_QUERY_DISPLAY_LEN]}... "
                  f"(priority: {q.priority_score:.2f})")
    elif args.query:
        print(f"  - [{args.source}] {args.query}")
    else:
        print("  - No action specified (use --query or --from-questions)")


def execute_single_query(
    orchestrator: ResearchOrchestrator,
    query_text: str,
    source: str
) -> None:
    """Execute a single manual research query.
    
    Args:
        orchestrator: The research orchestrator instance.
        query_text: The search query text.
        source: The source to search.
    """
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    query = ResearchQuery(
        id=MANUAL_QUERY_ID_FORMAT.format(timestamp=timestamp),
        question_id=None,
        query=query_text,
        source=source,
        category="manual",
        confidence_before=DEFAULT_CONFIDENCE,
        priority_score=DEFAULT_PRIORITY_SCORE,
        created_at=datetime.now().isoformat()
    )
    
    result = orchestrator.run_query(query)
    
    if result:
        print(f"\n[Result] {result.title}")
        print(f"[Content] {result.content[:MAX_CONTENT_PREVIEW_LEN]}...")
    else:
        print("\n[No Result] Query returned no results")


def main() -> int:
    """Main entry point for the research orchestrator.
    
    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        orchestrator = ResearchOrchestrator()
    except Exception as e:
        print(f"[Error] Failed to initialize orchestrator: {e}")
        return 1
    
    if args.dry_run:
        execute_dry_run(orchestrator, args)
        return 0
    
    if args.from_questions:
        results = orchestrator.run_from_questions(args.top)
        print(f"\n[Summary] Completed {len(results)} research tasks")
        return 0 if results else 1
    
    if args.query:
        execute_single_query(orchestrator, args.query, args.source)
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
