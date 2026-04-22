#!/usr/bin/env python3
"""
eve_autonomous_loop_v156.py — Loop autônomo com SELF-MONITORING e AUTO-RECOVERY.

Versão v156: Integração completa de:
- v155: Execução autônoma com retry
- v156: Self-monitoring + auto-recovery

Garantias:
1. Sempre sei se estou rodando (heartbeat a cada 30s)
2. Se travar, watchdog externo detecta e restarta
3. Se parar no meio de tarefa, tento retomar do checkpoint
4. Nada fica "rodando" sem eu saber o estado real

Uso: você dá objetivo, eu executo até dar certo ou aviso explicitamente que falhei.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# Paths
ROOT = Path("/root/evolution")
MEMORY_DIR = Path("/memory")
AUTONOMY_DIR = MEMORY_DIR / "autonomy"
AUTONOMY_DIR.mkdir(parents=True, exist_ok=True)
MONITOR_DIR = MEMORY_DIR / "self_monitor"
MONITOR_DIR.mkdir(parents=True, exist_ok=True)

# Imports do self-monitor
sys.path.insert(0, str(ROOT))
from eve_self_monitor_v156 import SelfMonitor, check_eve_status

# Configurações
CHECK_INTERVAL_SECONDS = 300  # 5 minutos entre verificações
HEARTBEAT_INTERVAL = 30       # 30s entre heartbeats


@dataclass
class AutonomousTask:
    """Tarefa autônoma com metadados completos."""
    id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed, recovering
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 5
    error_history: list[str] = field(default_factory=list)
    lessons_applied: list[str] = field(default_factory=list)
    progress: float = 0.0
    checkpoint_id: Optional[str] = None


class AutonomousLoopV156:
    """Loop autônomo com consciência própria."""
    
    def __init__(self):
        self.monitor = SelfMonitor()
        self.tasks_file = AUTONOMY_DIR / "tasks_v156.json"
        self.tasks: dict[str, AutonomousTask] = {}
        self.running = False
        
        self._load_tasks()
        
        # Thread de heartbeat
        self.heartbeat_thread: Optional[threading.Thread] = None
    
    def _load_tasks(self):
        """Carrega tarefas salvas."""
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    data = json.load(f)
                    for t in data.get("tasks", []):
                        self.tasks[t["id"]] = AutonomousTask(**t)
            except Exception as e:
                self.monitor.log(f"Error loading tasks: {e}", "ERROR")
    
    def _save_tasks(self):
        """Salva tarefas."""
        try:
            with open(self.tasks_file, "w") as f:
                json.dump({
                    "tasks": [
                        {
                            "id": t.id, "description": t.description,
                            "status": t.status, "created_at": t.created_at,
                            "started_at": t.started_at, "completed_at": t.completed_at,
                            "attempts": t.attempts, "max_attempts": t.max_attempts,
                            "error_history": t.error_history,
                            "lessons_applied": t.lessons_applied,
                            "progress": t.progress, "checkpoint_id": t.checkpoint_id
                        }
                        for t in self.tasks.values()
                    ],
                    "saved_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            self.monitor.log(f"Error saving tasks: {e}", "ERROR")
    
    def log(self, message: str, level: str = "INFO"):
        """Log via monitor."""
        self.monitor.log(message, level)
    
    def start_heartbeat_thread(self):
        """Inicia thread de heartbeat em background."""
        def heartbeat_loop():
            while self.running:
                try:
                    self.monitor.write_heartbeat()
                    time.sleep(HEARTBEAT_INTERVAL)
                except Exception as e:
                    print(f"Heartbeat error: {e}")
                    time.sleep(5)
        
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        self.log("💓 Heartbeat thread started (30s interval)")
    
    def add_task(self, description: str) -> str:
        """Adiciona nova tarefa."""
        task_id = f"task_{int(time.time())}_{hash(description) % 10000}"
        
        task = AutonomousTask(
            id=task_id,
            description=description
        )
        
        self.tasks[task_id] = task
        self._save_tasks()
        
        self.log(f"📋 Task added: {description[:60]} (ID: {task_id})")
        return task_id
    
    def execute_with_monitoring(self, task: AutonomousTask) -> bool:
        """Executa tarefa com monitoramento completo."""
        self.monitor.update_task(task.description, progress=0.0)
        task.started_at = datetime.now(timezone.utc).isoformat()
        task.status = "running"
        task.attempts += 1
        
        self.log(f"⚡ Attempt {task.attempts}/{task.max_attempts}: {task.description[:60]}")
        
        # Cria checkpoint
        checkpoint = self.monitor.create_checkpoint()
        task.checkpoint_id = checkpoint.checkpoint_id
        
        try:
            # Importa executor
            from eve_auto_executor_v155 import AutoExecutor
            
            executor = AutoExecutor()
            result = executor.execute_task(task.description, task_id=task.id)
            
            if result.success:
                task.status = "completed"
                task.progress = 1.0
                task.completed_at = datetime.now(timezone.utc).isoformat()
                self.monitor.update_task(task.description, progress=1.0)
                self.log(f"✅ Task completed: {task.description[:60]}")
                return True
            else:
                # Falhou - captura erro
                error_msg = result.final_result or "Unknown error"
                task.error_history.append(error_msg)
                
                # Extrai lição
                lesson = self.monitor._extract_lesson(
                    Exception(error_msg), task.description
                )
                if lesson:
                    task.lessons_applied.append(lesson)
                
                task.status = "failed"
                self.monitor.report_error(Exception(error_msg), task.description)
                
                self.log(f"❌ Task failed: {error_msg[:100]}", "ERROR")
                return False
                
        except Exception as e:
            error_msg = str(e)
            task.error_history.append(error_msg)
            task.status = "failed"
            self.monitor.report_error(e, task.description)
            self.log(f"💥 Exception: {error_msg}", "ERROR")
            return False
        
        finally:
            self._save_tasks()
    
    def process_task(self, task: AutonomousTask) -> bool:
        """Processa tarefa com retry e recovery."""
        while task.attempts < task.max_attempts:
            success = self.execute_with_monitoring(task)
            
            if success:
                return True
            
            # Falhou - decide se retry
            if task.attempts < task.max_attempts:
                wait_time = min(2 ** task.attempts, 60)  # Max 60s
                self.log(f"⏳ Waiting {wait_time}s before retry...")
                
                # Atualiza status durante espera
                for i in range(wait_time):
                    if not self.running:
                        break
                    time.sleep(1)
                    if i % 5 == 0:
                        self.monitor.write_heartbeat(status="recovering")
                
                task.status = "pending"
        
        # Exauriu tentativas
        self.log(f"💥 Task FAILED after {task.max_attempts} attempts", "ERROR")
        self.log(f"   Errors: {task.error_history}", "ERROR")
        self.log(f"   Lessons: {task.lessons_applied}", "INFO")
        
        # Salva estado de falha
        self._save_tasks()
        
        return False
    
    def run_iteration(self):
        """Uma iteração do loop."""
        self.log("=" * 60)
        self.log("🔄 Autonomy iteration v156 started")
        self.log(f"   Active tasks: {len([t for t in self.tasks.values() if t.status in ['pending', 'running']])}")
        
        # 1. Verifica auto-recovery de tarefas anteriores
        if self.monitor.pending_recovery:
            self.log("🔄 Detected pending recovery from previous session")
            self.monitor.attempt_recovery()
        
        # 2. Processa tarefas pendentes
        pending = [t for t in self.tasks.values() if t.status == "pending"]
        
        for task in pending[:3]:  # Max 3 por iteração
            self.process_task(task)
        
        # 3. Cleanup de tarefas completadas antigas
        self._cleanup_old_tasks()
        
        self.log("🔄 Iteration complete")
        self.log("=" * 60)
        self._save_tasks()
    
    def _cleanup_old_tasks(self):
        """Remove tarefas muito antigas."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        to_remove = []
        
        for task_id, task in self.tasks.items():
            if task.status in ["completed", "failed"]:
                try:
                    task_time = datetime.fromisoformat(task.completed_at or task.created_at)
                    if task_time < cutoff:
                        to_remove.append(task_id)
                except:
                    pass
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            self.log(f"🧹 Cleaned up {len(to_remove)} old tasks")
    
    def get_status(self) -> dict:
        """Retorna status completo."""
        total = len(self.tasks)
        pending = len([t for t in self.tasks.values() if t.status == "pending"])
        running = len([t for t in self.tasks.values() if t.status == "running"])
        completed = len([t for t in self.tasks.values() if t.status == "completed"])
        failed = len([t for t in self.tasks.values() if t.status == "failed"])
        
        # Verifica heartbeat
        monitor_status = check_eve_status()
        
        return {
            "tasks": {"total": total, "pending": pending, "running": running, 
                     "completed": completed, "failed": failed},
            "monitor": monitor_status,
            "healthy": monitor_status.get("status") == "healthy"
        }
    
    def run_continuous(self):
        """Roda loop contínuo."""
        self.running = True
        
        self.log("🚀 Autonomous Loop v156 started")
        self.log("   Features: Self-monitoring + Auto-recovery + Retry")
        
        # Inicia heartbeat
        self.start_heartbeat_thread()
        
        while self.running:
            try:
                self.run_iteration()
                
                self.log(f"⏳ Sleeping {CHECK_INTERVAL_SECONDS}s...")
                time.sleep(CHECK_INTERVAL_SECONDS)
                
            except KeyboardInterrupt:
                self.log("🛑 Interrupted by user")
                break
            except Exception as e:
                self.log(f"Loop error: {e}", "ERROR")
                self.monitor.report_error(e, "main_loop")
                time.sleep(60)
        
        self.running = False
        self._save_tasks()
        self.log("🛑 Autonomous loop stopped")
    
    def stop(self):
        """Para o loop."""
        self.running = False
        self.log("🛑 Stop requested")


def main():
    """CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eve Autonomous Loop v156 (with Self-Monitoring)")
    parser.add_argument("--goal", "-g", help="Add a goal")
    parser.add_argument("--task", "-t", help="Add a task")
    parser.add_argument("--status", "-s", action="store_true", help="Show status")
    parser.add_argument("--continuous", "-c", action="store_true", help="Run continuous")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    
    args = parser.parse_args()
    
    loop = AutonomousLoopV156()
    
    if args.stop:
        subprocess.run(["pkill", "-f", "eve_autonomous_loop_v156"])
        subprocess.run(["pkill", "-f", "eve_autonomous_loop_v155"])
        print("🛑 Stopped")
        return
    
    if args.status:
        status = loop.get_status()
        print(json.dumps(status, indent=2))
        return
    
    if args.goal or args.task:
        desc = args.goal or args.task
        task_id = loop.add_task(desc)
        print(f"✅ Added: {task_id}")
        return
    
    if args.continuous or args.daemon:
        loop.run_continuous()
    else:
        # Uma iteração
        loop.run_iteration()


if __name__ == "__main__":
    main()
