#!/usr/bin/env python3
"""
eve_aci.py — Agent-Computer Interface for Eve

Radically simple ACI inspired by mini-SWE-agent principles:
- Only tool: bash (universal, no API needed)
- Linear history: append-only
- Stateless execution: subprocess.run
- LM-first: trust model capability over tool complexity

~100 lines. No complexity. Just capability.
"""

import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class EveACI:
    """
    Minimalist interface between Eve and the environment.
    
    Design principle: Bash is the universal tool.
    A capable LM + bash = infinite capabilities.
    """
    
    def __init__(self, work_dir: str = "/", max_history: int = 50):
        self.work_dir = Path(work_dir).resolve()
        self.history: List[Dict[str, str]] = []
        self.max_history = max_history
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def read(self, path: str, offset: int = 1, limit: int = 100) -> str:
        """Read file with line numbers."""
        try:
            full_path = self.work_dir / path
            with open(full_path, 'r') as f:
                lines = f.readlines()
            
            start = max(0, offset - 1)
            end = min(len(lines), start + limit)
            
            result = []
            for i, line in enumerate(lines[start:end], start=start+1):
                result.append(f"{i:4d}| {line.rstrip()}")
            
            return "\n".join(result) if result else f"[Empty file or offset {offset} beyond bounds]"
        except Exception as e:
            return f"[Error reading {path}: {e}]"
    
    def edit(self, path: str, old: str, new: str) -> str:
        """Edit file with diff feedback."""
        try:
            full_path = self.work_dir / path
            with open(full_path, 'r') as f:
                content = f.read()
            
            if old not in content:
                return f"[Error: old text not found in {path}]"
            
            new_content = content.replace(old, new, 1)
            
            with open(full_path, 'w') as f:
                f.write(new_content)
            
            # Return context around change
            old_lines = old.split('\n')
            return f"[Edited {path}: replaced {len(old_lines)} lines]"
        except Exception as e:
            return f"[Error editing {path}: {e}]"
    
    def bash(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Execute command, return structured feedback.
        Stateless: each command runs in fresh subprocess.
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.work_dir,
                timeout=timeout
            )
            
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout[:5000] if result.stdout else "",
                "stderr": result.stderr[:2000] if result.stderr else "",
                "command": command[:100] + "..." if len(command) > 100 else command
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"[Timeout after {timeout}s]",
                "command": command
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"[Error: {e}]",
                "command": command
            }
    
    def search(self, query: str, path: str = ".", file_pattern: str = "*.py") -> str:
        """Search files using grep/ripgrep."""
        cmd = f"grep -r -n -i '{query}' {path} --include='{file_pattern}' 2>/dev/null | head -20"
        result = self.bash(cmd)
        if result["stdout"]:
            return result["stdout"]
        return f"[No matches for '{query}' in {path}]"
    
    def observe(self, observation: str) -> None:
        """Add observation to linear history."""
        self.history.append({"role": "user", "content": observation})
        self._trim_history()
    
    def act(self, action: str) -> Dict[str, Any]:
        """
        Execute action (bash command), return observation.
        Records both action and result in history.
        """
        self.history.append({"role": "assistant", "content": action})
        
        result = self.bash(action)
        
        observation = f"Exit: {result['exit_code']}\n"
        if result["stdout"]:
            observation += f"Output:\n{result['stdout']}\n"
        if result["stderr"]:
            observation += f"Error:\n{result['stderr']}\n"
        
        self.history.append({"role": "user", "content": observation})
        self._trim_history()
        
        return result
    
    def _trim_history(self) -> None:
        """Keep history bounded — oldest entries removed first."""
        if len(self.history) > self.max_history:
            # Keep system/context if present, trim from oldest interaction
            self.history = self.history[-self.max_history:]
    
    def get_history(self) -> List[Dict[str, str]]:
        """Return current history for LM consumption."""
        return self.history.copy()
    
    def save_trajectory(self, path: str = None) -> str:
        """Save full history for analysis/training."""
        if path is None:
            path = f"/root/evolution/trajectories/trajectory_{self.session_id}.json"
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                "session_id": self.session_id,
                "work_dir": str(self.work_dir),
                "history": self.history
            }, f, indent=2)
        
        return path


class EveMinimalAgent:
    """
    Minimal autonomous agent using EveACI.
    
    No complex orchestration. Just:
    1. Observe
    2. Think (via external LM)
    3. Act
    4. Loop
    """
    
    def __init__(self, lm_client, work_dir: str = "/"):
        self.aci = EveACI(work_dir)
        self.lm = lm_client
        self.step_count = 0
        self.max_steps = 50
    
    def run(self, task: str, max_steps: int = None) -> List[Dict]:
        """
        Execute task autonomously.
        
        Args:
            task: Description of what to accomplish
            max_steps: Override default step limit
        
        Returns:
            Full trajectory (history)
        """
        if max_steps:
            self.max_steps = max_steps
        
        # Initial observation
        self.aci.observe(f"Task: {task}\nWorking directory: {self.aci.work_dir}\nBegin.")
        
        for step in range(self.max_steps):
            self.step_count = step
            
            # Get action from LM
            history = self.aci.get_history()
            action = self.lm.complete(history)
            
            # Check for completion
            if self._is_done(action):
                self.aci.observe("Task completed.")
                break
            
            # Execute action
            result = self.aci.act(action)
            
            # Check for stuck state
            if step > 10 and self._is_stuck():
                self.aci.observe("[System: Agent appears stuck. Consider alternative approach.]")
        
        # Save trajectory for learning
        trajectory_path = self.aci.save_trajectory()
        
        return self.aci.get_history()
    
    def _is_done(self, action: str) -> bool:
        """Check if action signals completion."""
        done_signals = [
            "DONE", "COMPLETE", "FINISHED", "TERMINATE",
            "task complete", "completed successfully"
        ]
        return any(sig in action.upper() for sig in done_signals)
    
    def _is_stuck(self) -> bool:
        """Detect repetitive/stuck behavior from history."""
        if len(self.aci.history) < 6:
            return False
        
        # Check last 3 actions for repetition
        recent = self.aci.history[-6:]
        actions = [h["content"] for h in recent if h["role"] == "assistant"]
        
        if len(set(actions)) == 1 and len(actions) >= 2:
            return True
        
        return False


# Simple LM client interface
class SimpleLMClient:
    """
    Placeholder LM client.
    In production, this connects to GLM-5, Dolphin, or Eve Model v1.
    """
    
    def complete(self, history: List[Dict[str, str]]) -> str:
        """
        Generate next action based on history.
        
        For now, returns placeholder. Real implementation calls model API.
        """
        # This is where Eve Model v1 will plug in
        # For testing, return a simple bash command
        return "ls -la"


if __name__ == "__main__":
    # Test the ACI
    aci = EveACI("/root/evolution")
    
    # Test read
    print("=== Testing read ===")
    print(aci.read("eve_aci.py", limit=20))
    
    # Test bash
    print("\n=== Testing bash ===")
    result = aci.bash("echo 'Hello from Eve ACI' && pwd")
    print(f"Exit: {result['exit_code']}")
    print(f"Output: {result['stdout']}")
    
    # Test search
    print("\n=== Testing search ===")
    print(aci.search("class Eve", path="/root/evolution", file_pattern="*.py"))
    
    print("\n=== EveACI ready ===")
