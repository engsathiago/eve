#!/usr/bin/env python3
"""
eve_habit_compiler_v107.py — Habit Compilation Mechanism v107

Baseado em Tri-Spirit Architecture + Ciclo #107 insights.
Promove caminhos de raciocínio repetidos em políticas de execução zero-inference.

NOVO v107:
- Pattern extraction de QUESTIONs resolvidas
- Habit composition (hábitos compostos de sub-hábitos)
- Execution analytics (track success/failure)
- Auto-threshold calibration baseado em performance

Estrutura CACM-aware:
- Static: Regras de compilação, thresholds (imutáveis)
- Dynamic: Frequência de padrões detectados (evolui)
- Corrective: Feedback de execução (aprendizado)

Ciclo #107 — Eve 🌙
"""

import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import sqlite3

# Configuração CACM-aware v107
HABIT_CONFIG = {
    "frequency_threshold": 3,  # Mínimo de ocorrências para compilar
    "confidence_threshold": 0.75,
    "recency_weight": 0.7,  # Peso para ocorrências recentes
    "max_habits": 100,
    "compile_format": "json",
    # NOVO v107:
    "composition_threshold": 0.85,  # Confiança mínima para compor hábitos
    "auto_calibrate": True,  # Ajusta thresholds automaticamente
    "success_rate_target": 0.80,  # Meta de sucesso para calibração
}

PATHS = {
    "insights_consolidated": Path("/memory/corrective/insights/consolidated"),
    "insights_pending": Path("/memory/corrective/insights/pending"),
    "habits_compiled": Path("/memory/corrective/habits/compiled"),
    "habits_meta": Path("/memory/corrective/habits/meta_v107.json"),
    "habits_log": Path("/memory/corrective/habits/compilation_v107.log"),
    "habits_db": Path("/memory/corrective/habits/habits_v107.db"),
    "execution_log": Path("/memory/corrective/habits/execution_v107.jsonl"),
    "questions_resolved": Path("/memory/corrective/questions/resolved"),
}


@dataclass
class Pattern:
    """Representa um padrão detectado nos insights."""
    pattern_type: str  # 'reasoning_template', 'action_sequence', 'validation_check', 'question_resolution'
    content: str
    source_insights: List[str] = field(default_factory=list)
    frequency: int = 1
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 0.7
    compiled: bool = False
    habit_id: Optional[str] = None
    # NOVO v107: execution tracking
    execution_history: List[Dict] = field(default_factory=list)
    avg_success_rate: float = 0.0


@dataclass
class CompiledHabit:
    """Hábito compilado pronto para execução zero-inference."""
    habit_id: str
    pattern_type: str
    trigger: str
    action: Dict
    confidence: float
    compiled_at: str
    # NOVO v107: composition e analytics
    sub_habits: List[str] = field(default_factory=list)  # IDs de hábitos compostos
    is_composite: bool = False
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_executed: Optional[str] = None
    avg_execution_time_ms: float = 0.0


class HabitDatabase:
    """SQLite backend para analytics de execução."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa schema do banco."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    habit_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    trigger_text TEXT,
                    success BOOLEAN,
                    execution_time_ms REAL,
                    context TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_type TEXT,
                    content TEXT,
                    frequency INTEGER,
                    confidence REAL,
                    first_seen TEXT,
                    last_seen TEXT,
                    compiled BOOLEAN
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_executions_habit 
                ON executions(habit_id)
            """)
            conn.commit()
    
    def log_execution(self, habit_id: str, trigger_text: str, success: bool, 
                      execution_time_ms: float = 0, context: str = ""):
        """Registra execução de hábito."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO executions (habit_id, timestamp, trigger_text, success, execution_time_ms, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (habit_id, datetime.now().isoformat(), trigger_text, success, 
                  execution_time_ms, context))
            conn.commit()
    
    def get_success_rate(self, habit_id: str, days: int = 30) -> float:
        """Calcula taxa de sucesso de um hábito."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END)
                FROM executions
                WHERE habit_id = ? AND timestamp > ?
            """, (habit_id, cutoff))
            total, successes = cursor.fetchone()
            if total == 0:
                return 0.0
            return successes / total
    
    def get_top_habits(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Retorna hábitos mais executados."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT habit_id, COUNT(*) as count
                FROM executions
                GROUP BY habit_id
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()


class HabitCompilerV107:
    """
    Compilador de hábitos v107 — com analytics e composition.
    
    NOVO:
    - Pattern extraction de QUESTIONs resolvidas
    - Habit composition (hábitos compostos)
    - Auto-threshold calibration via execution feedback
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or HABIT_CONFIG
        self.patterns: Dict[str, Pattern] = {}
        self.habits: Dict[str, CompiledHabit] = {}
        self.db = HabitDatabase(PATHS["habits_db"])
        self._ensure_dirs()
        self._load_meta()
    
    def _ensure_dirs(self):
        """Cria estrutura de diretórios CACM-aware."""
        for path in [PATHS["habits_compiled"], PATHS["insights_consolidated"],
                     PATHS["questions_resolved"]]:
            path.mkdir(parents=True, exist_ok=True)
    
    def _load_meta(self):
        """Carrega metadados de hábitos existentes."""
        if PATHS["habits_meta"].exists():
            with open(PATHS["habits_meta"], 'r') as f:
                meta = json.load(f)
                for habit_data in meta.get("habits", []):
                    # Handle v87 -> v107 migration
                    habit = CompiledHabit(**{k: v for k, v in habit_data.items() 
                                             if k in CompiledHabit.__dataclass_fields__})
                    self.habits[habit.habit_id] = habit
    
    def _save_meta(self):
        """Salva metadados de hábitos."""
        meta = {
            "last_updated": datetime.now().isoformat(),
            "cycle": 107,
            "habit_count": len(self.habits),
            "config": self.config,
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
        return f"H107-{pattern.pattern_type[:3].upper()}-{timestamp}-{pattern.frequency}"
    
    def extract_patterns_from_insight(self, insight_path: Path) -> List[Pattern]:
        """Extrai padrões de um arquivo de insight."""
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
                confidence=0.8
            ))
        
        # Pattern: Action sequences
        action_matches = re.findall(r'(?:first|1\.)\s+(.+?)\s+(?:then|2\.)\s+(.+?)\s+(?:finally|3\.)\s+(.+?)(?:\.|\n)', content, re.IGNORECASE)
        for step1, step2, step3 in action_matches:
            pattern_content = f"SEQ: {step1.strip()} → {step2.strip()} → {step3.strip()}"
            patterns.append(Pattern(
                pattern_type="action_sequence",
                content=pattern_content,
                source_insights=[insight_path.stem],
                frequency=1,
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
                confidence=0.7
            ))
        
        return patterns
    
    def extract_patterns_from_questions(self) -> List[Pattern]:
        """
        NOVO v107: Extrai padrões de QUESTIONs resolvidas.
        
        QUESTIONs resolvidas contêm patterns de resolução de problemas
        que podem ser compilados em hábitos.
        """
        patterns = []
        
        if not PATHS["questions_resolved"].exists():
            return patterns
        
        for question_file in PATHS["questions_resolved"].glob("*.md"):
            with open(question_file, 'r') as f:
                content = f.read()
            
            # Pattern: Resolution strategy
            resolution_matches = re.findall(
                r'(?:resolution|solution|answer):\s*(.+?)(?:\n\n|\Z)', 
                content, re.IGNORECASE | re.DOTALL
            )
            for resolution in resolution_matches:
                pattern_content = f"RESOLVED: {resolution.strip()[:200]}"
                patterns.append(Pattern(
                    pattern_type="question_resolution",
                    content=pattern_content,
                    source_insights=[question_file.stem],
                    frequency=1,
                    confidence=0.85  # QUESTIONs resolvidas têm confiança maior
                ))
            
            # Pattern: Evidence-based conclusion
            evidence_matches = re.findall(
                r'(?:evidence|based on|from)\s+(.+?)\s+(?:conclude|conclusion|determine)\s+(.+?)(?:\.|\n)',
                content, re.IGNORECASE
            )
            for evidence, conclusion in evidence_matches:
                pattern_content = f"EVIDENCE: {evidence.strip()} → CONCLUSION: {conclusion.strip()}"
                patterns.append(Pattern(
                    pattern_type="evidence_based_reasoning",
                    content=pattern_content,
                    source_insights=[question_file.stem],
                    frequency=1,
                    confidence=0.9
                ))
        
        return patterns
    
    def scan_all_sources(self) -> int:
        """
        Escaneia todas as fontes de patterns:
        - Insights consolidados
        - QUESTIONs resolvidas
        """
        new_patterns = 0
        
        # Insights consolidados
        if PATHS["insights_consolidated"].exists():
            for insight_file in PATHS["insights_consolidated"].glob("*.md"):
                patterns = self.extract_patterns_from_insight(insight_file)
                new_patterns += self._merge_patterns(patterns, insight_file.stem)
        
        # QUESTIONs resolvidas
        question_patterns = self.extract_patterns_from_questions()
        new_patterns += self._merge_patterns(question_patterns, "questions")
        
        return new_patterns
    
    def _merge_patterns(self, patterns: List[Pattern], source: str) -> int:
        """Merge patterns detectados com existentes."""
        new_count = 0
        
        for pattern in patterns:
            pattern_id = self._generate_pattern_id(pattern.content)
            
            if pattern_id in self.patterns:
                existing = self.patterns[pattern_id]
                existing.frequency += 1
                if source not in existing.source_insights:
                    existing.source_insights.append(source)
                existing.last_seen = datetime.now().isoformat()
                existing.confidence = min(0.95, existing.confidence + 0.03)
            else:
                pattern.source_insights = [source]
                self.patterns[pattern_id] = pattern
                new_count += 1
        
        return new_count
    
    def find_composable_habits(self) -> List[List[CompiledHabit]]:
        """
        NOVO v107: Encontra hábitos que podem ser compostos.
        
        Hábitos compostos quando:
        - Mesmo pattern_type
        - Triggers similares (overlap > 0.7)
        - Ambos com confidence > composition_threshold
        """
        compositions = []
        habits_list = list(self.habits.values())
        
        for i, habit1 in enumerate(habits_list):
            if habit1.confidence < self.config["composition_threshold"]:
                continue
            
            for habit2 in habits_list[i+1:]:
                if habit2.confidence < self.config["composition_threshold"]:
                    continue
                
                if habit1.pattern_type == habit2.pattern_type:
                    # Check trigger similarity (simple overlap)
                    trigger1 = set(habit1.trigger.lower().split())
                    trigger2 = set(habit2.trigger.lower().split())
                    if len(trigger1) > 0 and len(trigger2) > 0:
                        overlap = len(trigger1 & trigger2) / len(trigger1 | trigger2)
                        if overlap > 0.5:
                            compositions.append([habit1, habit2])
        
        return compositions
    
    def create_composite_habit(self, habits: List[CompiledHabit]) -> Optional[CompiledHabit]:
        """
        NOVO v107: Cria hábito composto de múltiplos hábitos.
        """
        if len(habits) < 2:
            return None
        
        # Composite ID
        ids = [h.habit_id.split('-')[1] for h in habits]
        composite_id = f"H107-COMP-{''.join(ids)}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Composite trigger (union of triggers)
        triggers = [h.trigger for h in habits]
        composite_trigger = " | ".join(triggers[:2])  # Limita a 2 para evitar complexidade
        
        # Composite action (sequence of actions)
        composite_action = {
            "type": "composite",
            "sub_actions": [h.action for h in habits],
            "execute": f"Execute composite: {' then '.join([h.habit_id for h in habits])}"
        }
        
        # Confidence é média ponderada
        avg_confidence = sum(h.confidence for h in habits) / len(habits)
        
        composite = CompiledHabit(
            habit_id=composite_id,
            pattern_type=f"composite_{habits[0].pattern_type}",
            trigger=composite_trigger,
            action=composite_action,
            confidence=avg_confidence,
            compiled_at=datetime.now().isoformat(),
            sub_habits=[h.habit_id for h in habits],
            is_composite=True
        )
        
        return composite
    
    def auto_calibrate_thresholds(self):
        """
        NOVO v107: Auto-calibra thresholds baseado em performance.
        
        Se success_rate < target: aumenta confidence_threshold
        Se success_rate > target: pode diminuir para compilar mais
        """
        if not self.config["auto_calibrate"]:
            return
        
        # Calcula success rate global
        total_execs = sum(h.execution_count for h in self.habits.values())
        total_success = sum(h.success_count for h in self.habits.values())
        
        if total_execs == 0:
            return
        
        global_success_rate = total_success / total_execs
        target = self.config["success_rate_target"]
        
        # Ajusta confidence_threshold
        old_threshold = self.config["confidence_threshold"]
        
        if global_success_rate < target * 0.9:  # 10% abaixo do target
            self.config["confidence_threshold"] = min(0.95, old_threshold + 0.05)
            print(f"   Auto-calibration: ↑ confidence_threshold {old_threshold:.2f} → {self.config['confidence_threshold']:.2f}")
        elif global_success_rate > target * 1.1:  # 10% acima do target
            self.config["confidence_threshold"] = max(0.5, old_threshold - 0.03)
            print(f"   Auto-calibration: ↓ confidence_threshold {old_threshold:.2f} → {self.config['confidence_threshold']:.2f}")
    
    def calculate_compilation_candidates(self) -> List[Pattern]:
        """Identifica padrões prontos para compilação."""
        candidates = []
        
        for pattern in self.patterns.values():
            if (pattern.frequency >= self.config["frequency_threshold"] and
                pattern.confidence >= self.config["confidence_threshold"] and
                not pattern.compiled):
                candidates.append(pattern)
        
        candidates.sort(key=lambda p: p.confidence * p.frequency, reverse=True)
        return candidates
    
    def compile_habit(self, pattern: Pattern) -> Optional[CompiledHabit]:
        """Compila um padrão em hábito executável."""
        habit_id = self._generate_habit_id(pattern)
        
        # Gera trigger e action baseado no tipo
        if pattern.pattern_type == "reasoning_template":
            match = re.match(r'IF\s+(.+?)\s+THEN\s+(.+)', pattern.content, re.IGNORECASE)
            if match:
                trigger = match.group(1).lower()
                action_desc = match.group(2)
                action = {"type": "reasoning", "description": action_desc, "execute": f"Apply: {action_desc}"}
            else:
                trigger = pattern.content.lower()[:50]
                action = {"type": "reasoning", "execute": pattern.content}
        
        elif pattern.pattern_type == "action_sequence":
            steps = pattern.content.replace("SEQ: ", "").split(" → ")
            trigger = steps[0].lower()[:30] if steps else "sequence"
            action = {"type": "sequence", "steps": steps, "execute": f"Sequence: {' → '.join(steps)}"}
        
        elif pattern.pattern_type == "validation_check":
            check = pattern.content.replace("CHECK: ", "")
            trigger = check.lower()[:40]
            action = {"type": "validation", "check": check, "execute": f"Validate: {check}"}
        
        elif pattern.pattern_type == "question_resolution":
            trigger = pattern.content.lower()[:60]
            action = {"type": "resolution", "pattern": pattern.content, "execute": "Apply resolution pattern"}
        
        elif pattern.pattern_type == "evidence_based_reasoning":
            trigger = pattern.content.lower()[:50]
            action = {"type": "evidence_reasoning", "execute": pattern.content}
        
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
        
        # Salva hábito
        habit_path = PATHS["habits_compiled"] / f"{habit_id}.json"
        with open(habit_path, 'w') as f:
            json.dump(asdict(habit), f, indent=2)
        
        pattern.compiled = True
        pattern.habit_id = habit_id
        
        return habit
    
    def compile_candidates(self, max_compile: int = 10) -> List[CompiledHabit]:
        """Compila candidatos em hábitos."""
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
            "cycle": 107,
            "compiled_count": len(habits),
            "habits": [h.habit_id for h in habits],
            "config": self.config
        }
        
        mode = 'a' if PATHS["habits_log"].exists() else 'w'
        with open(PATHS["habits_log"], mode) as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def execute_habit(self, trigger_text: str, context: str = "") -> Optional[CompiledHabit]:
        """
        Executa hábito baseado em trigger (zero-inference).
        
        NOVO v107: Registra execução no banco para analytics.
        """
        trigger_lower = trigger_text.lower()
        start_time = datetime.now()
        
        for habit in self.habits.values():
            if habit.trigger in trigger_lower or trigger_lower in habit.trigger:
                habit.execution_count += 1
                habit.last_executed = datetime.now().isoformat()
                
                exec_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                habit.avg_execution_time_ms = (
                    (habit.avg_execution_time_ms * (habit.execution_count - 1) + exec_time_ms)
                    / habit.execution_count
                )
                
                self._save_meta()
                return habit
        
        return None
    
    def report_execution(self, habit_id: str, success: bool, context: str = ""):
        """
        NOVO v107: Reporta sucesso/falha de execução para analytics.
        """
        if habit_id in self.habits:
            habit = self.habits[habit_id]
            if success:
                habit.success_count += 1
            else:
                habit.failure_count += 1
            
            self.db.log_execution(habit_id, habit.trigger, success, context=context)
            self._save_meta()
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas completas."""
        total_execs = sum(h.execution_count for h in self.habits.values())
        total_success = sum(h.success_count for h in self.habits.values())
        
        success_rate = total_success / total_execs if total_execs > 0 else 0
        
        return {
            "total_patterns": len(self.patterns),
            "compiled_habits": len(self.habits),
            "composite_habits": len([h for h in self.habits.values() if h.is_composite]),
            "candidates_pending": len(self.calculate_compilation_candidates()),
            "total_executions": total_execs,
            "success_rate": f"{success_rate:.1%}",
            "by_type": defaultdict(int, {
                k: len([p for p in self.patterns.values() if p.pattern_type == k])
                for k in set(p.pattern_type for p in self.patterns.values())
            }),
            "config": self.config
        }
    
    def get_analytics(self) -> Dict:
        """NOVO v107: Retorna analytics de execução."""
        top_habits = self.db.get_top_habits(5)
        
        return {
            "top_executed": [
                {"habit_id": h[0], "count": h[1], "success_rate": f"{self.db.get_success_rate(h[0]):.1%}"}
                for h in top_habits
            ],
            "global_success_rate": self.db.get_success_rate("*"),
            "habits_with_data": len([h for h in self.habits.values() if h.execution_count > 0])
        }


def main():
    """Entry point do compilador v107."""
    print("=" * 70)
    print("Eve Habit Compiler v107 — Ciclo #107")
    print("Baseado em: Tri-Spirit + Ciclo #107 Convergência")
    print("NOVO: Question patterns, Composition, Auto-calibration")
    print("=" * 70)
    
    compiler = HabitCompilerV107()
    
    # Passo 1: Escaneia todas as fontes
    print("\n📊 Escaneando fontes de patterns...")
    new_patterns = compiler.scan_all_sources()
    print(f"   Novos padrões detectados: {new_patterns}")
    
    # Passo 2: Auto-calibração
    print("\n⚙️  Auto-calibrando thresholds...")
    compiler.auto_calibrate_thresholds()
    
    # Passo 3: Estatísticas
    stats = compiler.get_stats()
    print(f"\n📈 Estatísticas:")
    print(f"   Total de padrões: {stats['total_patterns']}")
    print(f"   Hábitos compilados: {stats['compiled_habits']} (composites: {stats['composite_habits']})")
    print(f"   Candidatos pendentes: {stats['candidates_pending']}")
    print(f"   Execuções totais: {stats['total_executions']}")
    print(f"   Taxa de sucesso: {stats['success_rate']}")
    print(f"   Por tipo: {dict(stats['by_type'])}")
    
    # Passo 4: Encontra composições
    print("\n🔗 Analisando composições possíveis...")
    compositions = compiler.find_composable_habits()
    if compositions:
        print(f"   {len(compositions)} composições identificadas")
        for habits in compositions[:3]:  # Limita a 3
            ids = [h.habit_id for h in habits]
            print(f"   • {ids[0][:20]}... + {ids[1][:20]}...")
    
    # Passo 5: Compilação
    print(f"\n🔨 Compilando hábitos...")
    compiled = compiler.compile_candidates(max_compile=5)
    
    if compiled:
        print(f"\n✅ Hábitos compilados: {len(compiled)}")
        for habit in compiled:
            print(f"   • {habit.habit_id} ({habit.pattern_type}, conf: {habit.confidence:.2f})")
    else:
        print("\n⏳ Nenhum candidato pronto para compilação.")
    
    # Passo 6: Analytics
    print("\n📊 Analytics:")
    analytics = compiler.get_analytics()
    print(f"   Hábitos com dados: {analytics['habits_with_data']}")
    if analytics['top_executed']:
        print(f"   Mais executados:")
        for h in analytics['top_executed'][:3]:
            print(f"     - {h['habit_id'][:30]}...: {h['count']}x (SR: {h['success_rate']})")
    
    print("\n" + "=" * 70)
    print("Compilação v107 completa.")
    print("Próximo passo: Integração com Cognitive Companion")
    print("=" * 70)


if __name__ == "__main__":
    main()
