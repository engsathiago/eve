#!/usr/bin/env python3
"""
eve_offline_search_v112.py - Offline Research Fallback

Sistema de pesquisa que funciona 100% offline usando:
- Cache local de papers
- Índice pré-construído de conceitos
- Heurísticas de relevância

Autor: Eve 🌙
Ciclo: #112
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import sqlite3

# Configurações
RESEARCH_DIR = Path("/root/evolution/research_cache")
CONCEPT_INDEX_PATH = RESEARCH_DIR / "concept_index.json"
PAPER_DB_PATH = RESEARCH_DIR / "research_papers.db"

@dataclass
class SearchResult:
    """Resultado de busca offline."""
    source: str  # 'cache', 'concept_index', 'heuristic'
    title: str
    arxiv_id: Optional[str]
    summary: str
    relevance_score: float
    matched_concepts: List[str]


class ConceptIndex:
    """Índice de conceitos extraídos de papers para busca offline."""
    
    # Conceitos pré-definidos e seus sinônimos
    CONCEPTS = {
        "memory": ["memory", "memoria", "long-term", "short-term", "retrieval", "storage"],
        "autonomy": ["autonomous", "autonomy", "self-directed", "independent", "self-governing"],
        "learning": ["learning", "training", "fine-tuning", "adaptation", "optimization"],
        "reasoning": ["reasoning", "inference", "deduction", "logic", "planning"],
        "safety": ["safety", "alignment", "robustness", "reliability", "guardrails"],
        "architecture": ["architecture", "framework", "system", "design", "structure"],
        "agents": ["agent", "multi-agent", "agency", "actor", "entity"],
        "embeddings": ["embedding", "vector", "representation", "encoding", "semantic"],
        "orchestration": ["orchestration", "coordination", "workflow", "pipeline"],
        "feedback": ["feedback", "correction", "improvement", "evaluation", "assessment"]
    }
    
    def __init__(self):
        self.index = defaultdict(list)  # concept -> [paper_ids]
        self._load_or_build()
    
    def _load_or_build(self):
        """Carrega índice existente ou constrói novo."""
        if CONCEPT_INDEX_PATH.exists():
            with open(CONCEPT_INDEX_PATH) as f:
                data = json.load(f)
                self.index = defaultdict(list, data)
            print(f"[INFO] Índice carregado: {len(self.index)} conceitos")
        else:
            print("[INFO] Índice não encontrado, será construído na primeira execução")
    
    def build_from_papers(self, papers: List[Dict]):
        """Constrói índice a partir de papers."""
        for paper in papers:
            text = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
            paper_id = paper.get('arxiv_id', paper.get('hash', 'unknown'))
            
            for concept, keywords in self.CONCEPTS.items():
                if any(kw in text for kw in keywords):
                    self.index[concept].append(paper_id)
        
        # Salvar
        CONCEPT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONCEPT_INDEX_PATH, "w") as f:
            json.dump(dict(self.index), f, indent=2)
        
        print(f"[INFO] Índice construído: {len(self.index)} conceitos")
    
    def search(self, query: str) -> List[str]:
        """Retorna paper_ids relevantes para a query."""
        query_lower = query.lower()
        matched_papers = set()
        matched_concepts = []
        
        for concept, keywords in self.CONCEPTS.items():
            if any(kw in query_lower for kw in keywords):
                matched_papers.update(self.index.get(concept, []))
                matched_concepts.append(concept)
        
        return list(matched_papers), matched_concepts


class OfflineSearcher:
    """Motor de busca offline completo."""
    
    def __init__(self):
        self.concept_index = ConceptIndex()
        self.paper_cache = self._load_paper_cache()
    
    def _load_paper_cache(self) -> Dict[str, Dict]:
        """Carrega papers do banco SQLite local."""
        cache = {}
        
        if not PAPER_DB_PATH.exists():
            return cache
        
        try:
            import sqlite3
            with sqlite3.connect(PAPER_DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT arxiv_id, title, summary, primary_category FROM papers"
                )
                for row in cursor:
                    cache[row[0]] = {
                        "arxiv_id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "category": row[3]
                    }
        except Exception as e:
            print(f"[WARN] Não foi possível carregar cache: {e}")
        
        return cache
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Busca offline em múltiplas fontes."""
        results = []
        
        # 1. Busca por conceito
        paper_ids, concepts = self.concept_index.search(query)
        for pid in paper_ids[:max_results]:
            if pid in self.paper_cache:
                paper = self.paper_cache[pid]
                results.append(SearchResult(
                    source="concept_index",
                    title=paper["title"],
                    arxiv_id=pid,
                    summary=paper["summary"][:300] if paper["summary"] else "No summary",
                    relevance_score=0.8 + (0.05 * len(concepts)),
                    matched_concepts=concepts
                ))
        
        # 2. Busca por similaridade de título (heurística)
        if len(results) < max_results:
            query_words = set(query.lower().split())
            for pid, paper in self.paper_cache.items():
                if pid not in [r.arxiv_id for r in results]:
                    title_words = set(paper["title"].lower().split())
                    overlap = len(query_words & title_words)
                    if overlap > 0:
                        results.append(SearchResult(
                            source="heuristic",
                            title=paper["title"],
                            arxiv_id=pid,
                            summary=paper["summary"][:300] if paper["summary"] else "No summary",
                            relevance_score=0.5 + (0.1 * overlap),
                            matched_concepts=[f"word_overlap:{overlap}"]
                        ))
        
        # 3. Fallback: templates de resposta
        if not results:
            results.append(self._generate_fallback_result(query))
        
        # Ordenar por relevance_score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:max_results]
    
    def _generate_fallback_result(self, query: str) -> SearchResult:
        """Gera resultado simulado quando não há dados."""
        
        # Templates por categoria de query
        templates = {
            "memory": "Memory systems for AI agents typically involve external vector stores like ChromaDB or in-memory caching for rapid retrieval.",
            "autonomy": "Autonomous agent architectures often follow the sense-think-act loop with feedback mechanisms for self-correction.",
            "learning": "Self-improving systems can use evolutionary algorithms or gradient-based optimization to refine their behavior.",
            "safety": "AI safety mechanisms include output filtering, policy enforcement layers, and sandboxed execution environments.",
            "default": "This topic relates to autonomous AI systems. Research papers in cs.AI and cs.LG categories often cover related material."
        }
        
        query_lower = query.lower()
        content = templates["default"]
        
        for key, template in templates.items():
            if key in query_lower:
                content = template
                break
        
        return SearchResult(
            source="heuristic",
            title=f"Offline Knowledge: {query[:40]}",
            arxiv_id=None,
            summary=content,
            relevance_score=0.3,
            matched_concepts=["fallback_template"]
        )
    
    def get_concept_summary(self, concept: str) -> Optional[str]:
        """Retorna resumo de um conceito baseado em papers cacheados."""
        if concept not in self.concept_index.CONCEPTS:
            return None
        
        paper_ids = self.concept_index.index.get(concept, [])
        if not paper_ids:
            return f"No cached papers for concept: {concept}"
        
        # Agregar summaries
        summaries = []
        for pid in paper_ids[:3]:
            if pid in self.paper_cache:
                paper = self.paper_cache[pid]
                summaries.append(f"- {paper['title']}: {paper['summary'][:150]}...")
        
        return f"Concept: {concept}\nBased on {len(paper_ids)} papers:\n" + "\n".join(summaries)


def main():
    """Entry point para teste."""
    print("=" * 60)
    print("EVE OFFLINE SEARCH v112 🌙")
    print("Research without internet connectivity")
    print("=" * 60)
    
    searcher = OfflineSearcher()
    
    # Test queries
    test_queries = [
        "memory systems for agents",
        "autonomous learning",
        "safety alignment",
        "multi-agent coordination"
    ]
    
    for query in test_queries:
        print(f"\n[Query] {query}")
        results = searcher.search(query, max_results=3)
        
        for r in results:
            print(f"  [{r.source}] {r.title[:50]}... (score: {r.relevance_score:.2f})")
            print(f"    concepts: {', '.join(r.matched_concepts)}")
    
    # Estatísticas
    print("\n" + "=" * 60)
    print(f"[Cache] {len(searcher.paper_cache)} papers")
    print(f"[Index] {len(searcher.concept_index.index)} concepts")
    print("=" * 60)


if __name__ == "__main__":
    main()