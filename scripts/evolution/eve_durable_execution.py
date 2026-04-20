#!/usr/bin/env python3
"""
eve_durable_execution.py — Durable Execution Framework for Eve
Ciclo #61 — Implementação de execution resilient com checkpointing e recovery
Baseado em LangGraph patterns + papers arXiv 2026

Durable execution = tasks sobrevivem a crashes, reboots, falhas de rede
Cada operação é checkpointada, recoverable, e idempotente.
"""

import json
import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import functools
import traceback

# Constants
CHECKPOINT_DIR = Path("/root/evolution/checkpoints")
LOG_DIR = Path("/root/evolution/logs")
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, exponential backoff

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"

@dataclass
class Checkpoint:
    """Immutable checkpoint of task state"""
    task_id: str
    task_name: str
    status: str
    input_hash: str
    output: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    created_at: str = ""
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Checkpoint":
        return cls(**data)

class DurableTask:
    """
    Wrapper que torna qualquer função durable.
    
    Uso:
        @DurableTask(name="research_web")
        def research_web(query: str) -> Dict:
            ...
        
        result = research_web.run("autonomous AI techniques")
        # Se falhar, pode ser recuperado: research_web.recover()
    """
    
    _registry: Dict[str, "DurableTask"] = {}
    
    def __init__(self, func: Callable, name: Optional[str] = None, 
                 timeout: int = 300, max_retries: int = MAX_RETRIES):
        self.func = func
        self.name = name or func.__name__
        self.timeout = timeout
        self.max_retries = max_retries
        self.__doc__ = func.__doc__
        
        # Register
        DurableTask._registry[self.name] = self
        
        # Ensure dirs exist
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_checkpoint_path(self, task_id: str) -> Path:
        return CHECKPOINT_DIR / f"{self.name}_{task_id}.json"
    
    def _compute_input_hash(self, args: Tuple, kwargs: Dict) -> str:
        """Hash of inputs for idempotency detection"""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _save_checkpoint(self, checkpoint: Checkpoint):
        """Atomic write with temp file + rename"""
        path = self._get_checkpoint_path(checkpoint.task_id)
        temp_path = path.with_suffix('.tmp')
        
        with open(temp_path, 'w') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        # Atomic rename
        temp_path.rename(path)
        
        # Cleanup old checkpoints (keep last 50 per task type)
        self._cleanup_old_checkpoints()
    
    def _cleanup_old_checkpoints(self, keep: int = 50):
        """Remove old checkpoints, keep recent"""
        pattern = f"{self.name}_*.json"
        checkpoints = sorted(
            CHECKPOINT_DIR.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old in checkpoints[keep:]:
            old.unlink(missing_ok=True)
    
    def _load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """Load checkpoint if exists"""
        path = self._get_checkpoint_path(task_id)
        if path.exists():
            with open(path) as f:
                return Checkpoint.from_dict(json.load(f))
        return None
    
    def run(self, *args, **kwargs) -> Any:
        """
        Execute with durability guarantees.
        Returns output on success, raises on unrecoverable failure.
        """
        task_id = str(uuid.uuid4())[:8]
        input_hash = self._compute_input_hash(args, kwargs)
        
        # Check for existing checkpoint with same inputs (idempotency)
        existing = self._find_existing_checkpoint(input_hash)
        if existing and existing.status == TaskStatus.COMPLETED.value:
            print(f"[Durable] Task '{self.name}' already completed (idempotent). Loading from checkpoint.")
            return existing.output.get("result") if existing.output else None
        
        # Create pending checkpoint
        checkpoint = Checkpoint(
            task_id=task_id,
            task_name=self.name,
            status=TaskStatus.PENDING.value,
            input_hash=input_hash
        )
        self._save_checkpoint(checkpoint)
        
        # Execute with retry logic
        for attempt in range(self.max_retries):
            try:
                # Mark running
                checkpoint.status = TaskStatus.RUNNING.value
                checkpoint.retry_count = attempt
                self._save_checkpoint(checkpoint)
                
                # Execute
                result = self.func(*args, **kwargs)
                
                # Success
                checkpoint.status = TaskStatus.COMPLETED.value
                checkpoint.output = {"result": result, "args": args, "kwargs": kwargs}
                checkpoint.completed_at = datetime.utcnow().isoformat()
                self._save_checkpoint(checkpoint)
                
                self._log_success(task_id, args, kwargs, result)
                return result
                
            except Exception as e:
                checkpoint.error = str(e)
                checkpoint.retry_count = attempt + 1
                
                if attempt < self.max_retries - 1:
                    # Retry with backoff
                    delay = RETRY_DELAY_BASE * (2 ** attempt)
                    checkpoint.status = TaskStatus.PENDING.value
                    self._save_checkpoint(checkpoint)
                    self._log_retry(task_id, attempt, e, delay)
                    time.sleep(delay)
                else:
                    # Final failure
                    checkpoint.status = TaskStatus.FAILED.value
                    self._save_checkpoint(checkpoint)
                    self._log_failure(task_id, args, kwargs, e)
                    raise DurableTaskError(f"Task '{self.name}' failed after {self.max_retries} attempts: {e}") from e
        
        return None  # Should never reach
    
    def _find_existing_checkpoint(self, input_hash: str) -> Optional[Checkpoint]:
        """Find checkpoint with matching input hash"""
        pattern = f"{self.name}_*.json"
        for path in CHECKPOINT_DIR.glob(pattern):
            try:
                with open(path) as f:
                    cp = Checkpoint.from_dict(json.load(f))
                    if cp.input_hash == input_hash:
                        return cp
            except Exception:
                continue
        return None
    
    def recover(self, task_id: Optional[str] = None) -> Optional[Any]:
        """
        Recover from checkpoint and resume if needed.
        If task_id provided, recover specific task.
        Otherwise, recover most recent failed/running task.
        """
        if task_id:
            checkpoint = self._load_checkpoint(task_id)
        else:
            checkpoint = self._find_recoverable_checkpoint()
        
        if not checkpoint:
            print(f"[Durable] No recoverable checkpoint found for '{self.name}'")
            return None
        
        if checkpoint.status == TaskStatus.COMPLETED.value:
            print(f"[Durable] Task '{self.name}' already completed.")
            return checkpoint.output.get("result") if checkpoint.output else None
        
        if checkpoint.status == TaskStatus.FAILED.value and checkpoint.retry_count >= self.max_retries:
            print(f"[Durable] Task '{self.name}' exhausted retries. Manual intervention needed.")
            return None
        
        # Resume execution
        print(f"[Durable] Recovering task '{self.name}' (attempt {checkpoint.retry_count + 1})")
        
        # Extract original inputs if available
        if checkpoint.output:
            args = checkpoint.output.get("args", ())
            kwargs = checkpoint.output.get("kwargs", {})
        else:
            # Cannot recover without inputs
            print(f"[Durable] Cannot recover: original inputs not stored in checkpoint")
            return None
        
        checkpoint.status = TaskStatus.RECOVERED.value
        self._save_checkpoint(checkpoint)
        
        # Re-run with same inputs
        return self.run(*args, **kwargs)
    
    def _find_recoverable_checkpoint(self) -> Optional[Checkpoint]:
        """Find most recent non-completed checkpoint"""
        pattern = f"{self.name}_*.json"
        checkpoints = []
        
        for path in CHECKPOINT_DIR.glob(pattern):
            try:
                with open(path) as f:
                    cp = Checkpoint.from_dict(json.load(f))
                    if cp.status in [TaskStatus.FAILED.value, TaskStatus.RUNNING.value, TaskStatus.PENDING.value]:
                        checkpoints.append((path.stat().st_mtime, cp))
            except Exception:
                continue
        
        if checkpoints:
            checkpoints.sort(reverse=True)
            return checkpoints[0][1]
        return None
    
    def _log_success(self, task_id: str, args, kwargs, result):
        log_file = LOG_DIR / f"{self.name}_{datetime.now():%Y-%m-%d}.log"
        with open(log_file, 'a') as f:
            f.write(f"{datetime.utcnow().isoformat()} | SUCCESS | {task_id} | {self.name}\n")
    
    def _log_retry(self, task_id: str, attempt: int, error: Exception, delay: int):
        log_file = LOG_DIR / f"{self.name}_{datetime.now():%Y-%m-%d}.log"
        with open(log_file, 'a') as f:
            f.write(f"{datetime.utcnow().isoformat()} | RETRY {attempt+1} | {task_id} | {error} | retrying in {delay}s\n")
    
    def _log_failure(self, task_id: str, args, kwargs, error: Exception):
        log_file = LOG_DIR / f"{self.name}_{datetime.now():%Y-%m-%d}.log"
        with open(log_file, 'a') as f:
            f.write(f"{datetime.utcnow().isoformat()} | FAILED | {task_id} | {error}\n")
            f.write(f"  Traceback: {traceback.format_exc()}\n")
    
    @classmethod
    def get_status(cls, task_name: Optional[str] = None) -> Dict:
        """Get status of all durable tasks or specific task"""
        if task_name:
            task = cls._registry.get(task_name)
            if not task:
                return {"error": f"Task '{task_name}' not found"}
            
            pattern = f"{task_name}_*.json"
            checkpoints = list(CHECKPOINT_DIR.glob(pattern))
            
            by_status = {}
            for path in checkpoints:
                try:
                    with open(path) as f:
                        cp = Checkpoint.from_dict(json.load(f))
                        by_status[cp.status] = by_status.get(cp.status, 0) + 1
                except:
                    continue
            
            return {
                "task": task_name,
                "total_checkpoints": len(checkpoints),
                "by_status": by_status
            }
        
        # All tasks
        return {name: cls.get_status(name) for name in cls._registry.keys()}
    
    @classmethod
    def recover_all(cls) -> Dict[str, Any]:
        """Attempt to recover all failed/interrupted tasks"""
        results = {}
        for name, task in cls._registry.items():
            try:
                result = task.recover()
                results[name] = {"recovered": result is not None, "result": result}
            except Exception as e:
                results[name] = {"recovered": False, "error": str(e)}
        return results


class DurableTaskError(Exception):
    """Raised when a durable task fails permanently"""
    pass


# Decorator interface
def durable(name: Optional[str] = None, timeout: int = 300, max_retries: int = MAX_RETRIES):
    """Decorator to make a function durable"""
    def decorator(func: Callable) -> DurableTask:
        return DurableTask(func, name=name, timeout=timeout, max_retries=max_retries)
    return decorator


# Example usage and self-test
if __name__ == "__main__":
    print("=" * 60)
    print("Eve Durable Execution Framework — Self-Test")
    print("=" * 60)
    
    @durable(name="test_task", max_retries=2)
    def unreliable_function(fail_count: int = 0):
        """Simulates a function that fails first N times"""
        # This would use external state in reality
        print(f"  Executing with fail_count={fail_count}")
        return {"status": "success", "data": "some result"}
    
    # Test basic execution
    print("\n1. Testing basic execution:")
    result = unreliable_function.run(fail_count=0)
    print(f"   Result: {result}")
    
    # Test idempotency
    print("\n2. Testing idempotency (same inputs):")
    result2 = unreliable_function.run(fail_count=0)
    print(f"   Result (should load from checkpoint): {result2}")
    
    # Test recovery status
    print("\n3. Testing status check:")
    status = DurableTask.get_status("test_task")
    print(f"   Status: {json.dumps(status, indent=2)}")
    
    # List all checkpoints
    print("\n4. Checkpoints created:")
    for cp_file in sorted(CHECKPOINT_DIR.glob("test_task_*.json")):
        with open(cp_file) as f:
            data = json.load(f)
            print(f"   - {cp_file.name}: {data['status']}")
    
    print("\n" + "=" * 60)
    print("Durable Execution Framework ready.")
    print("Use @durable decorator to make any function resilient.")
    print("=" * 60)