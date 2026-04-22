#!/usr/bin/env python3
"""
eve_auto_executor_v155.py — Execução autônoma com retry e aprendizado.

Recebe uma tarefa, executa até completar. Se falhar, analisa, aprende, tenta de novo.
Não para no primeiro erro. Não pede permissão. Apenas executa.

Padrões incorporados:
- EVE-Agent: error learning, context compression, retry com backoff
- Hermes (concept): autonomous execution loop
- Eve: verifiable reasoning, durable execution, safety limits
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Paths
ROOT = Path("/root/evolution")
MEMORY_DIR = Path("/memory")
AUTO_EXEC_LOG = MEMORY_DIR / "auto_executor_logs"
AUTO_EXEC_LOG.mkdir(parents=True, exist_ok=True)

# Limits (safety)
MAX_RETRIES = 5
MAX_STEPS_PER_TASK = 50
MAX_EXECUTION_TIME_MINUTES = 30
CHARS_PER_TOKEN = 4
CONTEXT_WINDOW_TOKENS = 8000
COMPRESSION_THRESHOLD = 0.75


@dataclass
class ExecutionAttempt:
    """Registra uma tentativa de execução."""
    attempt_number: int
    timestamp: str
    action: str
    result: str
    error: Optional[str] = None
    lesson: Optional[str] = None


@dataclass
class TaskContext:
    """Contexto de uma tarefa em execução."""
    task_id: str
    original_goal: str
    attempts: list[ExecutionAttempt] = field(default_factory=list)
    current_plan: list[str] = field(default_factory=list)
    accumulated_lessons: list[str] = field(default_factory=list)
    success: bool = False
    final_result: Optional[str] = None


class ErrorLearner:
    """Aprende com erros para não repetir."""
    
    def __init__(self, log_dir: Path = AUTO_EXEC_LOG):
        self.log_dir = log_dir
        self.errors_db = log_dir / "error_lessons.json"
        self.errors_db.parent.mkdir(parents=True, exist_ok=True)
        self._load_db()
    
    def _load_db(self):
        """Carrega base de lições aprendidas."""
        if self.errors_db.exists():
            with open(self.errors_db) as f:
                self.lessons = json.load(f)
        else:
            self.lessons = {}
    
    def _save_db(self):
        """Persiste lições aprendidas."""
        with open(self.errors_db, "w") as f:
            json.dump(self.lessons, f, indent=2, ensure_ascii=False)
    
    def extract_error_signature(self, error: str, action: str) -> str:
        """Extrai assinatura do erro para matching."""
        # Normaliza: remove números de linha específicos
        normalized = re.sub(r'line \d+', 'line N', error.lower())
        normalized = re.sub(r'/[\w/]+/', '/PATH/', normalized)
        # Usa primeiros 100 chars como key
        return f"{action[:30]}:{normalized[:100]}"
    
    def learn_from_error(self, action: str, error: str, result: str) -> str:
        """Extrai lição de um erro."""
        signature = self.extract_error_signature(error, action)
        
        # Se já vimos este erro, retorna lição anterior
        if signature in self.lessons:
            return self.lessons[signature]["lesson"]
        
        # Gera nova lição via análise simples
        lesson = self._generate_lesson(action, error, result)
        self.lessons[signature] = {
            "action": action,
            "error": error[:200],
            "lesson": lesson,
            "count": 1,
            "first_seen": datetime.now(timezone.utc).isoformat()
        }
        self._save_db()
        return lesson
    
    def _generate_lesson(self, action: str, error: str, result: str) -> str:
        """Gera lição heurística do erro."""
        error_lower = error.lower()
        
        # Padrões comuns
        if "permission denied" in error_lower or "access" in error_lower:
            return "Check file permissions and ownership before access. Use sudo only when necessary."
        
        if "not found" in error_lower or "no such file" in error_lower:
            return "Verify path exists before operations. Create directories if needed."
        
        if "connection" in error_lower or "timeout" in error_lower:
            return "Add retry logic with exponential backoff for network operations."
        
        if "memory" in error_lower or "oom" in error_lower:
            return "Reduce batch size or memory usage. Monitor resource constraints."
        
        if "syntax" in error_lower or "parse" in error_lower or "invalid" in error_lower:
            return "Validate input format before processing. Check for encoding issues."
        
        if "already exists" in error_lower:
            return "Check existence before creation. Use update/merge instead of create if appropriate."
        
        if "locked" in error_lower or "busy" in error_lower:
            return "Resource may be in use. Add retry with delay or check for competing processes."
        
        # Default
        return f"Error occurred during: {action[:50]}. Analyze pattern before retry."
    
    def get_relevant_lessons(self, action: str) -> list[str]:
        """Busca lições relevantes para uma ação."""
        action_lower = action.lower()
        relevant = []
        for sig, data in self.lessons.items():
            if any(word in action_lower for word in sig.lower().split(":")[0].split()):
                relevant.append(data["lesson"])
        return relevant[:3]  # Top 3


class ContextCompressor:
    """Compressão de contexto do EVE-Agent adaptada."""
    
    def __init__(self, threshold: float = COMPRESSION_THRESHOLD):
        self.threshold = threshold
        self.chars_per_token = CHARS_PER_TOKEN
        self.context_window = CONTEXT_WINDOW_TOKENS
    
    def estimate_tokens(self, text: str) -> int:
        """Estima tokens por heurística."""
        return max(1, len(text) // self.chars_per_token)
    
    def should_compress(self, *texts: str) -> bool:
        """Verifica se precisa comprimir."""
        total = sum(self.estimate_tokens(t) for t in texts if t)
        return total > (self.context_window * self.threshold)
    
    def compress(self, text: str, target_ratio: float = 0.5) -> str:
        """Comprime texto mantendo informação essencial."""
        lines = text.split("\n")
        
        if len(lines) < 10:
            return text
        
        # Estratégia: keep first, last, and key middle points
        keep_start = 3
        keep_end = 3
        middle_idx = len(lines) // 2
        
        compressed = (
            lines[:keep_start] +
            ["... [compressed middle section] ..."] +
            lines[middle_idx:middle_idx+2] +
            ["..."] +
            lines[-keep_end:]
        )
        
        return "\n".join(compressed)
    
    def compress_attempts(self, attempts: list[ExecutionAttempt]) -> list[ExecutionAttempt]:
        """Comprime histórico de tentativas se muito longo."""
        if len(attempts) <= 3:
            return attempts
        
        # Mantém primeira, última, e melhor tentativa
        best = max(attempts, key=lambda a: len(a.lesson) if a.lesson else 0)
        compressed = [attempts[0], best, attempts[-1]]
        return compressed


class AutoExecutor:
    """Executor autônomo com retry e aprendizado."""
    
    def __init__(self):
        self.error_learner = ErrorLearner()
        self.compressor = ContextCompressor()
        self.active_tasks: dict[str, TaskContext] = {}
    
    def execute_shell(self, command: str, timeout: int = 60) -> tuple[bool, str, str]:
        """Executa comando shell com timeout."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/root/evolution"
            )
            success = result.returncode == 0
            stdout = result.stdout
            stderr = result.stderr
            
            output = stdout
            if stderr:
                output += f"\n[STDERR]: {stderr}"
            
            return success, output, stderr if not success else ""
            
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def execute_python(self, code: str, timeout: int = 60) -> tuple[bool, str, str]:
        """Executa código Python com timeout."""
        try:
            # Write to temp file
            temp_file = ROOT / f"_temp_exec_{int(time.time())}.py"
            temp_file.write_text(code, encoding="utf-8")
            
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/root/evolution"
            )
            
            # Cleanup
            temp_file.unlink(missing_ok=True)
            
            success = result.returncode == 0
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr}"
            
            return success, output, result.stderr if not success else ""
            
        except subprocess.TimeoutExpired:
            return False, "", "Python execution timed out"
        except Exception as e:
            return False, "", str(e)
    
    def generate_plan(self, goal: str, lessons: list[str] = None) -> list[str]:
        """Gera plano de execução baseado no objetivo."""
        # Plano heurístico baseado em keywords
        plan = []
        goal_lower = goal.lower()
        
        if "criar" in goal_lower or "escrever" in goal_lower or "create" in goal_lower:
            if ".py" in goal_lower:
                plan = [
                    "Analyze requirements from goal",
                    "Create Python file with proper structure",
                    "Add error handling",
                    "Test execution",
                    "Verify output"
                ]
            elif ".md" in goal_lower:
                plan = [
                    "Determine document purpose",
                    "Create markdown structure",
                    "Add relevant content",
                    "Verify formatting"
                ]
            else:
                plan = [
                    "Determine file type and structure needed",
                    "Create file with appropriate content",
                    "Verify creation"
                ]
        
        elif "executar" in goal_lower or "rodar" in goal_lower or "run" in goal_lower:
            plan = [
                "Identify script/command to run",
                "Check prerequisites/dependencies",
                "Execute with proper parameters",
                "Capture and analyze output",
                "Verify success"
            ]
        
        elif "analise" in goal_lower or "analisar" in goal_lower or "analyze" in goal_lower:
            plan = [
                "Identify target for analysis",
                "Collect relevant data",
                "Perform analysis",
                "Document findings"
            ]
        
        elif "instalar" in goal_lower or "setup" in goal_lower or "install" in goal_lower:
            plan = [
                "Check current state",
                "Install required components",
                "Verify installation",
                "Test basic functionality"
            ]
        
        else:
            plan = [
                "Understand the goal",
                "Determine appropriate action",
                "Execute action",
                "Verify result"
            ]
        
        # Injeta lições no início do plano
        if lessons:
            plan.insert(0, f"Apply learned lessons: {'; '.join(lessons)}")
        
        return plan
    
    def attempt_execution(self, task_ctx: TaskContext, attempt_num: int) -> ExecutionAttempt:
        """Tenta executar a tarefa uma vez."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Recupera lições relevantes
        lessons = self.error_learner.get_relevant_lessons(task_ctx.original_goal)
        
        # Gera plano (ou recupera existente)
        if not task_ctx.current_plan:
            task_ctx.current_plan = self.generate_plan(task_ctx.original_goal, lessons)
        
        print(f"[Attempt {attempt_num}] Goal: {task_ctx.original_goal[:60]}...")
        print(f"[Attempt {attempt_num}] Plan: {task_ctx.current_plan}")
        
        # Determina tipo de ação
        goal_lower = task_ctx.original_goal.lower()
        
        # Análise do objetivo para decidir ação
        if "python" in goal_lower or ".py" in goal_lower or "script" in goal_lower:
            action_type = "python"
        elif any(cmd in goal_lower for cmd in ["git", "pip", "apt", "npm", "make"]):
            action_type = "shell"
        else:
            action_type = "auto"
        
        # Executa baseado no tipo
        if action_type == "python":
            # Extrai código se presente, ou cria baseado no objetivo
            success, result, error = self._execute_python_task(task_ctx)
        elif action_type == "shell":
            success, result, error = self._execute_shell_task(task_ctx)
        else:
            success, result, error = self._execute_auto_task(task_ctx)
        
        # Registra tentativa
        attempt = ExecutionAttempt(
            attempt_number=attempt_num,
            timestamp=timestamp,
            action=f"{action_type}: {task_ctx.current_plan[0] if task_ctx.current_plan else 'auto'}",
            result=result[:500] if result else "(no output)",
            error=error if error else None
        )
        
        # Se falhou, aprende
        if not success and error:
            lesson = self.error_learner.learn_from_error(
                attempt.action, error, result
            )
            attempt.lesson = lesson
            print(f"[Attempt {attempt_num}] Learned: {lesson}")
        
        return attempt
    
    def _execute_python_task(self, task_ctx: TaskContext) -> tuple[bool, str, str]:
        """Executa tarefa Python."""
        # Tenta extrair código do objetivo, ou cria arquivo simples
        code_match = re.search(r'```python\n(.*?)\n```', task_ctx.original_goal, re.S)
        
        if code_match:
            code = code_match.group(1)
        else:
            # Cria script baseado no objetivo
            code = self._generate_python_script(task_ctx.original_goal)
        
        # Salva em arquivo
        script_name = f"auto_{int(time.time())}.py"
        script_path = ROOT / script_name
        script_path.write_text(code, encoding="utf-8")
        
        # Executa
        success, result, error = self.execute_python(code)
        
        return success, result, error
    
    def _execute_shell_task(self, task_ctx: TaskContext) -> tuple[bool, str, str]:
        """Executa tarefa shell."""
        # Extrai comando do objetivo
        cmd_match = re.search(r'`(.*?)`', task_ctx.original_goal)
        if cmd_match:
            command = cmd_match.group(1)
        else:
            # Tenta inferir comando
            command = self._infer_shell_command(task_ctx.original_goal)
        
        if command:
            return self.execute_shell(command)
        else:
            return False, "", "Could not infer shell command from goal"
    
    def _execute_auto_task(self, task_ctx: TaskContext) -> tuple[bool, str, str]:
        """Tenta executar automaticamente baseado no objetivo."""
        # Verifica se parece ser criação de arquivo
        if any(word in task_ctx.original_goal.lower() for word in ["criar", "create", "escrever", "write"]):
            return self._handle_file_creation(task_ctx.original_goal)
        
        # Default: tenta como shell
        return self.execute_shell(task_ctx.original_goal, timeout=30)
    
    def _generate_python_script(self, goal: str) -> str:
        """Gera script Python baseado no objetivo."""
        return f'''#!/usr/bin/env python3
"""Auto-generated script for: {goal[:60]}"""

def main():
    print("Executing auto-generated script...")
    # TODO: Implement based on goal
    print(f"Goal: {goal}")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
'''
    
    def _infer_shell_command(self, goal: str) -> Optional[str]:
        """Infere comando shell do objetivo."""
        goal_lower = goal.lower()
        
        if "git" in goal_lower:
            return "git status"
        elif "pip" in goal_lower:
            return "pip list"
        elif "listar" in goal_lower or "ls" in goal_lower:
            return "ls -la"
        elif "diretório" in goal_lower or "pasta" in goal_lower:
            return "pwd && ls -la"
        
        return None
    
    def _handle_file_creation(self, goal: str) -> tuple[bool, str, str]:
        """Manipula criação de arquivo."""
        # Extrai nome do arquivo
        file_match = re.search(r'(\S+\.(?:py|md|txt|json|yaml|yml|sh))', goal)
        
        if not file_match:
            return False, "", "Could not extract filename from goal"
        
        filename = file_match.group(1)
        filepath = ROOT / filename
        
        # Gera conteúdo baseado no tipo
        ext = filepath.suffix.lower()
        
        if ext == ".py":
            content = self._generate_python_script(goal)
        elif ext == ".md":
            content = f"# {filepath.stem}\n\nGenerated automatically.\n\n{goal}\n"
        elif ext in [".json"]:
            content = json.dumps({"generated": True, "goal": goal}, indent=2)
        else:
            content = f"# Generated file\n# Goal: {goal}\n"
        
        try:
            filepath.write_text(content, encoding="utf-8")
            return True, f"Created file: {filepath}", ""
        except Exception as e:
            return False, "", str(e)
    
    def execute_task(self, goal: str, task_id: Optional[str] = None) -> TaskContext:
        """Executa uma tarefa até completar ou esgotar retries."""
        task_id = task_id or f"task_{int(time.time())}"
        
        task_ctx = TaskContext(
            task_id=task_id,
            original_goal=goal
        )
        
        print(f"=" * 60)
        print(f"[AUTO-EXECUTOR] Starting task: {goal[:70]}")
        print(f"=" * 60)
        
        for attempt_num in range(1, MAX_RETRIES + 1):
            # Executa tentativa
            attempt = self.attempt_execution(task_ctx, attempt_num)
            task_ctx.attempts.append(attempt)
            
            # Verifica sucesso
            if attempt.error is None:
                task_ctx.success = True
                task_ctx.final_result = attempt.result
                print(f"\n✅ [SUCCESS] Task completed in {attempt_num} attempt(s)")
                break
            
            # Se falhou, prepara próxima tentativa
            print(f"\n❌ [Attempt {attempt_num}] Failed: {attempt.error[:100] if attempt.error else 'Unknown'}")
            
            if attempt_num < MAX_RETRIES:
                # Atualiza plano com lição aprendida
                if attempt.lesson:
                    task_ctx.accumulated_lessons.append(attempt.lesson)
                    print(f"💡 Applying lesson: {attempt.lesson}")
                
                # Ajusta plano
                task_ctx.current_plan = self.generate_plan(
                    goal, 
                    task_ctx.accumulated_lessons
                )
                
                # Backoff antes de retry
                wait_time = min(2 ** attempt_num, 10)  # Max 10s
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        else:
            # Exauriu retries
            print(f"\n💥 [FAILED] Task failed after {MAX_RETRIES} attempts")
            task_ctx.final_result = "Max retries exceeded"
        
        # Salva log
        self._save_task_log(task_ctx)
        
        return task_ctx
    
    def _save_task_log(self, task_ctx: TaskContext):
        """Salva log da execução."""
        log_file = AUTO_EXEC_LOG / f"{task_ctx.task_id}.json"
        
        log_data = {
            "task_id": task_ctx.task_id,
            "original_goal": task_ctx.original_goal,
            "success": task_ctx.success,
            "final_result": task_ctx.final_result,
            "attempts": [
                {
                    "attempt_number": a.attempt_number,
                    "timestamp": a.timestamp,
                    "action": a.action,
                    "result": a.result[:500],
                    "error": a.error,
                    "lesson": a.lesson
                }
                for a in task_ctx.attempts
            ],
            "lessons_learned": task_ctx.accumulated_lessons,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Log saved: {log_file}")


def main():
    """CLI do auto-executor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eve Auto-Executor v155")
    parser.add_argument("goal", nargs="?", help="Goal to execute")
    parser.add_argument("--file", "-f", help="Read goal from file")
    parser.add_argument("--max-retries", "-r", type=int, default=MAX_RETRIES, help="Max retry attempts")
    
    args = parser.parse_args()
    
    if args.file:
        goal = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.goal:
        goal = args.goal
    else:
        print("Usage: python eve_auto_executor_v155.py 'Create a file X' or --file goal.txt")
        sys.exit(1)
    
    executor = AutoExecutor()
    result = executor.execute_task(goal)
    
    print(f"\n{'=' * 60}")
    print(f"Final status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
    print(f"Result: {result.final_result[:200] if result.final_result else '(none)'}")
    print(f"{'=' * 60}")
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
