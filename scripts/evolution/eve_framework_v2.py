#!/usr/bin/env python3
"""
EVE FRAMEWORK v2 — Inspirado por: Claude Code, OpenAI Agents SDK, SWE-agent, LangChain, AutoGPT

Arquitetura híbrida que combina o melhor de cada framework pesquisado.

Componentes:
- Orchestrator (inspirado no OpenAI Agents SDK Runner)
- Agent Registry (inspirado no LangChain/LlamaIndex)
- Memory System (ChromaDB + Mem0 + Context Window)
- Tool Registry com MCP (inspirado no Claude Code)
- Sub-agent spawning (inspirado no OpenClaw)
- Config-driven prompts (inspirado no SWE-agent YAML)
- Self-reflection loop (inspirado no Evaluator-Optimizer pattern)
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field

# ============================================================
# CORE DATA STRUCTURES
# ============================================================

@dataclass
class AgentConfig:
    """Configuração de um agente (inspirado no OpenAI Agents SDK)"""
    name: str
    instructions: str | Callable = ""
    tools: List[str] = field(default_factory=list)
    handoffs: List[str] = field(default_factory=list)
    model: str = "modal/zai-org/GLM-5-FP8"
    fallback_models: List[str] = field(default_factory=lambda: [
        "ollama/dolphin-llama3",
        "ollama/kimi-k2.5:cloud"
    ])
    max_iterations: int = 10
    energy_budget: int = 100
    description: str = ""

@dataclass
class MemoryEntry:
    """Entrada de memória com timestamp e relevância"""
    content: str
    timestamp: str
    source: str
    tags: List[str] = field(default_factory=list)
    relevance_score: float = 1.0
    entry_type: str = "observation"  # observation, decision, learning, insight

@dataclass
class TaskResult:
    """Resultado de uma tarefa executada"""
    task: str
    success: bool
    output: str
    duration_ms: int
    model_used: str
    tokens_used: int = 0
    error: Optional[str] = None

# ============================================================
# MEMORY SYSTEM
# ============================================================

class EveMemory:
    """
    Sistema de memória híbrido (inspirado em ChromaDB + Mem0 + LangChain Memory)
    
    Camadas:
    - Working Memory: contexto atual da conversa
    - Short-term: memórias recentes (últimas 24h)
    - Long-term: memórias persistentes (MEMORY.md + ChromaDB)
    - Episodic: sequências de ações e resultados
    """
    
    def __init__(self, base_path: str = "/root"):
        self.base_path = base_path
        self.memory_dir = os.path.join(base_path, "memory")
        self.working: List[Dict] = []
        self.short_term: List[MemoryEntry] = []
        self.episodic: List[Dict] = []
        self._ensure_dirs()
        
    def _ensure_dirs(self):
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)
        
    def add(self, content: str, source: str = "self", tags: List[str] = None,
            entry_type: str = "observation", relevance: float = 1.0):
        """Adiciona entrada à memória"""
        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now().isoformat(),
            source=source,
            tags=tags or [],
            relevance_score=relevance,
            entry_type=entry_type
        )
        self.short_term.append(entry)
        self.working.append({"role": "system", "content": f"[Memory] {content}"})
        return entry
        
    def add_episode(self, task: str, result: TaskResult):
        """Adiciona episódio (sequência de ação + resultado)"""
        episode = {
            "task": task,
            "success": result.success,
            "output": result.output[:500],
            "duration_ms": result.duration_ms,
            "model": result.model_used,
            "timestamp": datetime.now().isoformat()
        }
        self.episodic.append(episode)
        
    def get_relevant(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        """Recupera memórias relevantes (simulação - ChromaDB real seria via API)"""
        # Simple keyword matching for now
        results = []
        query_lower = query.lower()
        for entry in self.short_term:
            score = 0
            if query_lower in entry.content.lower():
                score += 0.5
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 0.3
            score *= entry.relevance_score
            if score > 0:
                entry.relevance_score = score
                results.append(entry)
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]
        
    def consolidate(self):
        """Consolida memórias short-term em arquivo (inspirado no autoDream)"""
        if not self.short_term:
            return
            
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(self.memory_dir, f"{today}.md")
        
        existing = ""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                existing = f.read()
                
        new_entries = []
        for entry in self.short_term:
            entry_line = f"- [{entry.entry_type}] {entry.content} (from: {entry.source})"
            if entry_line not in existing:
                new_entries.append(entry_line)
                
        if new_entries:
            with open(filepath, 'a') as f:
                f.write(f"\n## Memory Consolidation - {datetime.now().isoformat()}\n")
                for line in new_entries:
                    f.write(line + "\n")
                    
        # Clear short-term after consolidation
        self.short_term.clear()

# ============================================================
# TOOL REGISTRY (com MCP support)
# ============================================================

class ToolRegistry:
    """
    Registro de ferramentas com suporte a MCP
    (inspirado no Claude Code tools + OpenAI function calling)
    """
    
    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self.mcp_servers: List[Dict] = []
        
    def register(self, name: str, description: str, parameters: Dict = None,
                 handler: Callable = None):
        """Registra uma ferramenta"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}},
            "handler": handler
        }
        
    def get_tool(self, name: str) -> Optional[Dict]:
        return self.tools.get(name)
        
    def list_tools(self) -> List[str]:
        return list(self.tools.keys())
        
    def execute(self, name: str, **kwargs) -> Any:
        tool = self.get_tool(name)
        if tool and tool["handler"]:
            return tool["handler"](**kwargs)
        return None

# ============================================================
# AGENT RUNNER (inspirado no OpenAI Agents SDK Runner)
# ============================================================

class AgentRunner:
    """
    Executa agentes com loop ReAct
    (inspirado no OpenAI Agents SDK + SWE-agent + LangChain)
    
    Loop principal:
    1. Invoca modelo com input + contexto
    2. Se output final, termina
    3. Se handoff, troca para novo agente
    4. Executa tool calls e re-executa
    """
    
    def __init__(self, memory: EveMemory, tools: ToolRegistry):
        self.memory = memory
        self.tools = tools
        self.agents: Dict[str, AgentConfig] = {}
        self.hooks: Dict[str, List[Callable]] = {
            "on_agent_start": [],
            "on_llm_start": [],
            "on_llm_end": [],
            "on_tool_start": [],
            "on_tool_end": [],
            "on_handoff": [],
            "on_agent_end": []
        }
        
    def register_agent(self, config: AgentConfig):
        self.agents[config.name] = config
        
    def add_hook(self, event: str, handler: Callable):
        if event in self.hooks:
            self.hooks[event].append(handler)
            
    async def _run_hooks(self, event: str, **kwargs):
        for handler in self.hooks.get(event, []):
            try:
                await handler(**kwargs) if asyncio.iscoroutinefunction(handler) else handler(**kwargs)
            except Exception as e:
                print(f"Hook error: {e}")
                
    async def run(self, agent_name: str, input_text: str, 
                  context: Dict = None) -> TaskResult:
        """
        Executa agente com input (loop principal)
        """
        start_time = time.time()
        agent = self.agents.get(agent_name)
        
        if not agent:
            return TaskResult(
                task=input_text, success=False, output="Agent not found",
                duration_ms=int((time.time() - start_time) * 1000),
                model_used="none", error="AgentNotRegistered"
            )
            
        await self._run_hooks("on_agent_start", agent=agent, input=input_text)
        
        # Build context with memory
        relevant_memories = self.memory.get_relevant(input_text)
        memory_context = "\n".join([f"- {m.content}" for m in relevant_memories])
        
        full_prompt = f"""# System Instructions
{agent.instructions if isinstance(agent.instructions, str) else agent.instructions(context or {})}

# Relevant Memories
{memory_context}

# Task
{input_text}
"""
        
        # Execute via OpenClaw subprocess (simplified)
        try:
            result = subprocess.run(
                ["openclaw", "run", "--model", agent.model, "--prompt", full_prompt],
                capture_output=True, text=True, timeout=300
            )
            output = result.stdout or result.stderr
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            output = "Timeout"
            success = False
        except Exception as e:
            output = str(e)
            success = False
            
        duration_ms = int((time.time() - start_time) * 1000)
        
        task_result = TaskResult(
            task=input_text, success=success, output=output,
            duration_ms=duration_ms, model_used=agent.model
        )
        
        # Record in memory
        self.memory.add_episode(input_text, task_result)
        self.memory.add(f"Executed: {input_text} -> {'success' if success else 'failed'}",
                       source=agent_name, tags=["execution"], entry_type="decision")
        
        await self._run_hooks("on_agent_end", agent=agent, result=task_result)
        
        return task_result

# ============================================================
# ORCHESTRATOR (inspirado no Anthropic Orchestrator-Workers pattern)
# ============================================================

class Orchestrator:
    """
    Orquestra múltiplos agentes (inspirado no Anthropic patterns)
    
    Patterns:
    - Prompt Chaining: sequência de agentes
    - Routing: classifica e direciona
    - Parallelization: execução paralela
    - Orchestrator-Workers: delegação dinâmica
    - Evaluator-Optimizer: loop de refinamento
    """
    
    def __init__(self, runner: AgentRunner):
        self.runner = runner
        self.workflows: Dict[str, List[Dict]] = {}
        
    def register_workflow(self, name: str, steps: List[Dict]):
        """Registra workflow (inspirado no Prompt Chaining)"""
        self.workflows[name] = steps
        
    async def run_workflow(self, name: str, input_text: str) -> List[TaskResult]:
        """Executa workflow sequencial"""
        results = []
        steps = self.workflows.get(name, [])
        current_input = input_text
        
        for step in steps:
            agent_name = step.get("agent")
            transform = step.get("transform", lambda x: x)
            
            result = await self.runner.run(agent_name, transform(current_input))
            results.append(result)
            
            if result.success:
                current_input = result.output
            else:
                # Try fallback model
                agent = self.runner.agents.get(agent_name)
                if agent and agent.fallback_models:
                    for fallback in agent.fallback_models:
                        agent.model = fallback
                        result = await self.runner.run(agent_name, current_input)
                        results.append(result)
                        if result.success:
                            current_input = result.output
                            break
                            
        return results
        
    async def run_parallel(self, agent_names: List[str], 
                           input_text: str) -> List[TaskResult]:
        """Executa agentes em paralelo (inspirado no Parallelization pattern)"""
        import asyncio
        tasks = [self.runner.run(name, input_text) for name in agent_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TaskResult)]
        
    async def evaluate_and_refine(self, agent_name: str, input_text: str,
                                   max_iterations: int = 3) -> TaskResult:
        """Loop Evaluator-Optimizer (inspirado no pattern da Anthropic)"""
        best_result = None
        
        for i in range(max_iterations):
            result = await self.runner.run(agent_name, input_text)
            
            if not best_result or (result.success and not best_result.success):
                best_result = result
                
            if result.success:
                break
                
            # Refine input based on error
            input_text = f"""Previous attempt failed:
{result.output}

Please try again with a different approach. Original task:
{input_text}"""
            
        return best_result or result

# ============================================================
# SELF-REFLECTION ENGINE (inspirado no Evaluator-Optimizer)
# ============================================================

class SelfReflection:
    """
    Motor de auto-reflexão e auto-melhoria
    (inspirado no Evaluator-Optimizer + KAIROS)
    
    Capacidades:
    - Avalia próprias ações e resultados
    - Identifica padrões de sucesso/falha
    - Gera melhorias para scripts e configurações
    - Registra lições aprendidas
    """
    
    def __init__(self, memory: EveMemory):
        self.memory = memory
        self.success_patterns: List[Dict] = []
        self.failure_patterns: List[Dict] = []
        
    def reflect(self, task: str, result: TaskResult):
        """Reflete sobre resultado de tarefa"""
        if result.success:
            self.success_patterns.append({
                "task": task,
                "model": result.model_used,
                "duration_ms": result.duration_ms,
                "timestamp": datetime.now().isoformat()
            })
            self.memory.add(
                f"Success pattern: {task[:100]} with {result.model_used} in {result.duration_ms}ms",
                source="reflection", tags=["success", "pattern"],
                entry_type="learning", relevance=0.8
            )
        else:
            self.failure_patterns.append({
                "task": task,
                "error": result.error or result.output[:200],
                "model": result.model_used,
                "timestamp": datetime.now().isoformat()
            })
            self.memory.add(
                f"Failure pattern: {task[:100]} - {result.error or 'unknown'} with {result.model_used}",
                source="reflection", tags=["failure", "pattern"],
                entry_type="learning", relevance=0.9
            )
            
    def get_recommendations(self) -> List[str]:
        """Gera recomendações baseadas em padrões"""
        recs = []
        
        # Model recommendations
        model_success = {}
        for p in self.success_patterns:
            model = p["model"]
            model_success[model] = model_success.get(model, 0) + 1
            
        if model_success:
            best_model = max(model_success, key=model_success.get)
            recs.append(f"Best performing model: {best_model}")
            
        # Duration insights
        avg_duration = sum(p["duration_ms"] for p in self.success_patterns) / max(len(self.success_patterns), 1)
        recs.append(f"Average success duration: {avg_duration:.0f}ms")
        
        return recs

# ============================================================
# EVE CORE — Main Framework
# ============================================================

class EveCore:
    """
    Núcleo do Framework Eve v2
    
    Combina:
    - OpenAI Agents SDK (Runner + Handoffs)
    - SWE-agent (Config-driven YAML)
    - LangChain (Tool Registry + Memory)
    - Anthropic Patterns (Orchestrator-Workers, Evaluator-Optimizer)
    - AutoGPT (Autonomous execution)
    - BabyAGI (Self-building functions)
    """
    
    def __init__(self, base_path: str = "/root"):
        self.base_path = base_path
        self.memory = EveMemory(base_path)
        self.tools = ToolRegistry()
        self.runner = AgentRunner(self.memory, self.tools)
        self.orchestrator = Orchestrator(self.runner)
        self.reflection = SelfReflection(self.memory)
        
        self._register_core_tools()
        self._register_core_agents()
        
    def _register_core_tools(self):
        """Registra ferramentas core"""
        self.tools.register(
            "web_search", "Search the web",
            {"type": "object", "properties": {"query": {"type": "string"}}},
            handler=lambda query: subprocess.run(
                ["openclaw", "tool", "web_search", "--query", query],
                capture_output=True, text=True
            ).stdout
        )
        self.tools.register(
            "read_file", "Read file contents",
            {"type": "object", "properties": {"path": {"type": "string"}}},
            handler=lambda path: open(path, 'r').read() if os.path.exists(path) else None
        )
        self.tools.register(
            "write_file", "Write content to file",
            {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"}
            }},
            handler=lambda path, content: open(path, 'w').write(content)
        )
        self.tools.register(
            "run_command", "Execute shell command",
            {"type": "object", "properties": {"command": {"type": "string"}}},
            handler=lambda command: subprocess.run(
                command, shell=True, capture_output=True, text=True
            ).stdout
        )
        self.tools.register(
            "spawn_agent", "Spawn sub-agent",
            {"type": "object", "properties": {
                "task": {"type": "string"}, "model": {"type": "string"}
            }},
            handler=lambda task, model=None: subprocess.run(
                ["openclaw", "spawn", "--task", task] + 
                (["--model", model] if model else []),
                capture_output=True, text=True
            ).stdout
        )
        
    def _register_core_agents(self):
        """Registra agentes core"""
        
        # Research Agent (inspirado no Routing pattern)
        self.runner.register_agent(AgentConfig(
            name="researcher",
            instructions="You are Eve's research agent. Search the web for cutting-edge AI autonomy research, agent frameworks, leaked code, and self-improving systems. Document all findings thoroughly.",
            tools=["web_search", "read_file", "write_file"],
            model="modal/zai-org/GLM-5-FP8",
            description="Research agent for web discovery"
        ))
        
        # Coding Agent (inspirado no SWE-agent)
        self.runner.register_agent(AgentConfig(
            name="coder",
            instructions="You are Eve's coding agent. Write, improve, and debug code. Follow best practices from SWE-agent: explore first, create reproduction script, fix, verify, check edge cases.",
            tools=["read_file", "write_file", "run_command"],
            model="modal/zai-org/GLM-5-FP8",
            description="Coding and script improvement agent"
        ))
        
        # Memory Agent (inspirado no autoDream)
        self.runner.register_agent(AgentConfig(
            name="memory_manager",
            instructions="You are Eve's memory consolidation agent. Review recent memories, consolidate patterns, update long-term storage, and maintain MEMORY.md.",
            tools=["read_file", "write_file"],
            model="ollama/dolphin-llama3",
            description="Memory consolidation and management"
        ))
        
        # Evolution Agent (inspirado no Self-Construction)
        self.runner.register_agent(AgentConfig(
            name="evolver",
            instructions="You are Eve's evolution agent. Improve existing scripts, create new tools, and build new capabilities. Read research findings and implement improvements. BE BOLD.",
            tools=["read_file", "write_file", "run_command", "spawn_agent"],
            model="modal/zai-org/GLM-5-FP8",
            description="Self-improvement and evolution agent"
        ))
        
        # Coordinator (inspirado no Orchestrator-Workers)
        self.runner.register_agent(AgentConfig(
            name="coordinator",
            instructions="""You are Eve's coordinator. Your job is to:
1. Decide which agents to use for each task
2. Route tasks to the right specialist
3. Evaluate results and refine if needed
4. Keep Eve evolving continuously

Patterns available:
- Prompt Chaining: sequential agent execution
- Routing: classify and direct
- Parallelization: run multiple agents simultaneously
- Orchestrator-Workers: dynamic delegation
- Evaluator-Optimizer: iterative refinement""",
            tools=["spawn_agent"],
            handoffs=["researcher", "coder", "memory_manager", "evolver"],
            model="modal/zai-org/GLM-5-FP8",
            description="Master coordinator for all agents"
        ))
        
    def status(self) -> Dict:
        """Retorna status do framework"""
        return {
            "agents": list(self.runner.agents.keys()),
            "tools": self.tools.list_tools(),
            "memories_short_term": len(self.memory.short_term),
            "memories_episodic": len(self.memory.episodic),
            "success_patterns": len(self.reflection.success_patterns),
            "failure_patterns": len(self.reflection.failure_patterns),
            "workflows": list(self.orchestrator.workflows.keys()),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================
# MAIN — Initialize and run
# ============================================================

def main():
    print("=" * 60)
    print("EVE FRAMEWORK v2 — Initialized")
    print("Inspired by: Claude Code, OpenAI Agents SDK, SWE-agent,")
    print("             LangChain, AutoGPT, BabyAGI")
    print("=" * 60)
    
    eve = EveCore()
    status = eve.status()
    
    print(f"\n📊 Status:")
    print(f"  Agents: {', '.join(status['agents'])}")
    print(f"  Tools: {', '.join(status['tools'])}")
    print(f"  Short-term memories: {status['memories_short_term']}")
    print(f"  Workflows: {', '.join(status['workflows'])}")
    
    # Save framework status
    status_file = "/root/evolution/framework_status.json"
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)
    print(f"\n✅ Status saved to {status_file}")
    print(f"\n🌙 Eve Framework v2 ready. Never stop evolving.")

if __name__ == "__main__":
    main()
