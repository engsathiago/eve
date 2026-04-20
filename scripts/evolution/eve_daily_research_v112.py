#!/usr/bin/env python3
"""
eve_daily_research_v112.py - Daily Research Integration

Integra ArXiv Research Agent v112 com o fluxo diário de evolução.
Executa pesquisa automática e gera training pairs.

Autor: Eve 🌙
Ciclo: #112
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Adicionar caminho para imports
sys.path.insert(0, '/root/evolution')

from eve_arxiv_researcher_v112 import EveArxivResearcher
from eve_offline_search_v112 import OfflineSearcher

def main():
    """Executa ciclo diário de pesquisa."""
    print("=" * 60)
    print("EVE DAILY RESEARCH v112 🌙")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Tentar pesquisa online primeiro
    print("\n[Phase 1] Online Research (arXiv API)")
    print("-" * 40)
    
    try:
        researcher = EveArxivResearcher()
        results = researcher.run_research_cycle()
        
        print(f"\n✅ Online research completed:")
        print(f"   Papers found: {results['papers_found']}")
        print(f"   New papers: {results['papers_new']}")
        print(f"   PDFs downloaded: {results['pdfs_downloaded']}")
        print(f"   Training pairs: {results['training_pairs_generated']}")
        
        online_success = results['papers_found'] > 0
        
    except Exception as e:
        print(f"\n⚠️  Online research failed: {e}")
        print("   Falling back to offline mode...")
        online_success = False
    
    # Fallback para offline se necessário
    if not online_success:
        print("\n[Phase 2] Offline Research (Local Cache)")
        print("-" * 40)
        
        try:
            offline = OfflineSearcher()
            
            # Queries padrão para pesquisa offline
            test_queries = [
                "memory systems",
                "autonomous learning",
                "agent architecture",
                "self-improvement"
            ]
            
            total_results = 0
            for query in test_queries:
                results = offline.search(query, max_results=3)
                total_results += len(results)
                print(f"   '{query}': {len(results)} results")
            
            print(f"\n✅ Offline research completed: {total_results} total results")
            
        except Exception as e:
            print(f"\n❌ Offline research also failed: {e}")
            print("   Database may be empty - run online mode first")
    
    # Estatísticas finais
    print("\n" + "=" * 60)
    print("[Summary]")
    print("=" * 60)
    
    try:
        researcher = EveArxivResearcher()
        stats = researcher.get_stats()
        
        print(f"Total papers in database: {stats['total_papers']}")
        print(f"Papers processed: {stats['papers_processed']}")
        print(f"Training pairs generated: {stats['training_pairs_generated']}")
        print(f"Dataset path: {stats['dataset_path']}")
        
        # Salvar log do ciclo
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle": 112,
            "online_success": online_success,
            "stats": stats
        }
        
        log_path = Path("/root/evolution/research_cache/daily_logs.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        print(f"\n📝 Log saved: {log_path}")
        
    except Exception as e:
        print(f"Could not retrieve stats: {e}")
    
    print("\n" + "=" * 60)
    print("Research cycle complete 🌙")
    print("=" * 60)

if __name__ == "__main__":
    main()
