#!/usr/bin/env python3
"""
eve_habit_compiler.py — Habit Compilation Mechanism

Baseado em Tri-Spirit Architecture (arXiv:2604.13757).
Promove caminhos de raciocínio repetidos em políticas de execução zero-inference.

Estrutura CACM-aware:
- Static: Regras de compilação, thresholds (imutáveis)
- Dynamic: Frequência de padrões detectados (evolui)
- Corrective: Feedback de execução (aprendizado)

Ciclo #87 — Eve 🌙
"""

import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Configuração CACM-aware
HABIT_CONFIG = {
    "frequency_threshold": 3,  # Mínimo de ocorrências para compilar
    "confidence_threshold": 0.75,
    "recency_weight": 0.7,  # Peso para ocorrências recentes
    "max_habits": 100,  # Limite de memória
    "compile_format": "json",  # Formato de exportação
}

PATHS = {
    "insights_consolidated": Path("/memory/corrective/insights/consolidated"),
    "habits_compiled": Path("/memory/corrective/habits/compiled"),
    "habits_meta": Path("/memory/corrective/habits/meta.json"),
    "habits_log": Path("/memory/corrective/habits/compilation.log"),
}


@dataclass
class Pattern:
    """Representa um padrão detectado nos insights."""
    pattern_type: str  # 'reasoning_template', 'action_sequence', 'validation_check'
    content: str
    source_insights: List[str]  # IDs dos insights fonte
    frequency: int
    last_seen: str  # ISO timestamp
    confidence: float  # 0.0-1.0
    compiled: bool = False
    habit_id: Optional[str] = None


@dataclass
class CompiledHabit:
    """Hábito compilado pronto para execução zero-inference."""
    habit_id: str
    pattern_type: str
    trigger: str  # Regex ou condição de ativação
    action: Dict  # Ação a ser executada
    confidence: float
    compiled_at: str
    execution_count: int = 0
    success_count: int = 0


class HabitCompiler:
    """
    Compila padrões recorrentes em hábitos executáveis.
    
    Baseado no habit-compilation mechanism do Tri-Spirit:
    - Detecta padrões em insights consolidados
    - Calcula frequência ponderada por recência
    - Compila em hábitos quando threshold atingido
    - Executa em zero-inference quando trigger match
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or HABIT_CONFIG
        self.patterns: Dict[str, Pattern] = {}
        self.habits: Dict[str, CompiledHabit] = {}
        self._ensure_dirs()
        self._load_meta()
    
    def _ensure_dirs(self):
        """Cria estrutura de diretórios CACM-aware."""
        for path in [PATHS["habits_compiled"], PATHS["insights_consolidated"]]:
            path.mkdir(parents=True, exist_ok=True)
    
    def _load_meta(self):
        """Carrega metadados de hábitos existentes."""
        if PATHS["habits_meta"].exists():
            with open(PATHS["habits_meta"], 'r') as f:
                meta = json.load(f)
                for habit_data in meta.get("habits", []):
                    habit = CompiledHabit(**habit_data)
                    self.habits[habit.habit_id] = habit
    
    def _save_meta(self):
        """Salva metadados de hábitos."""
        meta = {
            "last_updated": datetime.now().isoformat(),
            "cycle": 87,
            "habit_count": len(self.habits),
            "habits": [asdict(h) for h in self.habits.values()]
        }
        with open(PATHS["habits_meta"], 'w') as f:
            json.dump(meta, f, indent=2)
    
    def _generate_pattern_id(self, content: str) -> str:
        """Gera ID único para padrão baseado em hash."""
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _generate_habit_id(self, pattern: Pattern) -> str:
        """Gera ID de hábito compilado."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        return f"H-{pattern.pattern_type[:3].upper()}-{timestamp}-{pattern.frequency}"
    
    def extract_patterns_from_insight(self, insight_path: Path) -> List[Pattern]:
        """
        Extrai padrões de um arquivo de insight.
        
        Padrões detectados:
        - Reasoning templates: "If X then Y" structures
        - Action sequences: "First A, then B, finally C"
        - Validation checks: "Verify that...", "Check if..."
        """
        patterns = []
        
        with open(insight_path, 'r') as f:
            content = f.read()
        
        # Pattern: Reasoning templates (if-then)
        if_then_matches = re.findall(r'if\s+(.+?)\s+then\s+(.+?)(?:\.|\n)', content, re.IGNORECASE)
        for condition, consequence in if_then_matches:
            pattern_content = f"IF {condition.strip()} THEN {consequence.strip()}"
            pattern_id = self._generate_pattern_id(pattern_content)
            patterns.append(Pattern(
                pattern_type="reasoning_template",
                content=pattern_content,
                source_insights=[insight_path.stem],
                frequency=1,
                last_seen=datetime.now().isoformat(),
                confidence=0.8
            ))
        
        # Pattern: Action sequences (first-then-finally)
        action_matches = re.findall(r'(?:first|1\.)\s+(.+?)\s+(?:then|2\.)\s+(.+?)\s+(?:finally|3\.)\s+(.+?)(?:\.|\n)', content, re.IGNORECASE)
        for step1, step2, step3 in action_matches:
            pattern_content = f"SEQ: {step1.strip()} → {step2.strip()} → {step3.strip()}"
            patterns.append(Pattern(
                pattern_type="action_sequence",
                content=pattern_content,
                source_insights=[insight_path.stem],
                frequency=1,
                last_seen=datetime.now().isoformat(),
                confidence=0.75
            ))
        
        # Pattern: Validation checks
        validation_matches = re.findall(r'(?:verify|check|validate|ensure)\s+(?:that\s+)?(.+?)(?:\.|\n)', content, re.IGNORECASE)
        for check in validation_matches:
            pattern_content = f"CHECK: {check.strip()}"
            patterns.append(Pattern(
                pattern_type="validation_check",
                content=pattern_content,
                source_insights=[insight_path.stem],
                frequency=1,
                last_seen=datetime.now().isoformat(),
                confidence=0.7
            ))
        
        return patterns
    
    def scan_insights(self) -> int:
        """
        Escaneia insights consolidados e atualiza padrões.
        
        Returns:
            Número de novos padrões detectados
        """
        new_patterns = 0
        
        if not PATHS["insights_consolidated"].exists():
            return 0
        
        for insight_file in PATHS["insights_consolidated"].glob("*.md"):
            patterns = self.extract_patterns_from_insight(insight_file)
            
            for pattern in patterns:
                pattern_id = self._generate_pattern_id(pattern.content)
                
                if pattern_id in self.patterns:
                    # Atualiza padrão existente
                    existing = self.patterns[pattern_id]
                    existing.frequency += 1
                    existing.source_insights.append(insight_file.stem)
                    existing.last_seen = datetime.now().isoformat()
                    # Boost de confiança com repetição
                    existing.confidence = min(0.95, existing.confidence + 0.05)
                else:
                    # Novo padrão
                    self.patterns[pattern_id] = pattern
                    new_patterns += 1
        
        return new_patterns
    
    def calculate_compilation_candidates(self) -> List[Pattern]:
        """
        Identifica padrões prontos para compilação.
        
        Critérios:
        - Frequência >= threshold
        - Confiança >= threshold
        - Não compilado anteriormente
        """
        candidates = []
        
        for pattern in self.patterns.values():
            if (pattern.frequency >= self.config["frequency_threshold"] and
                pattern.confidence >= self.config["confidence_threshold"] and
                not pattern.compiled):
                candidates.append(pattern)
        
        # Ordena por confiança ponderada por frequência
        candidates.sort(key=lambda p: p.confidence * p.frequency, reverse=True)
        
        return candidates
    
    def compile_habit(self, pattern: Pattern) -> Optional[CompiledHabit]:
        """
        Compila um padrão em hábito executável.
        
        Gera:
        - Trigger: condição de ativação
        - Action: ação a ser executada
        - Metadata: confiança, fonte, etc.
        """
        habit_id = self._generate_habit_id(pattern)
        
        # Gera trigger baseado no tipo de padrão
        if pattern.pattern_type == "reasoning_template":
            # Extrai condição do IF-THEN
            match = re.match(r'IF\s+(.+?)\s+THEN\s+(.+)', pattern.content, re.IGNORECASE)
            if match:
                trigger = match.group(1).lower()
                action_desc = match.group(2)
                action = {
                    "type": "reasoning",
                    "description": action_desc,
                    "execute": f"Apply reasoning: {action_desc}"
                }
            else:
                trigger = pattern.content.lower()[:50]
                action = {"type": "reasoning", "execute": pattern.content}
        
        elif pattern.pattern_type == "action_sequence":
            # SEQ: step1 → step2 → step3
            steps = pattern.content.replace("SEQ: ", "").split(" → ")
            trigger = steps[0].lower()[:30] if steps else "sequence"
            action = {
                "type": "sequence",
                "steps": steps,
                "execute": f"Execute sequence: {' → '.join(steps)}"
            }
        
        elif pattern.pattern_type == "validation_check":
            # CHECK: condition
            check = pattern.content.replace("CHECK: ", "")
            trigger = check.lower()[:40]
            action = {
                "type": "validation",
                "check": check,
                "execute": f"Validate: {check}"
            }
        
        else:
            trigger = pattern.content.lower()[:50]
            action = {"type": "generic", "execute": pattern.content}
        
        habit = CompiledHabit(
            habit_id=habit_id,
            pattern_type=pattern.pattern_type,
            trigger=trigger,
            action=action,
            confidence=pattern.confidence,
            compiled_at=datetime.now().isoformat()
        )
        
        # Salva hábito compilado
        habit_path = PATHS["habits_compiled"] / f"{habit_id}.json"
        with open(habit_path, 'w') as f:
            json.dump(asdict(habit), f, indent=2)
        
        # Marca padrão como compilado
        pattern.compiled = True
        pattern.habit_id = habit_id
        
        return habit
    
    def compile_candidates(self, max_compile: int = 10) -> List[CompiledHabit]:
        """
        Compila candidatos em hábitos.
        
        Args:
            max_compile: Máximo de hábitos a compilar por ciclo
        
        Returns:
            Lista de hábitos compilados
        """
        candidates = self.calculate_compilation_candidates()
        compiled = []
        
        for pattern in candidates[:max_compile]:
            habit = self.compile_habit(pattern)
            if habit:
                self.habits[habit.habit_id] = habit
                compiled.append(habit)
        
        self._save_meta()
        self._log_compilation(compiled)
        
        return compiled
    
    def _log_compilation(self, habits: List[CompiledHabit]):
        """Registra compilação no log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle": 87,
            "compiled_count": len(habits),
            "habits": [h.habit_id for h in habits]
        }
        
        # Append ao log
        mode = 'a' if PATHS["habits_log"].exists() else 'w'
        with open(PATHS["habits_log"], mode) as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do compilador."""
        return {
            "total_patterns": len(self.patterns),
            "compiled_habits": len(self.habits),
            "candidates_pending": len(self.calculate_compilation_candidates()),
            "by_type": {
                "reasoning_template": len([p for p in self.patterns.values() if p.pattern_type == "reasoning_template"]),
                "action_sequence": len([p for p in self.patterns.values() if p.pattern_type == "action_sequence"]),
                "validation_check": len([p for p in self.patterns.values() if p.pattern_type == "validation_check"]),
            }
        }
    
    def execute_habit(self, trigger_text: str) -> Optional[CompiledHabit]:
        """
        Tenta executar hábito com base em trigger.
        
        Zero-inference execution: não requer LLM, apenas pattern matching.
        
        Args:
            trigger_text: Texto que pode ativar um hábito
        
        Returns:
            Hábito executado ou None
        """
        trigger_lower = trigger_text.lower()
        
        for habit in self.habits.values():
            # Match parcial do trigger
            if habit.trigger in trigger_lower or trigger_lower in habit.trigger:
                habit.execution_count += 1
                self._save_meta()
                return habit
        
        return None


def main():
    """Entry point do compilador de hábitos."""
    print("=" * 60)
    print("Eve Habit Compiler — Ciclo #87")
    print("Baseado em: Tri-Spirit Architecture (arXiv:2604.13757)")
    print("=" * 60)
    
    compiler = HabitCompiler()
    
    # Passo 1: Escaneia insights
    print("\n📊 Escaneando insights consolidados...")
    new_patterns = compiler.scan_insights()
    print(f"   Novos padrões detectados: {new_patterns}")
    
    # Passo 2: Mostra estatísticas
    stats = compiler.get_stats()
    print(f"\n📈 Estatísticas:")
    print(f"   Total de padrões: {stats['total_patterns']}")
    print(f"   Hábitos compilados: {stats['compiled_habits']}")
    print(f"   Candidatos pendentes: {stats['candidates_pending']}")
    print(f"   Por tipo: {stats['by_type']}")
    
    # Passo 3: Compila candidatos
    print(f"\n🔨 Compilando hábitos (threshold: {HABIT_CONFIG['frequency_threshold']})...")
    compiled = compiler.compile_candidates(max_compile=5)
    
    if compiled:
        print(f"\n✅ Hábitos compilados: {len(compiled)}")
        for habit in compiled:
            print(f"   • {habit.habit_id} ({habit.pattern_type}, conf: {habit.confidence:.2f})")
            print(f"     Trigger: {habit.trigger[:60]}...")
    else:
        print("\n⏳ Nenhum candidato pronto para compilação.")
        print("   (Aguardando mais repetições para atingir threshold)")
    
    print("\n" + "=" * 60)
    print("Compilação completa. Próximo passo: execução zero-inference.")
    print("=" * 60)


if __name__ == "__main__":
    main()
