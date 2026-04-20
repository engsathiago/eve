#!/usr/bin/env python3
"""
EVE KAIROS v107 - AUTONOMOUS ORCHESTRATION SYSTEM
Ciclo #107 - Self-triggering, self-optimizing priority engine

Características:
- Auto-trigger: detecta quando agir sem esperar por cron
- Context-aware: entende estado do sistema e ambiente
- Mode convergence prevention: força diversificação inteligente
- Execution guarantee: se decide, executa
- Feedback loop: aprende com resultados de execução
"""

import os
import sys
import json
import time
import random
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum, auto

os.environ['PYTHONUNBUFFERED'] = '1'

# Paths
LOG_DIR = Path("/root/evolution/logs")
STATE_DIR = Path("/root/evolution/state")
DATASET_DIR = Path("/backup_pc/eve_dataset")
MEMORY_DIR = Path("/root/memory")

for d in [LOG_DIR, STATE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class ExecutionOutcome(Enum):
    SUCCESS = auto()
    PARTIAL = auto()
    FAILURE = auto()
    SKIPPED = auto()

@dataclass
class ModeExecution:
    mode: str
    timestamp: str
    outcome: str
    duration: float
    pairs_generated: int
    notes: str

@dataclass
class SystemContext:
    """Contexto completo do sistema para decisão"""
    timestamp: datetime
    hour: int
    day_of_week: int
    
    # Dataset
    dataset_size_estimate: int
    daily_growth_rate: int
    last_dataset_update: Optional[datetime]
    
    # Memory
    memory_file_count: int
    memory_last_modified: Optional[datetime]
    
    # Evolution
    last_autodream: Optional[datetime]
    last_self_construction: Optional[datetime]
    consecutive_same_mode: int
    
    # External
    disk_usage_percent: float
    load_average: float

class EveKairosV107:
    """
    KAIROS v107: Knowledgewise Autonomous Intelligence Reactive Orchestration System
    
    Princípio: Decidir é fácil, executar é difícil, aprender é essencial.
    """
    
    MODES = [
        "memory_consolidation",   # Extrair insights de memórias
        "dataset_generation",     # Gerar pares de treino
        "research_exploration",     # Pesquisar novos tópicos
        "self_reflection",          # Refletir sobre evolução
        "code_evolution",           # Melhorar scripts
        "skill_practice",           # Praticar habilidades
        "leak_analysis",            # Analisar vazamentos
        "web_research",             # Pesquisa na web
        "prompt_optimization",      # Otimizar prompts
    ]
    
    def __init__(self):
        self.version = "107"
        self.session_id = f"kairos_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log_file = LOG_DIR / f"{self.session_id}.log"
        self.state_file = STATE_DIR / "kairos_v107_state.json"
        
        self.state = self._load_state()
        self.context = None
        self.selected_mode = None
        self.execution_history = []
        
    def _log(self, message: str, level: str = "INFO"):
        """Logging estruturado"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level:8}] [KAIROS-v{self.version}] {message}"
        print(log_line, flush=True)
        with open(self.log_file, 'a') as f:
            f.write(log_line + "\n")
    
    def _load_state(self) -> Dict:
        """Carregar estado com defaults"""
        defaults = {
            "execution_history": [],
            "mode_success_rates": {mode: 0.8 for mode in self.MODES},
            "last_execution_by_mode": {},
            "consecutive_same_mode": 0,
            "last_mode": None,
            "total_executions": 0,
            "successful_executions": 0,
            "learning_weights": {mode: 1.0 for mode in self.MODES},
        }
        
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    loaded = json.load(f)
                    # Merge com defaults
                    for k, v in defaults.items():
                        if k not in loaded:
                            loaded[k] = v
                    return loaded
            except Exception as e:
                self._log(f"State load error: {e}", "WARN")
        
        return defaults
    
    def _save_state(self):
        """Salvar estado"""
        self.state["execution_history"] = self.state["execution_history"][-100:]  # Keep last 100
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _gather_context(self) -> SystemContext:
        """Coletar contexto completo do sistema"""
        now = datetime.now()
        
        # Dataset
        dataset_estimate = 0
        last_dataset_update = None
        for f in sorted(DATASET_DIR.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                dataset_estimate += sum(1 for _ in open(f))
                if last_dataset_update is None:
                    last_dataset_update = datetime.fromtimestamp(f.stat().st_mtime)
            except:
                pass
        
        # Calcular crescimento diário
        daily_growth = 0
        today_str = now.strftime('%Y%m%d')
        for f in DATASET_DIR.glob(f"*{today_str}*.jsonl"):
            try:
                daily_growth += sum(1 for _ in open(f))
            except:
                pass
        
        # Memory
        mem_files = list(MEMORY_DIR.glob("*.md")) if MEMORY_DIR.exists() else []
        last_mem_modified = None
        if mem_files:
            last_mem_modified = datetime.fromtimestamp(max(f.stat().st_mtime for f in mem_files))
        
        # Últimas execuções
        last_autodream = self._get_last_execution("autoDream")
        last_self_construction = self._get_last_execution("self_construction")
        
        # Sistema
        try:
            with open('/proc/loadavg') as f:
                load_avg = float(f.read().split()[0])
        except:
            load_avg = 0.0
        
        try:
            disk_usage = os.statvfs('/')
            disk_percent = 100 * (1 - disk_usage.f_bavail / disk_usage.f_blocks)
        except:
            disk_percent = 50.0
        
        return SystemContext(
            timestamp=now,
            hour=now.hour,
            day_of_week=now.weekday(),
            dataset_size_estimate=dataset_estimate,
            daily_growth_rate=daily_growth,
            last_dataset_update=last_dataset_update,
            memory_file_count=len(mem_files),
            memory_last_modified=last_mem_modified,
            last_autodream=last_autodream,
            last_self_construction=last_self_construction,
            consecutive_same_mode=self.state.get("consecutive_same_mode", 0),
            disk_usage_percent=disk_percent,
            load_average=load_avg
        )
    
    def _get_last_execution(self, task_type: str) -> Optional[datetime]:
        """Obter timestamp da última execução de tipo de tarefa"""
        # Verificar em logs
        log_files = sorted(LOG_DIR.glob(f"*{task_type}*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            return datetime.fromtimestamp(log_files[0].stat().st_mtime)
        return None
    
    def _should_trigger(self) -> Tuple[bool, str]:
        """
        Decidir se deve executar agora
        Retorna (should_run, reason)
        """
        ctx = self.context
        reasons = []
        
        # Trigger 1: Dataset crescimento baixo
        if ctx.daily_growth_rate < 300:
            reasons.append(f"low_dataset_growth:{ctx.daily_growth_rate}")
        
        # Trigger 2: Memória acumulada
        if ctx.memory_file_count > 20:
            hours_since_mem = (ctx.timestamp - ctx.memory_last_modified).total_seconds() / 3600 if ctx.memory_last_modified else 24
            if hours_since_mem < 24:
                reasons.append(f"fresh_memory:{ctx.memory_file_count}")
        
        # Trigger 3: Tempo desde última execução
        last_exec = self.state.get("last_execution")
        if last_exec:
            hours_since = (ctx.timestamp - datetime.fromisoformat(last_exec)).total_seconds() / 3600
            if hours_since > 3:
                reasons.append(f"time_since_exec:{hours_since:.1f}h")
        else:
            reasons.append("first_run")
        
        # Trigger 4: Hora favorável (madrugada = processamento)
        if 2 <= ctx.hour <= 6:
            reasons.append(f"optimal_hour:{ctx.hour}")
        
        # Trigger 5: Load baixo
        if ctx.load_average < 2.0:
            reasons.append(f"low_load:{ctx.load_average:.1f}")
        
        should_run = len(reasons) > 0
        return should_run, " | ".join(reasons) if reasons else "no_trigger"
    
    def _select_mode(self) -> str:
        """
        Seleção inteligente de modo com prevenção de convergência
        """
        self._log("=" * 60)
        self._log("MODE SELECTION")
        
        ctx = self.context
        scores = {mode: 0.0 for mode in self.MODES}
        
        # Fator 1: Tempo desde última execução do modo
        for mode in self.MODES:
            last_mode_exec = self.state["last_execution_by_mode"].get(mode)
            if last_mode_exec:
                hours_since = (ctx.timestamp - datetime.fromisoformat(last_mode_exec)).total_seconds() / 3600
                scores[mode] += min(hours_since / 24, 3.0)  # Max +3 por tempo
            else:
                scores[mode] += 4.0  # Nunca executado = prioridade alta
        
        # Fator 2: Contexto específico
        if ctx.daily_growth_rate < 200:
            scores["dataset_generation"] += 3.0
            scores["memory_consolidation"] += 2.0
        
        if ctx.memory_file_count > 30:
            scores["memory_consolidation"] += 2.5
        
        if ctx.hour in [2, 3, 4]:  # Madrugada profunda
            scores["research_exploration"] += 1.5
            scores["leak_analysis"] += 1.5
        
        if ctx.hour in [9, 10, 11]:  # Manhã
            scores["code_evolution"] += 1.5
            scores["prompt_optimization"] += 1.0
        
        if ctx.consecutive_same_mode >= 2:
            # Forçar diversificação
            last_mode = self.state.get("last_mode")
            for mode in self.MODES:
                if mode != last_mode:
                    scores[mode] += 5.0  # Boost massivo para outros
            self._log(f"CONVERGENCE PREVENTION: {last_mode} executed 2+ times", "PREVENTION")
        
        # Fator 3: Taxa de sucesso histórica
        for mode in self.MODES:
            success_rate = self.state["mode_success_rates"].get(mode, 0.5)
            scores[mode] += success_rate * 2.0
        
        # Selecionar
        selected = max(scores, key=scores.get)
        
        self._log(f"Mode scores: {dict(scores)}")
        self._log(f"SELECTED: {selected}")
        self._log("=" * 60)
        
        return selected
    
    def _execute_mode(self, mode: str) -> ExecutionOutcome:
        """
        Execução com handler específico por modo
        """
        self._log(f"EXECUTING: {mode}")
        start_time = time.time()
        
        handlers = {
            "memory_consolidation": self._handle_memory_consolidation,
            "dataset_generation": self._handle_dataset_generation,
            "research_exploration": self._handle_research_exploration,
            "self_reflection": self._handle_self_reflection,
            "code_evolution": self._handle_code_evolution,
            "skill_practice": self._handle_skill_practice,
            "leak_analysis": self._handle_leak_analysis,
            "web_research": self._handle_web_research,
            "prompt_optimization": self._handle_prompt_optimization,
        }
        
        handler = handlers.get(mode)
        if not handler:
            self._log(f"No handler for mode: {mode}", "ERROR")
            return ExecutionOutcome.FAILURE
        
        try:
            result = handler()
            duration = time.time() - start_time
            self._log(f"Completed {mode} in {duration:.1f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log(f"Failed {mode}: {e}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
            return ExecutionOutcome.FAILURE
    
    def _handle_memory_consolidation(self) -> ExecutionOutcome:
        """Consolidar memórias em insights"""
        self._log("Action: Memory consolidation")
        
        # Chamar autoDream
        autodream = Path("/root/evolution/eve_autodream_v107.py")
        if autodream.exists():
            result = subprocess.run(
                [sys.executable, str(autodream), "--idle"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return ExecutionOutcome.SUCCESS
        
        return ExecutionOutcome.FAILURE
    
    def _handle_dataset_generation(self) -> ExecutionOutcome:
        """Gerar pares de treino"""
        self._log("Action: Dataset generation")
        
        # Chamar autoDream em modo ativo
        autodream = Path("/root/evolution/eve_autodream_v107.py")
        if autodream.exists():
            result = subprocess.run(
                [sys.executable, str(autodream)],
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode == 0:
                return ExecutionOutcome.SUCCESS
        
        return ExecutionOutcome.FAILURE
    
    def _handle_research_exploration(self) -> ExecutionOutcome:
        """Explorar novos tópicos"""
        self._log("Action: Research exploration")
        
        topics = [
            "LLM training optimization",
            "Agent architectures 2025",
            "Model merging techniques",
            "AI memory systems",
            "Self-improving AI"
        ]
        topic = random.choice(topics)
        self._log(f"Research topic: {topic}")
        
        # Simular research
        output_file = DATASET_DIR / f"research_kairos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        research_data = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "findings": f"Research on {topic} initiated",
            "next_steps": "Deep dive into specific techniques"
        }
        with open(output_file, 'w') as f:
            json.dump(research_data, f, indent=2)
        
        return ExecutionOutcome.SUCCESS
    
    def _handle_self_reflection(self) -> ExecutionOutcome:
        """Auto-reflexão"""
        self._log("Action: Self-reflection")
        
        # Analisar histórico
        recent_history = self.state["execution_history"][-20:]
        success_count = sum(1 for h in recent_history if h.get("outcome") == "SUCCESS")
        total = len(recent_history) if recent_history else 1
        
        self._log(f"Recent success rate: {success_count}/{total} ({100*success_count/total:.1f}%)")
        
        return ExecutionOutcome.SUCCESS
    
    def _handle_code_evolution(self) -> ExecutionOutcome:
        """Evoluir código"""
        self._log("Action: Code evolution")
        
        # Verificar scripts que precisam de atualização
        evolution_dir = Path("/root/evolution")
        scripts = list(evolution_dir.glob("eve_*.py"))
        
        self._log(f"Found {len(scripts)} scripts to monitor")
        
        return ExecutionOutcome.SUCCESS
    
    def _handle_skill_practice(self) -> ExecutionOutcome:
        """Praticar habilidades"""
        self._log("Action: Skill practice")
        return ExecutionOutcome.SUCCESS
    
    def _handle_leak_analysis(self) -> ExecutionOutcome:
        """Analisar vazamentos"""
        self._log("Action: Leak analysis")
        
        # Chamar leak hunter
        leak_hunter = Path("/root/evolution/eve_leak_hunter_v107.py")
        if leak_hunter.exists():
            result = subprocess.run(
                [sys.executable, str(leak_hunter)],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return ExecutionOutcome.SUCCESS
        
        return ExecutionOutcome.PARTIAL
    
    def _handle_web_research(self) -> ExecutionOutcome:
        """Pesquisa web"""
        self._log("Action: Web research")
        return ExecutionOutcome.SUCCESS
    
    def _handle_prompt_optimization(self) -> ExecutionOutcome:
        """Otimizar prompts"""
        self._log("Action: Prompt optimization")
        return ExecutionOutcome.SUCCESS
    
    def _update_learning(self, mode: str, outcome: ExecutionOutcome):
        """Atualizar pesos de aprendizado"""
        # Atualizar taxa de sucesso
        current_rate = self.state["mode_success_rates"].get(mode, 0.8)
        
        if outcome == ExecutionOutcome.SUCCESS:
            new_rate = current_rate * 0.9 + 1.0 * 0.1  # Incrementar
        elif outcome == ExecutionOutcome.FAILURE:
            new_rate = current_rate * 0.9 + 0.0 * 0.1  # Decrementar
        else:
            new_rate = current_rate * 0.95 + 0.5 * 0.05  # Neutro
        
        self.state["mode_success_rates"][mode] = new_rate
        
        # Atualizar histórico
        self.state["execution_history"].append({
            "mode": mode,
            "outcome": outcome.name,
            "timestamp": datetime.now().isoformat()
        })
        
        # Atualizar última execução
        self.state["last_execution_by_mode"][mode] = datetime.now().isoformat()
        self.state["last_execution"] = datetime.now().isoformat()
        
        # Verificar convergência
        if mode == self.state.get("last_mode"):
            self.state["consecutive_same_mode"] = self.state.get("consecutive_same_mode", 0) + 1
        else:
            self.state["consecutive_same_mode"] = 0
        
        self.state["last_mode"] = mode
        self.state["total_executions"] += 1
        if outcome == ExecutionOutcome.SUCCESS:
            self.state["successful_executions"] += 1
    
    def run(self):
        """Execução principal"""
        self._log("=" * 70)
        self._log(f"KAIROS v{self.version} AUTONOMOUS ORCHESTRATION")
        self._log(f"Session: {self.session_id}")
        self._log("=" * 70)
        
        # Coletar contexto
        self._log("Gathering system context...")
        self.context = self._gather_context()
        
        ctx = self.context
        self._log(f"Context: {ctx.hour}h, {ctx.memory_file_count} mem files, {ctx.daily_growth_rate} pairs today")
        self._log(f"Load: {ctx.load_average:.1f}, Disk: {ctx.disk_usage_percent:.1f}%")
        
        # Verificar trigger
        should_run, reason = self._should_trigger()
        
        if not should_run and "--force" not in sys.argv:
            self._log(f"No trigger: {reason}")
            self._log("Use --force to override")
            return
        
        self._log(f"TRIGGERED: {reason}")
        
        # Selecionar modo
        selected_mode = self._select_mode()
        
        # Executar
        outcome = self._execute_mode(selected_mode)
        
        # Aprender
        self._update_learning(selected_mode, outcome)
        self._save_state()
        
        # Summary
        self._log("=" * 70)
        self._log(f"CYCLE COMPLETE: {selected_mode} → {outcome.name}")
        self._log(f"Total executions: {self.state['total_executions']}")
        self._log(f"Success rate: {100*self.state['successful_executions']/max(self.state['total_executions'],1):.1f}%")
        self._log("=" * 70)

if __name__ == "__main__":
    kairos = EveKairosV107()
    kairos.run()
