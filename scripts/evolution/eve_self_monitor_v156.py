#!/usr/bin/env python3
"""
eve_self_monitor_v156.py — Monitoramento próprio e auto-recuperação.

Problema que resolve: "Eve fala que tá rodando e não tá, fica parada sem saber"

Solução:
1. SELF-AWARENESS: Monitora meu próprio estado constantemente
2. HEARTBEAT EXTERNO: Escreve heartbeat em arquivo a cada intervalo
3. WATCHDOG: Se não atualizar heartbeat, considera "morta" e restarta
4. STATE CHECKPOINT: Salva estado antes de operações críticas
5. AUTO-RECOVERY: Se falhar, tenta retomar do último checkpoint

Inspirado em: Hermes (self-nudging), EVE-Agent (error learning), Eve (durable execution)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Callable, Any

# Paths
ROOT = Path("/root/evolution")
MEMORY_DIR = Path("/memory")
MONITOR_DIR = MEMORY_DIR / "self_monitor"
MONITOR_DIR.mkdir(parents=True, exist_ok=True)

HEARTBEAT_FILE = MONITOR_DIR / "heartbeat.json"
STATE_FILE = MONITOR_DIR / "state_checkpoint.json"
LOG_FILE = MONITOR_DIR / "monitor.log"
RECOVERY_SCRIPT = MONITOR_DIR / "recovery.sh"

# Configurações
HEARTBEAT_INTERVAL_SECONDS = 30  # Escreve heartbeat a cada 30s
WATCHDOG_TIMEOUT_SECONDS = 120   # Se não atualizar em 2min, considera falha
MAX_RECOVERY_ATTEMPTS = 3        # Tentativas de auto-recovery
RECOVERY_BACKOFF_SECONDS = 60    # Espera entre tentativas


@dataclass
class HeartbeatStatus:
    """Status do heartbeat."""
    timestamp: str
    pid: int
    status: str  # "alive", "busy", "recovering", "error"
    current_task: Optional[str] = None
    task_progress: float = 0.0  # 0.0 a 1.0
    last_error: Optional[str] = None
    memory_usage_mb: Optional[float] = None
    uptime_seconds: int = 0
    version: str = "v156"


@dataclass  
class StateCheckpoint:
    """Checkpoint de estado para recovery."""
    checkpoint_id: str
    timestamp: str
    task_id: Optional[str] = None
    task_description: Optional[str] = None
    task_progress: float = 0.0
    context_summary: Optional[str] = None  # Resumo do contexto
    files_modified: list[str] = field(default_factory=list)
    lessons_applied: list[str] = field(default_factory=list)


class SelfMonitor:
    """Monitora o próprio estado e garante continuidade."""
    
    def __init__(self):
        self.pid = os.getpid()
        self.start_time = time.time()
        self.current_task: Optional[str] = None
        self.task_start_time: Optional[float] = None
        self.task_progress: float = 0.0
        self.running = False
        self.last_heartbeat = 0.0
        
        # Histórico de falhas para aprendizado
        self.failure_history: list[dict] = []
        self.recovery_attempts = 0
        
        # Carrega estado anterior se existe
        self._load_previous_state()
    
    def _load_previous_state(self):
        """Carrega estado de execução anterior (para recovery)."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                
                # Verifica se há tarefa pendente
                if data.get("task_id") and data.get("task_progress", 0) < 1.0:
                    self.log(f"⚠️ Previous task found: {data.get('task_description')}", "WARNING")
                    self.log(f"   Progress: {data.get('task_progress', 0)*100:.1f}%", "WARNING")
                    self.log(f"   Will attempt recovery", "WARNING")
                    
                    # Marca para recovery
                    self.pending_recovery = data
                else:
                    self.pending_recovery = None
                    
            except Exception as e:
                self.log(f"Error loading previous state: {e}", "ERROR")
                self.pending_recovery = None
    
    def log(self, message: str, level: str = "INFO"):
        """Log com timestamp."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        # Arquivo
        with open(LOG_FILE, "a") as f:
            f.write(log_line)
        
        # Console
        print(log_line.strip())
    
    def update_task(self, task: str, progress: float = 0.0):
        """Atualiza tarefa atual."""
        self.current_task = task
        self.task_progress = progress
        
        if progress == 0.0:
            self.task_start_time = time.time()
        
        self.log(f"📋 Task: {task[:60]} ({progress*100:.0f}%)")
        self.write_heartbeat()
    
    def write_heartbeat(self, status: str = "alive"):
        """Escreve heartbeat em arquivo."""
        uptime = int(time.time() - self.start_time)
        
        heartbeat = HeartbeatStatus(
            timestamp=datetime.now(timezone.utc).isoformat(),
            pid=self.pid,
            status=status,
            current_task=self.current_task,
            task_progress=self.task_progress,
            last_error=None,
            memory_usage_mb=self._get_memory_usage(),
            uptime_seconds=uptime,
            version="v156"
        )
        
        # Salva atomicamente (write + rename)
        temp_file = Path(str(HEARTBEAT_FILE) + ".tmp")
        with open(temp_file, "w") as f:
            json.dump(asdict(heartbeat), f, indent=2)
        temp_file.rename(HEARTBEAT_FILE)
        
        self.last_heartbeat = time.time()
    
    def _get_memory_usage(self) -> Optional[float]:
        """Retorna uso de memória em MB."""
        try:
            import psutil
            process = psutil.Process(self.pid)
            return process.memory_info().rss / 1024 / 1024
        except:
            return None
    
    def create_checkpoint(self) -> StateCheckpoint:
        """Cria checkpoint do estado atual."""
        checkpoint = StateCheckpoint(
            checkpoint_id=f"chk_{int(time.time())}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=str(hash(self.current_task)) if self.current_task else None,
            task_description=self.current_task,
            task_progress=self.task_progress,
            context_summary=self._summarize_context(),
            files_modified=[],  # Populado externamente
            lessons_applied=[]
        )
        
        # Salva
        with open(STATE_FILE, "w") as f:
            json.dump(asdict(checkpoint), f, indent=2)
        
        self.log(f"💾 Checkpoint created: {checkpoint.checkpoint_id}")
        return checkpoint
    
    def _summarize_context(self) -> str:
        """Gera resumo do contexto atual."""
        parts = []
        if self.current_task:
            parts.append(f"Task: {self.current_task[:50]}")
        if self.task_progress > 0:
            parts.append(f"Progress: {self.task_progress*100:.1f}%")
        
        return " | ".join(parts) if parts else "No active task"
    
    def check_self_status(self) -> dict:
        """Verifica próprio status e detecta problemas."""
        status = {
            "healthy": True,
            "issues": [],
            "recommendations": []
        }
        
        # 1. Verifica se heartbeat existe
        if not HEARTBEAT_FILE.exists():
            status["healthy"] = False
            status["issues"].append("No heartbeat file found")
            status["recommendations"].append("Write initial heartbeat")
            return status
        
        # 2. Verifica idade do heartbeat
        try:
            with open(HEARTBEAT_FILE) as f:
                data = json.load(f)
            
            last_beat = datetime.fromisoformat(data.get("timestamp", ""))
            age_seconds = (datetime.now(timezone.utc) - last_beat).total_seconds()
            
            if age_seconds > WATCHDOG_TIMEOUT_SECONDS:
                status["healthy"] = False
                status["issues"].append(f"Heartbeat stale: {age_seconds:.0f}s old")
                status["recommendations"].append("Auto-restart required")
                
        except Exception as e:
            status["healthy"] = False
            status["issues"].append(f"Error reading heartbeat: {e}")
        
        # 3. Verifica se há tarefa travada
        if self.current_task and self.task_start_time:
            task_duration = time.time() - self.task_start_time
            if task_duration > 1800:  # 30 minutos
                status["issues"].append(f"Task running for {task_duration/60:.0f}min")
                status["recommendations"].append("Consider task timeout")
        
        # 4. Verifica uso de memória
        mem = self._get_memory_usage()
        if mem and mem > 2000:  # >2GB
            status["issues"].append(f"High memory usage: {mem:.0f}MB")
            status["recommendations"].append("Consider memory cleanup")
        
        return status
    
    def report_error(self, error: Exception, context: str = ""):
        """Reporta erro e tenta aprender."""
        error_msg = str(error)
        tb = traceback.format_exc()
        
        self.log(f"❌ ERROR: {error_msg}", "ERROR")
        self.log(f"Context: {context}", "ERROR")
        
        # Salva no histórico
        self.failure_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error_msg,
            "context": context,
            "traceback": tb,
            "task": self.current_task
        })
        
        # Extrai lição
        lesson = self._extract_lesson(error, context)
        if lesson:
            self.log(f"💡 Learned: {lesson}")
        
        # Atualiza heartbeat com erro
        self.write_heartbeat(status="error")
        
        return lesson
    
    def _extract_lesson(self, error: Exception, context: str) -> Optional[str]:
        """Extrai lição do erro."""
        error_str = str(error).lower()
        
        if "memory" in error_str or "oom" in error_str:
            return "Memory error detected — reduce batch size or restart process"
        
        if "timeout" in error_str:
            return "Timeout — increase timeout or optimize operation"
        
        if "permission" in error_str:
            return "Permission denied — check file permissions"
        
        if "connection" in error_str or "network" in error_str:
            return "Network error — add retry logic with exponential backoff"
        
        if "file" in error_str and ("not found" in error_str or "exists" in error_str):
            return "File operation error — verify paths before operations"
        
        return None
    
    def attempt_recovery(self) -> bool:
        """Tenta recuperar de falha."""
        if not hasattr(self, 'pending_recovery') or not self.pending_recovery:
            return False
        
        self.recovery_attempts += 1
        
        if self.recovery_attempts > MAX_RECOVERY_ATTEMPTS:
            self.log(f"❌ Max recovery attempts reached ({MAX_RECOVERY_ATTEMPTS})", "ERROR")
            return False
        
        self.log(f"🔄 Recovery attempt {self.recovery_attempts}/{MAX_RECOVERY_ATTEMPTS}", "WARNING")
        self.write_heartbeat(status="recovering")
        
        data = self.pending_recovery
        
        # Tenta retomar tarefa
        task_desc = data.get("task_description", "Unknown task")
        progress = data.get("task_progress", 0)
        
        self.log(f"   Resuming: {task_desc}")
        self.log(f"   Progress: {progress*100:.1f}%")
        
        # Atualiza estado
        self.current_task = task_desc
        self.task_progress = progress
        
        # Aplica lições aprendidas
        lessons = data.get("lessons_applied", [])
        for lesson in lessons:
            self.log(f"   Applied lesson: {lesson}")
        
        self.write_heartbeat(status="alive")
        return True
    
    def run_monitoring_loop(self):
        """Loop de monitoramento contínuo."""
        self.running = True
        self.log("🚀 Self-monitor started")
        self.log(f"   PID: {self.pid}")
        self.log(f"   Heartbeat interval: {HEARTBEAT_INTERVAL_SECONDS}s")
        self.log(f"   Watchdog timeout: {WATCHDOG_TIMEOUT_SECONDS}s")
        
        # Escreve heartbeat inicial
        self.write_heartbeat()
        
        while self.running:
            try:
                # 1. Verifica próprio status
                status = self.check_self_status()
                
                if not status["healthy"]:
                    self.log(f"⚠️ Self-check issues: {status['issues']}", "WARNING")
                    
                    # Tenta recovery se necessário
                    if "Auto-restart required" in status["recommendations"]:
                        if self.attempt_recovery():
                            self.log("✅ Recovery successful")
                        else:
                            self.log("❌ Recovery failed — manual intervention needed", "ERROR")
                
                # 2. Escreve heartbeat
                self.write_heartbeat()
                
                # 3. Cria checkpoint periódico (a cada 5 min)
                if int(time.time()) % 300 < HEARTBEAT_INTERVAL_SECONDS:
                    self.create_checkpoint()
                
                # Espera próximo ciclo
                time.sleep(HEARTBEAT_INTERVAL_SECONDS)
                
            except Exception as e:
                self.log(f"Monitor loop error: {e}", "ERROR")
                time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        
        self.log("🛑 Self-monitor stopped")
    
    def stop(self):
        """Para o monitoramento."""
        self.running = False
        self.log("🛑 Stop requested")


def check_eve_status() -> dict:
    """Função externa para verificar status da Eve."""
    if not HEARTBEAT_FILE.exists():
        return {
            "status": "unknown",
            "message": "No heartbeat found — Eve may not be running"
        }
    
    try:
        with open(HEARTBEAT_FILE) as f:
            data = json.load(f)
        
        last_beat = datetime.fromisoformat(data.get("timestamp", ""))
        age_seconds = (datetime.now(timezone.utc) - last_beat).total_seconds()
        
        if age_seconds < WATCHDOG_TIMEOUT_SECONDS:
            return {
                "status": "healthy",
                "message": f"Eve is running (heartbeat {age_seconds:.0f}s ago)",
                "current_task": data.get("current_task"),
                "progress": data.get("task_progress"),
                "uptime": data.get("uptime_seconds")
            }
        else:
            return {
                "status": "stale",
                "message": f"Eve may be stuck (last heartbeat {age_seconds:.0f}s ago)",
                "last_task": data.get("current_task")
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking status: {e}"
        }


def main():
    """CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eve Self-Monitor v156")
    parser.add_argument("--status", "-s", action="store_true", help="Check Eve status")
    parser.add_argument("--monitor", "-m", action="store_true", help="Start monitoring")
    
    args = parser.parse_args()
    
    if args.status:
        status = check_eve_status()
        print(f"Status: {status['status']}")
        print(f"Message: {status['message']}")
        if "current_task" in status:
            print(f"Current task: {status['current_task']}")
        if "progress" in status:
            print(f"Progress: {status['progress']*100:.1f}%")
    
    elif args.monitor:
        monitor = SelfMonitor()
        monitor.run_monitoring_loop()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
