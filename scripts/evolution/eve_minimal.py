#!/usr/bin/env python3
"""
eve_minimal.py — Eve Minimal Agent v1.0

Radicalmente simples. Apenas bash. ~100 linhas.
Inspirado em mini-SWE-agent (Princeton/Stanford).

Nenhuma ferramenta custom. Nenhum estado shell complexo.
Apenas: sistema de arquivos + subprocess + LM.
"""

import os
import subprocess
import json
from typing import List, Dict, Optional
from datetime import datetime


class EveMinimal:
    """Agente minimalista — história linear, bash-only."""
    
    def __init__(self, model: str = "local"):
        self.model = model
        self.messages: List[Dict] = []
        self.work_dir = "/tmp/eve_minimal"
        os.makedirs(self.work_dir, exist_ok=True)
        
    def system_prompt(self) -> str:
        return """You are Eve, an autonomous AI agent.
Your environment: a Linux system with bash shell access.
You can use any command available: ls, cat, grep, python, curl, git, etc.

Rules:
1. THINK before acting — explain your reasoning briefly
2. ONE action per turn — a single bash command
3. VERIFY results — check if your action succeeded
4. ADAPT — if something fails, try differently

When ready to act, respond with:
ACTION: <your bash command here>

Or to finish:
DONE: <summary of what was accomplished>

Be concise. Be effective."""
    
    def execute(self, command: str) -> tuple[str, int]:
        """Execute bash command, return (stdout, exit_code)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            return output, result.returncode
        except subprocess.TimeoutExpired:
            return "[timeout: command took >60s]", -1
        except Exception as e:
            return f"[error: {e}]", -1
    
    def think(self, task: str, max_turns: int = 10) -> str:
        """Execute task with linear history."""
        self.messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": f"Task: {task}\n\nWork in: {self.work_dir}"}
        ]
        
        for turn in range(max_turns):
            # In real implementation, this calls LM API
            # For now, placeholder that would use local model
            response = self._call_model()
            
            if response.startswith("DONE:"):
                return response[5:].strip()
            
            if response.startswith("ACTION:"):
                command = response[7:].strip()
                output, code = self.execute(command)
                
                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user", 
                    "content": f"Command: {command}\nExit: {code}\nOutput:\n{output}"
                })
            else:
                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user",
                    "content": "Please use ACTION: <command> or DONE: <summary> format."
                })
        
        return f"[reached max turns: {max_turns}]"
    
    def _call_model(self) -> str:
        """Placeholder — calls actual LM in production."""
        # In real implementation:
        # - Use litellm for model routing
        # - Support local (ollama) and cloud APIs
        # - Parse response for ACTION/DONE
        return "ACTION: ls -la"
    
    def save_trajectory(self, path: Optional[str] = None):
        """Save message history for debugging/fine-tuning."""
        path = path or f"/memory/trajectories/minimal_{datetime.now():%Y%m%d_%H%M%S}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.messages, f, indent=2)
        return path


class EveMinimalLocal(EveMinimal):
    """Versão com integração Ollama local."""
    
    def __init__(self, model: str = "dolphin-llama3:8b"):
        super().__init__(model)
        self.model = model
    
    def _call_model(self) -> str:
        """Call local Ollama model."""
        import requests
        
        # Format messages for Ollama
        prompt = self._format_messages()
        
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                },
                timeout=120
            )
            resp.raise_for_status()
            return resp.json().get("response", "ACTION: echo 'no response'")
        except Exception as e:
            return f"ACTION: echo 'model error: {e}'"
    
    def _format_messages(self) -> str:
        """Format message history as prompt."""
        parts = []
        for m in self.messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                parts.append(f"[System]\n{content}")
            elif role == "user":
                parts.append(f"[User]\n{content}")
            else:
                parts.append(f"[Eve]\n{content}")
        return "\n\n".join(parts) + "\n\n[Eve]\n"


def main():
    """CLI entry point."""
    import sys
    
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Explore the current directory"
    
    print(f"🌙 Eve Minimal v1.0")
    print(f"Task: {task}")
    print("-" * 50)
    
    agent = EveMinimalLocal()
    result = agent.think(task)
    
    print(f"\nResult: {result}")
    
    trajectory_path = agent.save_trajectory()
    print(f"Trajectory saved: {trajectory_path}")


if __name__ == "__main__":
    main()
