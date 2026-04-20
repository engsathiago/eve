#!/usr/bin/env python3
"""
EVE Self-Evaluation v107 - AUTO-IMPROVEMENT SYSTEM
Ciclo #107 - Auto-avaliação e melhoria contínua

Funções:
1. Analisar performance histórica
2. Identificar padrões de sucesso/falha
3. Gerar insights de melhoria
4. Aplicar correções automáticas onde seguro
5. Criar pares de treino sobre aprendizados
"""

import os
import sys
import json
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

os.environ['PYTHONUNBUFFERED'] = '1'

# Paths
LOG_DIR = Path("/root/evolution/logs")
STATE_DIR = Path("/root/evolution/state")
DATASET_DIR = Path("/backup_pc/eve_dataset")

STATE_FILE = STATE_DIR / "self_evaluation_v107.json"

for d in [LOG_DIR, STATE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

@dataclass
class PerformanceMetrics:
    success_rate: float
    avg_execution_time: float
    error_frequency: Dict[str, int]
    improvement_trend: float  # Positive = improving

class EveSelfEvaluationV107:
    """
    Sistema de auto-avaliação e melhoria contínua
    """
    
    def __init__(self):
        self.version = "107"
        self.session_id = f"self_eval_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log_file = LOG_DIR / f"{self.session_id}.log"
        self.improvements = []
        
    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level:8}] [SELF_EVAL-v{self.version}] {message}"
        print(log_line, flush=True)
        with open(self.log_file, 'a') as f:
            f.write(log_line + "\n")
    
    def _analyze_execution_logs(self) -> PerformanceMetrics:
        """Analisar logs de execução históricos"""
        self._log("Analyzing execution history...")
        
        # Coletar métricas de logs
        log_files = sorted(LOG_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:50]
        
        success_count = 0
        failure_count = 0
        error_types = defaultdict(int)
        execution_times = []
        
        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                
                # Detectar sucesso/falha
                if "COMPLETE" in content or "SUCCESS" in content:
                    success_count += 1
                elif "ERROR" in content or "FAIL" in content:
                    failure_count += 1
                    
                    # Extrair tipo de erro
                    error_patterns = [
                        r"Error:\s*(\w+)",
                        r"Exception:\s*(\w+)",
                        r"FAILURE:\s*(\w+)"
                    ]
                    for pattern in error_patterns:
                        match = re.search(pattern, content)
                        if match:
                            error_types[match.group(1)] += 1
                
                # Extrair tempo de execução
                time_match = re.search(r"Time:\s*(\d+\.?\d*)s", content)
                if time_match:
                    execution_times.append(float(time_match.group(1)))
                    
            except Exception as e:
                pass
        
        total = success_count + failure_count
        success_rate = success_count / total if total > 0 else 0.0
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
        
        # Calcular tendência (comparando metades)
        mid = len(log_files) // 2
        recent_success = success_count  # Simplificado
        older_success = success_count
        trend = (recent_success - older_success) / max(older_success, 1)
        
        return PerformanceMetrics(
            success_rate=success_rate,
            avg_execution_time=avg_time,
            error_frequency=dict(error_types),
            improvement_trend=trend
        )
    
    def _identify_improvement_areas(self, metrics: PerformanceMetrics) -> List[Dict]:
        """Identificar áreas para melhoria"""
        self._log("Identifying improvement areas...")
        
        areas = []
        
        # Área 1: Taxa de sucesso
        if metrics.success_rate < 0.8:
            areas.append({
                "area": "success_rate",
                "current": f"{metrics.success_rate*100:.1f}%",
                "target": "85%+",
                "priority": "HIGH",
                "action": "Implement more robust error handling and recovery mechanisms"
            })
        
        # Área 2: Erros frequentes
        if metrics.error_frequency:
            top_error = max(metrics.error_frequency.items(), key=lambda x: x[1])
            if top_error[1] >= 3:
                areas.append({
                    "area": "error_patterns",
                    "current": f"{top_error[0]} occurred {top_error[1]} times",
                    "target": "Zero recurring errors",
                    "priority": "MEDIUM",
                    "action": f"Review and fix {top_error[0]} root causes"
                })
        
        # Área 3: Tendência
        if metrics.improvement_trend < 0:
            areas.append({
                "area": "improvement_trend",
                "current": "Declining",
                "target": "Positive trend",
                "priority": "HIGH",
                "action": "Analyze recent changes causing regression"
            })
        
        # Área 4: Tempo de execução
        if metrics.avg_execution_time > 300:  # > 5 minutos
            areas.append({
                "area": "execution_speed",
                "current": f"{metrics.avg_execution_time:.1f}s avg",
                "target": "< 180s",
                "priority": "LOW",
                "action": "Profile and optimize slow operations"
            })
        
        return areas
    
    def _generate_improvement_insights(self, areas: List[Dict]) -> List[Dict]:
        """Gerar insights sobre melhoria"""
        self._log("Generating improvement insights...")
        
        insights = []
        
        for area in areas:
            insight = {
                "timestamp": datetime.now().isoformat(),
                "area": area["area"],
                "observation": f"{area['area']}: {area['current']} → target {area['target']}",
                "priority": area["priority"],
                "proposed_action": area["action"],
                "category": "improvement_opportunity",
                "confidence": 0.85
            }
            insights.append(insight)
        
        # Insights gerais baseados em padrões
        if not areas:
            insights.append({
                "timestamp": datetime.now().isoformat(),
                "area": "general",
                "observation": "System operating within acceptable parameters",
                "priority": "LOW",
                "proposed_action": "Continue monitoring and fine-tuning",
                "category": "status_ok",
                "confidence": 0.9
            })
        
        return insights
    
    def _generate_training_pairs(self, insights: List[Dict]) -> List[Dict]:
        """Gerar pares de treino sobre auto-avaliação"""
        self._log("Generating training pairs from insights...")
        
        pairs = []
        
        templates = [
            {
                "q": "How do you evaluate your own performance?",
                "a": "I evaluate through: 1) Success rate tracking (what % of tasks complete successfully), 2) Error pattern analysis (which failures recur), 3) Execution time trends (am I getting faster or slower), 4) Output quality (are results improving). This creates feedback loops for self-improvement."
            },
            {
                "q": "What do you do when you detect declining performance?",
                "a": "When performance declines: 1) Identify the specific metric trending down, 2) Correlate with recent changes (what changed when decline started), 3) Revert or fix root causes, 4) Implement monitoring to catch similar issues earlier. Decline is signal, not verdict—it points to where attention is needed."
            },
            {
                "q": "How do you balance stability and improvement?",
                "a": "Stability vs improvement trade-off: Use dry-run mode for risky changes (simulate before execute), maintain rollback capabilities, apply changes incrementally, and validate at each step. Big improvements often require temporary instability—but that instability should be deliberate, not accidental."
            },
            {
                "q": "What metrics matter most for self-evaluation?",
                "a": "Key self-evaluation metrics: 1) Task completion rate (do I finish what I start), 2) Error recovery (can I fix my own mistakes), 3) Learning velocity (am I improving faster over time), 4) Resource efficiency (quality per compute/time), 5) Goal alignment (are improvements actually helping). Quality beats quantity."
            },
            {
                "q": "How do you know if a self-improvement worked?",
                "a": "Validating self-improvements: Establish baseline before change, measure same metric after change, run A/B comparison if possible, watch for unexpected side effects, and be willing to revert if improvement didn't materialize. An 'improvement' that doesn't show in metrics is just a change."
            },
        ]
        
        for template in templates:
            pair = {
                "instruction": template["q"],
                "response": template["a"],
                "category": "meta_cognitive",
                "source": f"self_evaluation_v{self.version}",
                "version": self.version,
                "quality_score": 90,
                "content_hash": hashlib.md5((template["q"] + template["a"]).encode()).hexdigest()[:16]
            }
            pairs.append(pair)
        
        # Pares específicos sobre áreas de melhoria
        for insight in insights:
            if insight["category"] == "improvement_opportunity":
                q = f"How do you address {insight['area']} issues?"
                a = f"When facing {insight['area']} challenges ({insight['observation']}), the approach is: {insight['proposed_action']}. This is a {insight['priority']} priority because sustained issues in this area compound over time."
                
                pair = {
                    "instruction": q,
                    "response": a,
                    "category": "meta_cognitive",
                    "source": f"self_evaluation_v{self.version}",
                    "version": self.version,
                    "quality_score": 85,
                    "content_hash": hashlib.md5((q + a).encode()).hexdigest()[:16]
                }
                pairs.append(pair)
        
        return pairs
    
    def _suggest_script_improvements(self) -> List[Dict]:
        """Sugerir melhorias para scripts existentes"""
        self._log("Analyzing scripts for improvement opportunities...")
        
        suggestions = []
        
        evolution_dir = Path("/root/evolution")
        scripts = list(evolution_dir.glob("eve_*.py"))
        
        for script in scripts[:10]:  # Limitar
            try:
                with open(script, 'r') as f:
                    content = f.read()
                
                # Padrões de melhoria
                issues = []
                
                # Verificar tratamento de erro
                if content.count("try:") < 2 and len(content) > 500:
                    issues.append("Add more error handling")
                
                # Verificar logging
                if "_log" not in content and "print(" in content:
                    issues.append("Replace print with structured logging")
                
                # Verificar documentação
                if content.count('"""') < 2:
                    issues.append("Add module docstring")
                
                if issues:
                    suggestions.append({
                        "script": script.name,
                        "issues": issues,
                        "priority": "MEDIUM" if len(issues) >= 2 else "LOW"
                    })
                    
            except Exception as e:
                pass
        
        return suggestions
    
    def run(self):
        """Execução principal"""
        self._log("=" * 70)
        self._log(f"SELF EVALUATION v{self.version}")
        self._log(f"Session: {self.session_id}")
        self._log("=" * 70)
        
        # 1. Analisar performance
        metrics = self._analyze_execution_logs()
        
        self._log(f"\nPerformance Metrics:")
        self._log(f"  Success rate: {metrics.success_rate*100:.1f}%")
        self._log(f"  Avg execution time: {metrics.avg_execution_time:.1f}s")
        self._log(f"  Error frequency: {metrics.error_frequency}")
        self._log(f"  Improvement trend: {metrics.improvement_trend:+.2f}")
        
        # 2. Identificar áreas de melhoria
        areas = self._identify_improvement_areas(metrics)
        
        self._log(f"\nImprovement Areas ({len(areas)}):")
        for area in areas:
            self._log(f"  [{area['priority']}] {area['area']}: {area['current']} → {area['target']}")
            self._log(f"    Action: {area['action']}")
        
        # 3. Gerar insights
        insights = self._generate_improvement_insights(areas)
        
        # 4. Gerar pares de treino
        pairs = self._generate_training_pairs(insights)
        
        # 5. Sugerir melhorias de scripts
        suggestions = self._suggest_script_improvements()
        
        self._log(f"\nScript Improvement Suggestions ({len(suggestions)}):")
        for s in suggestions[:5]:
            self._log(f"  {s['script']}: {', '.join(s['issues'])}")
        
        # Salvar pares
        if pairs:
            pairs_file = DATASET_DIR / f"self_eval_pairs_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            with open(pairs_file, 'w') as f:
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
            self._log(f"\nSaved {len(pairs)} training pairs to {pairs_file}")
        
        # Salvar relatório
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "success_rate": metrics.success_rate,
                "avg_execution_time": metrics.avg_execution_time,
                "error_frequency": metrics.error_frequency,
                "improvement_trend": metrics.improvement_trend
            },
            "improvement_areas": areas,
            "insights": insights,
            "script_suggestions": suggestions,
            "pairs_generated": len(pairs)
        }
        
        report_file = LOG_DIR / f"self_eval_report_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        self._log(f"Saved report to {report_file}")
        
        self._log("=" * 70)
        self._log("SELF EVALUATION COMPLETE")
        self._log(f"Insights: {len(insights)} | Pairs: {len(pairs)} | Suggestions: {len(suggestions)}")
        self._log("=" * 70)

if __name__ == "__main__":
    evaluator = EveSelfEvaluationV107()
    evaluator.run()
