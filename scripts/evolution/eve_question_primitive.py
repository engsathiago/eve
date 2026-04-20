#!/usr/bin/env python3
"""
eve_question_primitive.py — OIDA-based Question-as-Modeled-Ignorance

Implementa QUESTION primitive do paper OIDA (arXiv:2604.11759):
- Identificar lacunas de conhecimento explicitamente
- Inverse decay: questões não respondidas emergem com urgência crescente
- Integrar com KAIROS priority engine

Author: Eve (Autonomous Evolution Cycle #63)
Date: 2026-04-14
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

# Configurações
MEMORY_DIR = Path("/memory")
QUESTIONS_FILE = MEMORY_DIR / "corrective" / "questions.jsonl"
DECAY_CONFIG = {
    "initial_urgency": 1.0,
    "decay_rate": 0.95,  # Inverse decay = cresce com tempo
    "max_urgency": 10.0,
    "resolution_bonus": -5.0,  # Quando respondida
}


class QuestionPrimitive:
    """
    QUESTION-as-modeled-ignorance: representa explicitamente o que não sabemos.
    
    Comportamento:
    - Urgência inicial baixa (1.0)
    - Cresce com tempo (inverse decay: urgency *= 1/decay_rate)
    - Quando respondida: marcada como resolved, urgência → 0
    - Questões similares são agrupadas (deduplicação)
    """
    
    def __init__(self, questions_file: Path = QUESTIONS_FILE):
        self.questions_file = questions_file
        self.questions_file.parent.mkdir(parents=True, exist_ok=True)
        self.questions: List[Dict] = self._load_questions()
    
    def _load_questions(self) -> List[Dict]:
        """Carrega questões existentes do arquivo."""
        if not self.questions_file.exists():
            return []
        
        questions = []
        with open(self.questions_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    questions.append(json.loads(line))
        return questions
    
    def _save_questions(self):
        """Salva questões no arquivo."""
        with open(self.questions_file, 'w') as f:
            for q in self.questions:
                f.write(json.dumps(q, default=str) + '\n')
    
    def _compute_hash(self, text: str) -> str:
        """Computa hash para deduplicação de questões similares."""
        # Normaliza: lowercase, remove pontuação excessiva
        normalized = ' '.join(text.lower().split())[:100]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def add_question(
        self,
        question: str,
        context: str,
        source: str,
        category: str = "knowledge_gap",
        related_files: Optional[List[str]] = None
    ) -> str:
        """
        Adiciona uma nova questão ao sistema.
        
        Args:
            question: A pergunta explicitando a lacuna de conhecimento
            context: Contexto onde a questão surgiu
            source: Origem (autoDream, KAIROS, user_query, etc.)
            category: Tipo de questão (knowledge_gap, uncertainty, contradiction)
            related_files: Arquivos relacionados à questão
        
        Returns:
            ID da questão criada
        """
        q_hash = self._compute_hash(question)
        
        # Verifica se questão similar já existe
        for existing in self.questions:
            if existing['hash'] == q_hash and not existing.get('resolved'):
                print(f"[QUESTION] Questão similar já existe: {existing['id']}")
                return existing['id']
        
        question_id = f"Q-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{q_hash[:8]}"
        
        new_question = {
            'id': question_id,
            'hash': q_hash,
            'question': question,
            'context': context,
            'source': source,
            'category': category,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'urgency': DECAY_CONFIG['initial_urgency'],
            'resolved': False,
            'resolution': None,
            'resolution_source': None,
            'related_files': related_files or [],
            'references': []  # Links para research que a respondeu
        }
        
        self.questions.append(new_question)
        self._save_questions()
        
        print(f"[QUESTION] Adicionada: {question_id}")
        print(f"  Q: {question[:80]}...")
        print(f"  Urgência inicial: {DECAY_CONFIG['initial_urgency']}")
        
        return question_id
    
    def update_urgency(self):
        """
        Atualiza urgência de todas as questões não resolvidas.
        Inverse decay: urgência cresce com o tempo.
        """
        now = datetime.now()
        updated = 0
        
        for q in self.questions:
            if q.get('resolved'):
                continue
            
            created = datetime.fromisoformat(q['created_at'])
            days_open = (now - created).days
            
            # Inverse decay: urgência aumenta com tempo
            new_urgency = min(
                DECAY_CONFIG['initial_urgency'] * (1 / DECAY_CONFIG['decay_rate']) ** days_open,
                DECAY_CONFIG['max_urgency']
            )
            
            if new_urgency != q['urgency']:
                q['urgency'] = round(new_urgency, 2)
                q['updated_at'] = now.isoformat()
                updated += 1
        
        if updated > 0:
            self._save_questions()
            print(f"[QUESTION] {updated} questões tiveram urgência atualizada")
    
    def resolve_question(
        self,
        question_id: str,
        resolution: str,
        source: str,
        references: Optional[List[str]] = None
    ):
        """
        Marca uma questão como resolvida.
        
        Args:
            question_id: ID da questão
            resolution: Resposta/documento que resolve
            source: Origem da resolução (research_cycle, autoDream, etc.)
            references: Links para papers, arquivos, etc.
        """
        for q in self.questions:
            if q['id'] == question_id:
                q['resolved'] = True
                q['resolution'] = resolution
                q['resolution_source'] = source
                q['resolved_at'] = datetime.now().isoformat()
                q['urgency'] = 0.0
                q['references'] = references or []
                
                self._save_questions()
                print(f"[QUESTION] Resolvida: {question_id}")
                print(f"  Fonte: {source}")
                return True
        
        print(f"[QUESTION] ERRO: Questão não encontrada: {question_id}")
        return False
    
    def get_priority_questions(self, min_urgency: float = 3.0, limit: int = 10) -> List[Dict]:
        """
        Retorna questões prioritárias (urgência acima do threshold).
        
        Para integração com KAIROS: estas são tarefas de research prioritárias.
        """
        unresolved = [q for q in self.questions if not q.get('resolved')]
        by_urgency = sorted(unresolved, key=lambda x: x['urgency'], reverse=True)
        
        priority = [q for q in by_urgency if q['urgency'] >= min_urgency]
        return priority[:limit]
    
    def get_stats(self) -> Dict:
        """Estatísticas do sistema de questões."""
        total = len(self.questions)
        resolved = sum(1 for q in self.questions if q.get('resolved'))
        unresolved = total - resolved
        
        if unresolved > 0:
            avg_urgency = sum(q['urgency'] for q in self.questions if not q.get('resolved')) / unresolved
        else:
            avg_urgency = 0
        
        high_priority = len(self.get_priority_questions(min_urgency=5.0))
        
        return {
            'total': total,
            'resolved': resolved,
            'unresolved': unresolved,
            'avg_urgency_unresolved': round(avg_urgency, 2),
            'high_priority_count': high_priority,
            'categories': self._count_by_category()
        }
    
    def _count_by_category(self) -> Dict[str, int]:
        """Contagem por categoria."""
        counts = {}
        for q in self.questions:
            cat = q.get('category', 'unknown')
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    def generate_research_tasks(self) -> List[Dict]:
        """
        Gera tarefas de research para KAIROS baseadas em questões prioritárias.
        
        Retorna lista de dicts compatível com KAIROS task format.
        """
        priority = self.get_priority_questions(min_urgency=3.0, limit=5)
        
        tasks = []
        for q in priority:
            task = {
                'id': f"research-{q['id']}",
                'type': 'research',
                'description': f"Research: {q['question']}",
                'context': q['context'],
                'priority_score': q['urgency'],
                'source': 'question_primitive',
                'question_id': q['id'],
                'estimated_cycles': max(1, int(q['urgency'] / 2)),
                'category': q['category']
            }
            tasks.append(task)
        
        return tasks
    
    def export_for_training(self, output_file: Optional[Path] = None) -> Path:
        """
        Exporta questões resolvidas como dados de treino.
        
        Formato: instruction (questão) → response (resolução)
        """
        if output_file is None:
            output_file = Path("/root/evolution/training_data/questions_resolved.jsonl")
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        resolved = [q for q in self.questions if q.get('resolved') and q.get('resolution')]
        
        count = 0
        with open(output_file, 'w') as f:
            for q in resolved:
                training_pair = {
                    'instruction': q['question'],
                    'response': q['resolution'],
                    'context': q['context'],
                    'category': 'knowledge_gap',
                    'score': 85,  # Base score para pares de questões
                    'metadata': {
                        'question_id': q['id'],
                        'source': q['source'],
                        'resolution_source': q['resolution_source'],
                        'references': q.get('references', [])
                    }
                }
                f.write(json.dumps(training_pair) + '\n')
                count += 1
        
        print(f"[QUESTION] Exportadas {count} questões resolvidas para treino")
        return output_file


def main():
    """CLI para gerenciamento de questões."""
    import argparse
    
    parser = argparse.ArgumentParser(description='OIDA Question Primitive')
    subparsers = parser.add_subparsers(dest='command')
    
    # Add
    add_parser = subparsers.add_parser('add', help='Adicionar questão')
    add_parser.add_argument('question', help='Texto da questão')
    add_parser.add_argument('--context', default='', help='Contexto')
    add_parser.add_argument('--source', default='manual', help='Origem')
    add_parser.add_argument('--category', default='knowledge_gap', 
                           choices=['knowledge_gap', 'uncertainty', 'contradiction'])
    
    # List
    list_parser = subparsers.add_parser('list', help='Listar questões')
    list_parser.add_argument('--priority', action='store_true', help='Só prioritárias')
    list_parser.add_argument('--limit', type=int, default=20)
    
    # Stats
    subparsers.add_parser('stats', help='Estatísticas')
    
    # Update
    subparsers.add_parser('update', help='Atualizar urgência')
    
    # Resolve
    resolve_parser = subparsers.add_parser('resolve', help='Resolver questão')
    resolve_parser.add_argument('question_id', help='ID da questão')
    resolve_parser.add_argument('resolution', help='Resolução')
    resolve_parser.add_argument('--source', default='manual')
    
    # Export
    subparsers.add_parser('export', help='Exportar para treino')
    
    args = parser.parse_args()
    
    qp = QuestionPrimitive()
    
    if args.command == 'add':
        qp.add_question(
            question=args.question,
            context=args.context,
            source=args.source,
            category=args.category
        )
    
    elif args.command == 'list':
        if args.priority:
            questions = qp.get_priority_questions(limit=args.limit)
        else:
            questions = sorted(
                [q for q in qp.questions if not q.get('resolved')],
                key=lambda x: x['urgency'],
                reverse=True
            )[:args.limit]
        
        for q in questions:
            status = "✓" if q.get('resolved') else f"⚠ U{q['urgency']}"
            print(f"{status} [{q['id']}] {q['question'][:60]}...")
    
    elif args.command == 'stats':
        stats = qp.get_stats()
        print("\n=== Estatísticas de Questões ===")
        print(f"Total: {stats['total']}")
        print(f"Resolvidas: {stats['resolved']}")
        print(f"Pendentes: {stats['unresolved']}")
        print(f"Urgência média (pendentes): {stats['avg_urgency_unresolved']}")
        print(f"Alta prioridade (≥5.0): {stats['high_priority_count']}")
        print("\nPor categoria:")
        for cat, count in stats['categories'].items():
            print(f"  {cat}: {count}")
    
    elif args.command == 'update':
        qp.update_urgency()
    
    elif args.command == 'resolve':
        qp.resolve_question(args.question_id, args.resolution, args.source)
    
    elif args.command == 'export':
        qp.export_for_training()
    
    else:
        # Atualiza urgência por padrão
        qp.update_urgency()
        stats = qp.get_stats()
        print(f"[QUESTION] {stats['unresolved']} questões pendentes, "
              f"{stats['high_priority_count']} alta prioridade")


if __name__ == "__main__":
    main()
