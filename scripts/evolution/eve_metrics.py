#!/usr/bin/env python3
"""
eve_metrics.py - Sistema de Métricas para Auto-Avaliação
Inspirado em DSPy: compilador otimiza pipelines para métricas específicas
Ciclo #72 - Implementação de verification layer (QUESTION D-003)

Responsabilidades:
1. Definir métricas para cada módulo do sistema Eve
2. Calcular scores antes/depois de modificações
3. Detectar regressões automaticamente (QUESTION S-004)
4. Fornecer feedback estruturado para autoDream
"""

import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/root/evolution/logs/eve_metrics.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('eve_metrics')


def get_timestamp() -> str:
    """Retorna timestamp UTC ISO format"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MetricResult:
    """Resultado de uma métrica computada"""
    name: str
    score: float  # 0-100
    weight: float  # Importância relativa
    details: Dict[str, Any]
    timestamp: str
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class ModuleMetrics:
    """Métricas agregadas para um módulo"""
    module_name: str
    version: str
    overall_score: float
    metrics: List[MetricResult]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'module_name': self.module_name,
            'version': self.version,
            'overall_score': self.overall_score,
            'metrics': [asdict(m) for m in self.metrics],
            'timestamp': self.timestamp
        }


class MetricsDatabase:
    """Persistência de métricas em SQLite"""
    
    def __init__(self, db_path: str = '/root/evolution/metrics.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa schema do banco"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_name TEXT NOT NULL,
                version TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                score REAL NOT NULL,
                weight REAL NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_name TEXT NOT NULL,
                version TEXT NOT NULL,
                overall_score REAL NOT NULL,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_metric(self, module_name: str, version: str, metric: MetricResult):
        """Armazena métrica individual"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO metrics (module_name, version, metric_name, score, weight, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (module_name, version, metric.name, metric.score, metric.weight, 
              json.dumps(metric.details), metric.timestamp))
        
        conn.commit()
        conn.close()
    
    def store_module_score(self, module_name: str, version: str, overall_score: float, timestamp: str):
        """Armazena score agregado do módulo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO module_scores (module_name, version, overall_score, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (module_name, version, overall_score, timestamp))
        
        conn.commit()
        conn.close()
    
    def get_module_history(self, module_name: str, limit: int = 10) -> List[Dict]:
        """Recupera histórico de scores de um módulo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT version, overall_score, timestamp
            FROM module_scores
            WHERE module_name = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (module_name, limit))
        
        results = [{'version': row[0], 'score': row[1], 'timestamp': row[2]} 
                   for row in cursor.fetchall()]
        conn.close()
        return results
    
    def detect_regression(self, module_name: str, current_score: float, 
                         threshold: float = 5.0) -> Optional[Dict]:
        """Detecta regressão comparando com versão anterior"""
        history = self.get_module_history(module_name, limit=2)
        
        if len(history) < 2:
            return None
        
        previous_score = history[1]['score']  # Segunda entrada (mais recente antes da atual)
        delta = current_score - previous_score
        
        if delta < -threshold:
            return {
                'regression_detected': True,
                'previous_score': previous_score,
                'current_score': current_score,
                'delta': delta,
                'severity': 'high' if delta < -10 else 'medium'
            }
        
        return None


class MetricsEngine:
    """Motor de avaliação de métricas - inspirado em DSPy compiler"""
    
    def __init__(self):
        self.db = MetricsDatabase()
        self.metric_functions: Dict[str, Callable] = {}
        self._register_default_metrics()
    
    def _register_default_metrics(self):
        """Registra métricas padrão do sistema Eve"""
        
        # Métricas para autoDream
        self.register_metric('autodream_quality', self._eval_autodream_quality)
        self.register_metric('autodream_coverage', self._eval_autodream_coverage)
        self.register_metric('autodream_consistency', self._eval_autodream_consistency)
        
        # Métricas para KAIROS
        self.register_metric('kairos_precision', self._eval_kairos_precision)
        self.register_metric('kairos_coverage', self._eval_kairos_coverage)
        
        # Métricas para Memory System
        self.register_metric('memory_retrieval', self._eval_memory_retrieval)
        self.register_metric('memory_compression', self._eval_memory_compression)
    
    def register_metric(self, name: str, func: Callable):
        """Registra função de métrica personalizada"""
        self.metric_functions[name] = func
    
    def evaluate_module(self, module_name: str, version: str, 
                       context: Optional[Dict] = None) -> ModuleMetrics:
        """Avalia todas as métricas de um módulo"""
        
        metrics = []
        total_weight = 0
        weighted_sum = 0
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Seleciona métricas relevantes para o módulo
        relevant_metrics = [k for k in self.metric_functions.keys() 
                           if k.startswith(module_name.lower())]
        
        for metric_name in relevant_metrics:
            func = self.metric_functions[metric_name]
            try:
                result = func(context or {})
                if result:
                    result.timestamp = timestamp
                    metrics.append(result)
                    weighted_sum += result.weighted_score
                    total_weight += result.weight
                    
                    # Persiste métrica individual
                    self.db.store_metric(module_name, version, result)
            except Exception as e:
                logger.error(f"Erro avaliando métrica {metric_name}: {e}")
        
        # Calcula score agregado
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        
        module_metrics = ModuleMetrics(
            module_name=module_name,
            version=version,
            overall_score=overall_score,
            metrics=metrics,
            timestamp=timestamp
        )
        
        # Persiste score agregado
        self.db.store_module_score(module_name, version, overall_score, timestamp)
        
        # Verifica regressão
        regression = self.db.detect_regression(module_name, overall_score)
        if regression:
            logger.warning(f"REGRESSÃO DETECTADA em {module_name}: {regression}")
        
        return module_metrics
    
    # === IMPLEMENTAÇÕES DE MÉTRICAS ===
    
    def _eval_autodream_quality(self, context: Dict) -> MetricResult:
        """Avalia qualidade dos insights gerados pelo autoDream"""
        
        # Lê último synthesis para avaliar
        synthesis_path = Path('/root/evolution/SYNTHESIS_MASTER.md')
        if not synthesis_path.exists():
            return MetricResult(
                name='insight_quality',
                score=50.0,
                weight=0.4,
                details={'error': 'SYNTHESIS_MASTER.md não encontrado'},
                timestamp=''
            )
        
        content = synthesis_path.read_text()
        
        # Heurísticas de qualidade
        score = 50.0
        details = {}
        
        # Presença de estrutura (ciclos documentados)
        cycle_count = content.count('### Ciclo #')
        details['cycles_documented'] = cycle_count
        if cycle_count > 0:
            score += 10
        
        # Presença de action items
        action_count = content.count('**Action')
        details['action_items'] = action_count
        if action_count > 0:
            score += 10
        
        # Presença de métricas
        metric_refs = content.count('score') + content.count('Score')
        details['metric_references'] = metric_refs
        if metric_refs > 5:
            score += 10
        
        # Comprimento indicativo de profundidade
        details['content_length'] = len(content)
        if len(content) > 50000:
            score += 10
        
        # Cap em 100
        score = min(100, score)
        
        return MetricResult(
            name='insight_quality',
            score=score,
            weight=0.4,
            details=details,
            timestamp=''
        )
    
    def _eval_autodream_coverage(self, context: Dict) -> MetricResult:
        """Avalia cobertura de tópicos do autoDream"""
        
        # Verifica se QUESTIONS.md está sendo coberto
        questions_path = Path('/memory/QUESTIONS.md')
        if not questions_path.exists():
            return MetricResult(
                name='question_coverage',
                score=50.0,
                weight=0.3,
                details={'error': 'QUESTIONS.md não encontrado'},
                timestamp=''
            )
        
        questions_content = questions_path.read_text()
        
        # Conta questões e respostas/resoluções
        total_questions = questions_content.count('| Q-') + questions_content.count('| O-') + \
                          questions_content.count('| T-') + questions_content.count('| A-')
        
        # Questões em RESOLVED/
        resolved_count = questions_content.count('## RESOLVED/')
        
        coverage = (resolved_count / max(1, total_questions)) * 100
        
        return MetricResult(
            name='question_coverage',
            score=min(100, coverage + 50),  # Base de 50 + progresso
            weight=0.3,
            details={
                'total_questions': total_questions,
                'resolved': resolved_count,
                'coverage_pct': coverage
            },
            timestamp=''
        )
    
    def _eval_autodream_consistency(self, context: Dict) -> MetricResult:
        """Avalia consistência temporal do autoDream"""
        
        # Verifica se há gaps nas sínteses
        import glob
        synthesis_files = glob.glob('/root/evolution/synthesis_*.md')
        
        if len(synthesis_files) < 2:
            return MetricResult(
                name='consistency',
                score=50.0,
                weight=0.3,
                details={'synthesis_count': len(synthesis_files)},
                timestamp=''
            )
        
        # Ordena por data
        synthesis_files.sort()
        
        # Verifica consistência (todos têm conteúdo significativo)
        consistent_count = 0
        for f in synthesis_files[-5:]:  # Últimos 5
            content = Path(f).read_text()
            if len(content) > 1000 and '### Ciclo' in content:
                consistent_count += 1
        
        score = (consistent_count / 5) * 100
        
        return MetricResult(
            name='consistency',
            score=score,
            weight=0.3,
            details={
                'recent_syntheses': len(synthesis_files[-5:]),
                'consistent': consistent_count
            },
            timestamp=''
        )
    
    def _eval_kairos_precision(self, context: Dict) -> MetricResult:
        """Avalia precisão das prioridades do KAIROS"""
        
        # Verifica improvements_pending.md
        pending_path = Path('/root/evolution/improvements_pending.md')
        if not pending_path.exists():
            return MetricResult(
                name='priority_precision',
                score=50.0,
                weight=0.5,
                details={'error': 'improvements_pending.md não encontrado'},
                timestamp=''
            )
        
        content = pending_path.read_text()
        
        # Heurísticas de qualidade de priorização
        score = 50.0
        
        # Presença de scores UCB
        ucb_count = content.count('UCB')
        if ucb_count > 0:
            score += 20
        
        # Presença de prioridades explícitas
        priority_count = content.count('Prioridade') + content.count('priority')
        if priority_count > 0:
            score += 15
        
        # Presença de ROI estimado
        roi_count = content.count('ROI')
        if roi_count > 0:
            score += 15
        
        return MetricResult(
            name='priority_precision',
            score=min(100, score),
            weight=0.5,
            details={
                'ucb_references': ucb_count,
                'priority_mentions': priority_count,
                'roi_references': roi_count
            },
            timestamp=''
        )
    
    def _eval_kairos_coverage(self, context: Dict) -> MetricResult:
        """Avalia cobertura de domínios do KAIROS"""
        
        # Verifica se cobre todos os módulos
        modules = ['autodream', 'memory', 'learning', 'self_improve']
        covered = 0
        
        pending_path = Path('/root/evolution/improvements_pending.md')
        if pending_path.exists():
            content = pending_path.read_text().lower()
            for mod in modules:
                if mod in content:
                    covered += 1
        
        score = (covered / len(modules)) * 100
        
        return MetricResult(
            name='domain_coverage',
            score=score,
            weight=0.5,
            details={
                'modules_total': len(modules),
                'modules_covered': covered
            },
            timestamp=''
        )
    
    def _eval_memory_retrieval(self, context: Dict) -> MetricResult:
        """Avalia qualidade de recuperação de memória"""
        
        # Verifica ChromaDB
        try:
            import subprocess
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:8000/api/v1/collections'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return MetricResult(
                    name='retrieval_availability',
                    score=90.0,
                    weight=0.5,
                    details={'chroma_status': 'available'},
                    timestamp=''
                )
            else:
                return MetricResult(
                    name='retrieval_availability',
                    score=30.0,
                    weight=0.5,
                    details={'chroma_status': 'unavailable'},
                    timestamp=''
                )
        except Exception as e:
            return MetricResult(
                name='retrieval_availability',
                score=30.0,
                weight=0.5,
                details={'error': str(e)},
                timestamp=''
            )
    
    def _eval_memory_compression(self, context: Dict) -> MetricResult:
        """Avalia eficiência de compressão de memória"""
        
        # Verifica se context_compressor existe
        compressor_path = Path('/root/evolution/eve_context_compressor.py')
        
        if compressor_path.exists():
            return MetricResult(
                name='compression_available',
                score=85.0,
                weight=0.5,
                details={'compressor_exists': True},
                timestamp=''
            )
        else:
            return MetricResult(
                name='compression_available',
                score=20.0,
                weight=0.5,
                details={'compressor_exists': False},
                timestamp=''
            )


def main():
    """Entry point para execução via cron/CLI"""
    
    engine = MetricsEngine()
    
    # Avalia módulos principais
    modules = ['autoDream', 'KAIROS', 'Memory']
    
    results_summary = []
    
    for module in modules:
        logger.info(f"Avaliando módulo: {module}")
        
        # Pega versão do módulo (do próprio arquivo ou registry)
        version = 'v18' if module == 'autoDream' else 'v15' if module == 'KAIROS' else 'v1'
        
        metrics = engine.evaluate_module(module, version)
        
        logger.info(f"Score {module}: {metrics.overall_score:.2f}")
        
        for m in metrics.metrics:
            logger.info(f"  - {m.name}: {m.score:.2f} (weight: {m.weight})")
        
        results_summary.append({
            'module': module,
            'version': version,
            'score': metrics.overall_score,
            'timestamp': metrics.timestamp
        })
    
    # Salva resumo
    summary_path = Path('/root/evolution/metrics_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    logger.info(f"Resumo salvo em {summary_path}")
    
    return results_summary


if __name__ == '__main__':
    main()
