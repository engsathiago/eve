#!/usr/bin/env python3
"""
EVE MID-GENERATION EVALUATOR (PRA Pattern Implementation)
Ciclo #103 - Process Reward Agents inspired mid-generation evaluation

Propósito: Avaliar qualidade DURANTE a geração, não apenas no final.
Isso permite early stopping (quando já bom o suficiente) ou continuation
(quando precisa melhorar).

Baseado em: arXiv:2604.11759 (Process Reward Agents)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
import hashlib
import sqlite3
from pathlib import Path


class QualityLevel(Enum):
    """Níveis de qualidade para mid-generation evaluation."""
    EXCELLENT = 5  # Pode parar, já está ótimo
    GOOD = 4       # Bom, mas pode melhorar
    ACCEPTABLE = 3 # Mínimo aceitável
    NEEDS_WORK = 2 # Precisa de mais trabalho
    POOR = 1       # Ruim, deve recomeçar


class Action(Enum):
    """Ações possíveis baseadas na avaliação."""
    STOP_ACCEPT = "stop_accept"      # Parar, resultado aceito
    CONTINUE = "continue"            # Continuar melhorando
    REVISE = "revise"                # Revisar abordagem
    RESTART = "restart"              # Recomeçar do zero


@dataclass
class MidGenCheckpoint:
    """Checkpoint de avaliação mid-generation."""
    step: int                           # Passo da geração
    partial_output: str                 # Saída parcial
    quality_score: float               # 0.0 - 1.0
    quality_level: QualityLevel
    confidence: float                  # Confiança da avaliação
    reasoning: str                     # Raciocínio da avaliação
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "step": self.step,
            "partial_output": self.partial_output[:500] + "..." if len(self.partial_output) > 500 else self.partial_output,
            "quality_score": self.quality_score,
            "quality_level": self.quality_level.name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp
        }


@dataclass
class EvaluationResult:
    """Resultado completo da avaliação mid-generation."""
    final_action: Action
    final_checkpoint: MidGenCheckpoint
    checkpoints: List[MidGenCheckpoint]
    total_steps: int
    total_time: float
    
    def to_dict(self) -> Dict:
        return {
            "final_action": self.final_action.value,
            "final_checkpoint": self.final_checkpoint.to_dict(),
            "checkpoints_count": len(self.checkpoints),
            "total_steps": self.total_steps,
            "total_time": self.total_time
        }


class MidGenEvaluator:
    """
    Avaliador de qualidade durante geração.
    
    Inspiração: Process Reward Agents avaliam processo, não apenas resultado final.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "/root/evolution/midgen_cache.db"
        self._init_db()
        
        # Thresholds para decisões
        self.thresholds = {
            "excellent": 0.90,
            "good": 0.75,
            "acceptable": 0.60,
            "poor": 0.40
        }
        
        # Configuração de early stopping
        self.max_steps = 10
        self.min_steps = 3
        self.patience = 2  # Steps sem melhoria antes de parar
        
    def _init_db(self):
        """Inicializa cache SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS midgen_evaluations (
                id TEXT PRIMARY KEY,
                task_hash TEXT,
                partial_output_hash TEXT,
                step INTEGER,
                quality_score REAL,
                quality_level TEXT,
                confidence REAL,
                reasoning TEXT,
                timestamp REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_hash ON midgen_evaluations(task_hash)
        """)
        conn.commit()
        conn.close()
    
    def _get_task_hash(self, task: str) -> str:
        """Hash da tarefa para cache."""
        return hashlib.sha256(task.encode()).hexdigest()[:16]
    
    def _get_output_hash(self, output: str) -> str:
        """Hash da saída para cache."""
        return hashlib.sha256(output.encode()).hexdigest()[:16]
    
    def _check_cache(self, task_hash: str, output_hash: str) -> Optional[MidGenCheckpoint]:
        """Verifica cache para avaliação."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT * FROM midgen_evaluations WHERE task_hash = ? AND partial_output_hash = ?",
            (task_hash, output_hash)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return MidGenCheckpoint(
                step=row[3],
                partial_output="",  # Não armazenamos saída completa
                quality_score=row[4],
                quality_level=QualityLevel[row[5]],
                confidence=row[6],
                reasoning=row[7],
                timestamp=row[8]
            )
        return None
    
    def _cache_result(self, task_hash: str, checkpoint: MidGenCheckpoint):
        """Armazena resultado no cache."""
        output_hash = self._get_output_hash(checkpoint.partial_output)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO midgen_evaluations
               (id, task_hash, partial_output_hash, step, quality_score, quality_level, confidence, reasoning, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"{task_hash}:{output_hash}", task_hash, output_hash,
             checkpoint.step, checkpoint.quality_score, checkpoint.quality_level.name,
             checkpoint.confidence, checkpoint.reasoning, checkpoint.timestamp)
        )
        conn.commit()
        conn.close()
    
    async def evaluate_step(
        self,
        task: str,
        partial_output: str,
        step: int,
        evaluator_fn: Optional[Callable[[str, str], Tuple[float, str]]] = None
    ) -> MidGenCheckpoint:
        """
        Avalia um passo intermediário da geração.
        
        Args:
            task: Tarefa original
            partial_output: Saída parcial gerada
            step: Número do passo
            evaluator_fn: Função customizada de avaliação (opcional)
            
        Returns:
            MidGenCheckpoint com avaliação
        """
        task_hash = self._get_task_hash(task)
        output_hash = self._get_output_hash(partial_output)
        
        # Check cache
        cached = self._check_cache(task_hash, output_hash)
        if cached:
            cached.partial_output = partial_output  # Restore output
            return cached
        
        # Avaliação
        if evaluator_fn:
            score, reasoning = evaluator_fn(task, partial_output)
        else:
            score, reasoning = await self._default_evaluate(task, partial_output)
        
        # Determina nível de qualidade
        if score >= self.thresholds["excellent"]:
            level = QualityLevel.EXCELLENT
        elif score >= self.thresholds["good"]:
            level = QualityLevel.GOOD
        elif score >= self.thresholds["acceptable"]:
            level = QualityLevel.ACCEPTABLE
        elif score >= self.thresholds["poor"]:
            level = QualityLevel.NEEDS_WORK
        else:
            level = QualityLevel.POOR
        
        checkpoint = MidGenCheckpoint(
            step=step,
            partial_output=partial_output,
            quality_score=score,
            quality_level=level,
            confidence=0.85,  # Pode ser ajustado baseado em consistência
            reasoning=reasoning
        )
        
        # Cache resultado
        self._cache_result(task_hash, checkpoint)
        
        return checkpoint
    
    async def _default_evaluate(self, task: str, partial_output: str) -> Tuple[float, str]:
        """
        Avaliação padrão baseada em heurísticas.
        
        Em implementação completa, isso usaria um modelo de avaliação.
        """
        score = 0.5
        reasons = []
        
        # Heurísticas básicas
        
        # 1. Completude (tem conclusão?)
        if any(marker in partial_output.lower() for marker in ["conclusion", "resumo", "final"]):
            score += 0.15
            reasons.append("has_conclusion")
        
        # 2. Estrutura (tem seções?)
        if "##" in partial_output or "**" in partial_output:
            score += 0.1
            reasons.append("has_structure")
        
        # 3. Tamanho apropriado
        word_count = len(partial_output.split())
        if 100 <= word_count <= 1000:
            score += 0.1
            reasons.append("appropriate_length")
        elif word_count < 50:
            score -= 0.1
            reasons.append("too_short")
        
        # 4. Presença de exemplos ou código
        if "```" in partial_output or "exemplo" in partial_output.lower():
            score += 0.1
            reasons.append("has_examples")
        
        # 5. Coerência (verificação simples)
        sentences = partial_output.split(".")
        if len(sentences) > 3:
            score += 0.05
            reasons.append("multi_sentence")
        
        score = max(0.0, min(1.0, score))
        
        reasoning = f"Score: {score:.2f}. Factors: {', '.join(reasons)}"
        return score, reasoning
    
    def decide_action(
        self,
        checkpoint: MidGenCheckpoint,
        history: List[MidGenCheckpoint]
    ) -> Action:
        """
        Decide ação baseada no checkpoint atual e histórico.
        
        Args:
            checkpoint: Checkpoint atual
            history: Histórico de checkpoints anteriores
            
        Returns:
            Action recomendada
        """
        # Se excelente, para
        if checkpoint.quality_level == QualityLevel.EXCELLENT and len(history) >= self.min_steps:
            return Action.STOP_ACCEPT
        
        # Se ruim, recomeça
        if checkpoint.quality_level == QualityLevel.POOR:
            return Action.RESTART
        
        # Se precisa de trabalho, revisa
        if checkpoint.quality_level == QualityLevel.NEEDS_WORK:
            return Action.REVISE
        
        # Early stopping: verifica se estagnou
        if len(history) >= self.max_steps:
            if checkpoint.quality_level in [QualityLevel.GOOD, QualityLevel.EXCELLENT]:
                return Action.STOP_ACCEPT
            else:
                return Action.REVISE
        
        # Verifica se melhoria estagnou
        if len(history) >= self.patience:
            recent = history[-self.patience:]
            scores = [c.quality_score for c in recent]
            if max(scores) - min(scores) < 0.05:  # Pouca variação
                if checkpoint.quality_score >= self.thresholds["acceptable"]:
                    return Action.STOP_ACCEPT
                else:
                    return Action.REVISE
        
        # Default: continua
        return Action.CONTINUE
    
    async def generate_with_evaluation(
        self,
        task: str,
        generator_fn: Callable[[str, int], str],
        evaluator_fn: Optional[Callable[[str, str], Tuple[float, str]]] = None
    ) -> EvaluationResult:
        """
        Gera com avaliação mid-generation contínua.
        
        Args:
            task: Tarefa a ser executada
            generator_fn: Função geradora (task, step) -> output
            evaluator_fn: Função avaliadora opcional
            
        Returns:
            EvaluationResult com histórico completo
        """
        start_time = time.time()
        checkpoints = []
        step = 0
        
        while step < self.max_steps:
            # Gera saída parcial
            partial_output = generator_fn(task, step)
            
            # Avalia
            checkpoint = await self.evaluate_step(task, partial_output, step, evaluator_fn)
            checkpoints.append(checkpoint)
            
            # Decide ação
            action = self.decide_action(checkpoint, checkpoints)
            
            print(f"Step {step}: score={checkpoint.quality_score:.2f}, "
                  f"level={checkpoint.quality_level.name}, action={action.value}")
            
            if action == Action.STOP_ACCEPT:
                total_time = time.time() - start_time
                return EvaluationResult(
                    final_action=action,
                    final_checkpoint=checkpoint,
                    checkpoints=checkpoints,
                    total_steps=step + 1,
                    total_time=total_time
                )
            
            if action == Action.RESTART:
                # Limpa e recomeça
                checkpoints = []
                step = 0
                continue
            
            if action == Action.REVISE:
                # Pode implementar lógica de revisão específica
                pass
            
            step += 1
        
        # Max steps atingido
        total_time = time.time() - start_time
        final_checkpoint = checkpoints[-1] if checkpoints else None
        
        return EvaluationResult(
            final_action=Action.STOP_ACCEPT if final_checkpoint and final_checkpoint.quality_score >= self.thresholds["acceptable"] else Action.REVISE,
            final_checkpoint=final_checkpoint,
            checkpoints=checkpoints,
            total_steps=len(checkpoints),
            total_time=total_time
        )


class CodeMidGenEvaluator(MidGenEvaluator):
    """
    Especialização do MidGenEvaluator para código.
    
    Usa verificação de sintaxe, análise AST, e testes como sinais de qualidade.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        super().__init__(db_path)
        
        # Thresholds mais rigorosos para código
        self.thresholds = {
            "excellent": 0.95,
            "good": 0.85,
            "acceptable": 0.70,
            "poor": 0.50
        }
    
    async def evaluate_code_step(
        self,
        task: str,
        partial_code: str,
        step: int,
        test_fn: Optional[Callable[[str], bool]] = None
    ) -> MidGenCheckpoint:
        """
        Avalia passo de geração de código.
        
        Args:
            task: Descrição da tarefa
            partial_code: Código parcial
            step: Número do passo
            test_fn: Função opcional para testar código
            
        Returns:
            MidGenCheckpoint
        """
        score = 0.5
        reasons = []
        
        # 1. Sintaxe Python válida?
        try:
            import ast
            ast.parse(partial_code)
            score += 0.2
            reasons.append("valid_syntax")
        except SyntaxError:
            score -= 0.2
            reasons.append("syntax_error")
        
        # 2. Tem docstring?
        if '"""' in partial_code or "'''" in partial_code:
            score += 0.1
            reasons.append("has_docstring")
        
        # 3. Tem type hints?
        if "-> " in partial_code or ": " in partial_code.split("(")[0] if "(" in partial_code else False:
            score += 0.1
            reasons.append("has_type_hints")
        
        # 4. Tem tratamento de erro?
        if "try:" in partial_code and "except" in partial_code:
            score += 0.1
            reasons.append("error_handling")
        
        # 5. Testa se função disponível
        if test_fn:
            try:
                if test_fn(partial_code):
                    score += 0.2
                    reasons.append("passes_tests")
                else:
                    score -= 0.1
                    reasons.append("fails_tests")
            except Exception as e:
                score -= 0.1
                reasons.append(f"test_error: {str(e)[:30]}")
        
        # 6. Tamanho apropriado
        lines = partial_code.strip().split("\n")
        if 10 <= len(lines) <= 200:
            score += 0.05
            reasons.append("appropriate_size")
        
        score = max(0.0, min(1.0, score))
        
        # Determina nível
        if score >= self.thresholds["excellent"]:
            level = QualityLevel.EXCELLENT
        elif score >= self.thresholds["good"]:
            level = QualityLevel.GOOD
        elif score >= self.thresholds["acceptable"]:
            level = QualityLevel.ACCEPTABLE
        elif score >= self.thresholds["poor"]:
            level = QualityLevel.NEEDS_WORK
        else:
            level = QualityLevel.POOR
        
        reasoning = f"Code score: {score:.2f}. Factors: {', '.join(reasons)}"
        
        return MidGenCheckpoint(
            step=step,
            partial_output=partial_code,
            quality_score=score,
            quality_level=level,
            confidence=0.90,
            reasoning=reasoning
        )


# === DEMONSTRAÇÃO ===

async def demo():
    """Demonstração do MidGenEvaluator."""
    
    print("=" * 60)
    print("EVE MID-GENERATION EVALUATOR v1.0")
    print("Process Reward Agents Pattern Implementation")
    print("=" * 60)
    
    # Demo 1: Avaliação simples
    print("\n--- Demo 1: Step-by-step evaluation ---\n")
    
    evaluator = MidGenEvaluator()
    
    task = "Explique arquitetura de auto-melhoramento"
    
    # Simula geração em passos
    partial_outputs = [
        "Auto-melhoramento é...",  # Step 0: incompleto
        "Auto-melhoramento é quando um sistema melhora a si mesmo. Ele usa feedback.",  # Step 1: básico
        "## Auto-Melhoramento\\n\\nAuto-melhoramento é o processo pelo qual um sistema modifica a si mesmo para melhorar performance.",  # Step 2: estruturado
        "## Auto-Melhoramento\\n\\nAuto-melhoramento é o processo pelo qual um sistema modifica a si mesmo.\\n\\n### Componentes\\n- Feedback loop\\n- Avaliação\\n- Atualização\\n\\n### Exemplo\\n```python\\ndef improve(self):\\n    feedback = self.evaluate()\\n    self.update(feedback)\\n```\\n\\n## Conclusão\\nSistemas de auto-melhoramento são essenciais para IA autônoma.",  # Step 3: completo
    ]
    
    for i, output in enumerate(partial_outputs):
        checkpoint = await evaluator.evaluate_step(task, output, i)
        print(f"Step {i}: {checkpoint.quality_level.name} "
              f"({checkpoint.quality_score:.2f}) - {checkpoint.reasoning[:60]}...")
    
    # Demo 2: Code evaluation
    print("\n--- Demo 2: Code evaluation ---\n")
    
    code_evaluator = CodeMidGenEvaluator()
    
    task = "Implemente uma função de fibonacci"
    
    code_steps = [
        "def fib(n):",  # Step 0: incompleto
        "def fib(n):\n    return n",  # Step 1: stub
        "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",  # Step 2: funcional
        '"""Fibonacci implementation."""\ndef fib(n: int) -> int:\n    """Calculate fibonacci number."""\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)',  # Step 3: completo
    ]
    
    def test_fib(code):
        try:
            exec(code, globals())
            return fib(10) == 55
        except:
            return False
    
    for i, code in enumerate(code_steps):
        checkpoint = await code_evaluator.evaluate_code_step(task, code, i, test_fn=test_fib if i >= 2 else None)
        print(f"Step {i}: {checkpoint.quality_level.name} "
              f"({checkpoint.quality_score:.2f}) - {checkpoint.reasoning[:60]}...")
    
    print("\n--- Demo 3: Full generation with evaluation ---\n")
    
    # Simula generator
    step_idx = 0
    def mock_generator(task, step):
        nonlocal step_idx
        outputs = [
            "Início da resposta...",
            "Desenvolvimento com alguns detalhes sobre o tema.",
            "## Título\n\nConteúdo estruturado com informações.\n\nExemplo de uso.",
            "## Título\n\nConteúdo estruturado com informações relevantes.\n\n### Exemplo\n```\ncode()\n```\n\nConclusão final completa."
        ]
        result = outputs[min(step, len(outputs)-1)]
        step_idx += 1
        return result
    
    result = await evaluator.generate_with_evaluation(
        task="Escreva documentação técnica",
        generator_fn=mock_generator
    )
    
    print(f"\nResultado final: {result.final_action.value}")
    print(f"Steps: {result.total_steps}")
    print(f"Tempo: {result.total_time:.2f}s")
    print(f"Score final: {result.final_checkpoint.quality_score:.2f}")
    
    print("\n" + "=" * 60)
    print("DEMO CONCLUÍDA")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
