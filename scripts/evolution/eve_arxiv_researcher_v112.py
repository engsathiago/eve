#!/usr/bin/env python3
"""
eve_arxiv_researcher_v112.py - ArXiv Research Agent

Busca, baixa e analisa papers do arXiv sem necessidade de API key.
Converte automaticamente em training pairs para o dataset Eve.

Autor: Eve 🌙
Ciclo: #112
Data: 2026-04-20
"""

import os
import sys
import json
import sqlite3
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import quote

# Configurações
RESEARCH_DIR = Path("/root/evolution/research_cache")
DB_PATH = RESEARCH_DIR / "research_papers.db"
DATASET_OUTPUT = Path("/backup_pc/eve_dataset/arxiv_training_pairs.jsonl")
MAX_PAPERS_PER_QUERY = 10
REQUEST_TIMEOUT = 30

@dataclass
class Paper:
    """Representa um paper do arXiv."""
    arxiv_id: str
    title: str
    authors: List[str]
    summary: str
    published: str
    primary_category: str
    pdf_url: str
    local_path: Optional[str] = None
    embedding_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def hash(self) -> str:
        """Gera hash único para deduplicação."""
        content = f"{self.arxiv_id}:{self.title}"
        return hashlib.md5(content.encode()).hexdigest()


class ResearchDatabase:
    """SQLite database para cache de papers."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Cria tabelas se não existirem."""
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    arxiv_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    authors TEXT,  -- JSON array
                    summary TEXT,
                    published TEXT,
                    primary_category TEXT,
                    pdf_url TEXT,
                    local_path TEXT,
                    embedding_id TEXT,
                    downloaded_at TEXT,
                    analyzed_at TEXT,
                    training_pairs_generated INTEGER DEFAULT 0,
                    metadata TEXT  -- JSON extra
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    results_count INTEGER,
                    max_results INTEGER
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON papers(primary_category);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_downloaded ON papers(downloaded_at);
            """)
    
    def save_paper(self, paper: Paper) -> bool:
        """Salva paper no banco. Retorna False se já existe."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO papers 
                    (id, arxiv_id, title, authors, summary, published, 
                     primary_category, pdf_url, local_path, embedding_id, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper.hash(),
                    paper.arxiv_id,
                    paper.title,
                    json.dumps(paper.authors),
                    paper.summary,
                    paper.published,
                    paper.primary_category,
                    paper.pdf_url,
                    paper.local_path,
                    paper.embedding_id,
                    datetime.now().isoformat()
                ))
                return conn.total_changes > 0
        except Exception as e:
            print(f"[ERROR] Falha ao salvar paper: {e}")
            return False
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """Recupera paper pelo ID do arXiv."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", 
                (arxiv_id,)
            ).fetchone()
            
            if row:
                return Paper(
                    arxiv_id=row[1],
                    title=row[2],
                    authors=json.loads(row[3]),
                    summary=row[4],
                    published=row[5],
                    primary_category=row[6],
                    pdf_url=row[7],
                    local_path=row[8],
                    embedding_id=row[9]
                )
        return None
    
    def get_uncategorized_papers(self, limit: int = 10) -> List[Paper]:
        """Retorna papers que ainda não geraram training pairs."""
        papers = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT arxiv_id, title, authors, summary, published, 
                    primary_category, pdf_url, local_path, embedding_id
                    FROM papers WHERE training_pairs_generated = 0 
                    LIMIT ?""",
                (limit,)
            ).fetchall()
            
            for row in rows:
                papers.append(Paper(*row))
        return papers
    
    def mark_as_processed(self, arxiv_id: str, pairs_count: int):
        """Marca paper como processado."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE papers SET training_pairs_generated = ?,
                    analyzed_at = ? WHERE arxiv_id = ?""",
                (pairs_count, datetime.now().isoformat(), arxiv_id)
            )


class ArXivClient:
    """Cliente HTTP para arXiv API (não requer API key)."""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EveResearchBot/112 (research@eve.local)"
        })
    
    def search(
        self, 
        query: str, 
        max_results: int = MAX_PAPERS_PER_QUERY,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending"
    ) -> List[Paper]:
        """Busca papers no arXiv."""
        
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order
        }
        
        try:
            response = self.session.get(
                self.BASE_URL, 
                params=params, 
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return self._parse_feed(response.text)
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Falha na busca: {e}")
            return []
    
    def _parse_feed(self, xml_content: str) -> List[Paper]:
        """Parse do XML do arXiv."""
        papers = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Namespace do Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            
            for entry in root.findall("atom:entry", ns):
                arxiv_id = entry.find("atom:id", ns)
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)
                
                if not all([arxiv_id, title, summary, published]):
                    continue
                
                # Extrair ID curto do arXiv
                arxiv_id_text = arxiv_id.text.split("/")[-1]
                
                # Autores
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text)
                
                # Categoria primária
                category = entry.find("atom:category", ns)
                primary_category = category.get("term") if category else "unknown"
                
                # Links
                pdf_url = None
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href")
                        break
                
                if pdf_url:
                    papers.append(Paper(
                        arxiv_id=arxiv_id_text,
                        title=title.text.strip(),
                        authors=authors,
                        summary=summary.text.strip(),
                        published=published.text[:10],  # YYYY-MM-DD
                        primary_category=primary_category,
                        pdf_url=pdf_url
                    ))
                    
        except ET.ParseError as e:
            print(f"[ERROR] Falha ao parse XML: {e}")
        
        return papers
    
    def download_pdf(self, paper: Paper) -> Optional[Path]:
        """Baixa PDF do paper."""
        if not paper.pdf_url:
            return None
        
        pdf_path = RESEARCH_DIR / "pdfs" / f"{paper.arxiv_id}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        if pdf_path.exists():
            print(f"[INFO] PDF já existe: {pdf_path}")
            return pdf_path
        
        try:
            response = self.session.get(paper.pdf_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            
            print(f"[INFO] Download concluído: {pdf_path} ({len(response.content)} bytes)")
            return pdf_path
            
        except Exception as e:
            print(f"[ERROR] Falha no download: {e}")
            return None


class TrainingPairGenerator:
    """Gera training pairs a partir de papers analisados."""
    
    TEMPLATES = {
        "paper_summary": {
            "instruction": "Summarize the key findings of this research paper in 3-4 sentences.",
            "input_template": "Paper: {title}\n\nAbstract: {summary}"
        },
        "paper_relevance": {
            "instruction": "Explain why this paper matters for AI autonomy research.",
            "input_template": "Paper: {title}\nCategory: {category}\n\nAbstract: {summary}"
        },
        "methodology_extraction": {
            "instruction": "What methodology or approach does this paper propose?",
            "input_template": "Paper: {title}\nAuthors: {authors}\n\nAbstract: {summary}"
        },
        "criticism_simulation": {
            "instruction": "What are potential limitations or critiques of this work?",
            "input_template": "Paper: {title}\nCategory: {category}\n\nAbstract: {summary}"
        }
    }
    
    def generate_pairs(self, paper: Paper) -> List[Dict]:
        """Gera múltiplos training pairs de um paper."""
        pairs = []
        
        for template_name, template in self.TEMPLATES.items():
            pair = self._create_pair(paper, template_name, template)
            if pair:
                pairs.append(pair)
        
        return pairs
    
    def _create_pair(
        self, 
        paper: Paper, 
        template_name: str, 
        template: Dict
    ) -> Optional[Dict]:
        """Cria um único training pair."""
        
        input_text = template["input_template"].format(
            title=paper.title,
            summary=paper.summary[:500],  # Limitar tamanho
            category=paper.primary_category,
            authors=", ".join(paper.authors[:3])  # Top 3 autores
        )
        
        # Geração de resposta baseada no template
        if template_name == "paper_summary":
            response = self._generate_summary_response(paper)
        elif template_name == "paper_relevance":
            response = self._generate_relevance_response(paper)
        elif template_name == "methodology_extraction":
            response = self._generate_methodology_response(paper)
        elif template_name == "criticism_simulation":
            response = self._generate_criticism_response(paper)
        else:
            return None
        
        return {
            "instruction": template["instruction"],
            "input": input_text,
            "output": response,
            "metadata": {
                "source": "arxiv",
                "arxiv_id": paper.arxiv_id,
                "category": paper.primary_category,
                "template": template_name,
                "generated_at": datetime.now().isoformat(),
                "quality_score": 75  # Base score, pode ser ajustado
            }
        }
    
    def _generate_summary_response(self, paper: Paper) -> str:
        """Gera resposta de sumarização."""
        sentences = paper.summary.split(". ")
        if len(sentences) >= 3:
            return ". ".join(sentences[:3]) + "."
        return paper.summary
    
    def _generate_relevance_response(self, paper: Paper) -> str:
        """Gera resposta sobre relevância para AI autonomy."""
        relevance_map = {
            "cs.AI": "This paper contributes to artificial intelligence theory",
            "cs.LG": "This machine learning research has implications for autonomous systems",
            "cs.CL": "This computational linguistics work impacts natural language understanding",
            "cs.RO": "This robotics research directly advances physical autonomy",
            "cs.SE": "This software engineering work improves system reliability"
        }
        
        base = relevance_map.get(
            paper.primary_category.split(".")[0],
            "This research has potential implications for autonomous systems"
        )
        
        return f"{base}. The work on '{paper.title[:60]}...' provides techniques that could be adapted for self-improving AI architectures."
    
    def _generate_methodology_response(self, paper: Paper) -> str:
        """Extrai metodologia do abstract."""
        # Heurística simples: procurar por frases que descrevem abordagem
        return f"Based on the abstract, this paper appears to propose: {paper.summary[:200]}..."
    
    def _generate_criticism_response(self, paper: Paper) -> str:
        """Gera críticas simuladas."""
        return f"Potential limitations include: (1) Scope may be limited to specific domains, (2) Evaluation metrics may not capture real-world complexity, (3) Scalability to larger systems is unverified. Full critique requires reading the complete paper."


class EveArxivResearcher:
    """Sistema completo de pesquisa arXiv."""
    
    # Queries rotativas para pesquisa contínua
    RESEARCH_QUERIES = [
        "cat:cs.AI AND autonomous agents",
        "cat:cs.LG AND self-improving",
        "cat:cs.CL AND long-term memory",
        "cat:cs.SE AND code generation",
        "cat:cs.AI AND reasoning",
        "cat:cs.RO AND decision making",
        "cat:cs.CY AND safety",
        "cat:cs.AI AND multi-agent"
    ]
    
    def __init__(self):
        self.db = ResearchDatabase()
        self.client = ArXivClient()
        self.generator = TrainingPairGenerator()
    
    def run_research_cycle(self, query_index: Optional[int] = None) -> Dict:
        """Executa um ciclo completo de pesquisa."""
        
        # Selecionar query
        if query_index is None:
            query_index = datetime.now().hour % len(self.RESEARCH_QUERIES)
        
        query = self.RESEARCH_QUERIES[query_index % len(self.RESEARCH_QUERIES)]
        
        print(f"[CYCLE] Iniciando pesquisa: '{query}'")
        
        results = {
            "query": query,
            "papers_found": 0,
            "papers_new": 0,
            "pdfs_downloaded": 0,
            "training_pairs_generated": 0,
            "errors": []
        }
        
        # 1. Buscar papers
        try:
            papers = self.client.search(query)
            results["papers_found"] = len(papers)
            print(f"[INFO] {len(papers)} papers encontrados")
        except Exception as e:
            results["errors"].append(f"Search failed: {e}")
            return results
        
        # 2. Salvar novos papers
        for paper in papers:
            if self.db.save_paper(paper):
                results["papers_new"] += 1
                print(f"[NEW] {paper.arxiv_id}: {paper.title[:60]}...")
        
        # 3. Baixar PDFs dos novos papers
        for paper in papers[:3]:  # Limitar a 3 para não sobrecarregar
            existing = self.db.get_paper_by_arxiv_id(paper.arxiv_id)
            if existing and not existing.local_path:
                pdf_path = self.client.download_pdf(paper)
                if pdf_path:
                    results["pdfs_downloaded"] += 1
        
        # 4. Gerar training pairs para papers não processados
        unprocessed = self.db.get_uncategorized_papers(limit=5)
        all_pairs = []
        
        for paper in unprocessed:
            pairs = self.generator.generate_pairs(paper)
            all_pairs.extend(pairs)
            self.db.mark_as_processed(paper.arxiv_id, len(pairs))
            print(f"[GEN] {len(pairs)} pairs de {paper.arxiv_id}")
        
        results["training_pairs_generated"] = len(all_pairs)
        
        # 5. Salvar pares
        if all_pairs:
            self._save_training_pairs(all_pairs)
        
        return results
    
    def _save_training_pairs(self, pairs: List[Dict]):
        """Salva training pairs em arquivo."""
        DATASET_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        
        with open(DATASET_OUTPUT, "a", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        
        print(f"[SAVE] {len(pairs)} pairs → {DATASET_OUTPUT}")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do sistema."""
        with sqlite3.connect(self.db.db_path) as conn:
            total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            total_processed = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE training_pairs_generated > 0"
            ).fetchone()[0]
            total_pairs = conn.execute(
                "SELECT SUM(training_pairs_generated) FROM papers"
            ).fetchone()[0] or 0
            
        return {
            "total_papers": total_papers,
            "papers_processed": total_processed,
            "training_pairs_generated": total_pairs,
            "db_path": str(self.db.db_path),
            "dataset_path": str(DATASET_OUTPUT)
        }


def main():
    """Entry point."""
    print("=" * 60)
    print("EVE ARXIV RESEARCHER v112 🌙")
    print("Autonomous research without API keys")
    print("=" * 60)
    
    researcher = EveArxivResearcher()
    
    # Modo de execução
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            stats = researcher.get_stats()
            print("\n[STATS]")
            for k, v in stats.items():
                print(f"  {k}: {v}")
            return
        
        elif sys.argv[1] == "query" and len(sys.argv) > 2:
            # Pesquisa customizada
            query = " ".join(sys.argv[2:])
            print(f"\n[Custom query]: {query}")
            papers = researcher.client.search(query)
            for p in papers[:5]:
                print(f"  - {p.arxiv_id}: {p.title[:70]}...")
            return
    
    # Ciclo padrão
    print("\n[Executing research cycle...]")
    results = researcher.run_research_cycle()
    
    print("\n" + "=" * 60)
    print("[RESULTS]")
    for k, v in results.items():
        if k != "errors":
            print(f"  {k}: {v}")
    
    if results["errors"]:
        print("\n[ERRORS]")
        for e in results["errors"]:
            print(f"  ! {e}")
    
    # Stats finais
    stats = researcher.get_stats()
    print(f"\n[Database] {stats['total_papers']} papers | {stats['training_pairs_generated']} pairs")
    print("=" * 60)


if __name__ == "__main__":
    main()