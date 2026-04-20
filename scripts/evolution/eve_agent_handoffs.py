#!/usr/bin/env python3
"""
eve_agent_handoffs.py — Agent Handoffs Framework for Eve
Ciclo #61 — Implementação de delegação entre agentes especializados
Baseado em OpenAI Agents SDK patterns + LangGraph handoffs

Handoffs = múltiplos agentes especializados, um passa controle para outro
Cada agente tem contexto, tools, e objetivo específico.
"""

import json
import uuid
from datetime import datetime, UTC
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

# Constants
HANDOFF_LOG_DIR = Path("/root/evolution/handoff_logs")
HANDOFF_LOG_DIR.mkdir(parents=True, exist_ok=True)

T = TypeVar('T')

class HandoffReason(Enum):
    """Why control is being transferred"""
    SPECIALIZATION = auto()      # Need different expertise
    ESCALATION = auto()          # Too complex for current agent
    DELEGATION = auto()          # Subtask completion
    ERROR_RECOVERY = auto()      # Current agent failed
    COMPLETION = auto()          # Task done

@dataclass
class AgentContext:
    """Shared context passed between agents during handoffs"""
    session_id: str
    original_goal: str
    current_agent: Optional[str] = None
    previous_agents: List[str] = field(default_factory=list)
    accumulated_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    handoff_count: int = 0
    max_handoffs: int = 10  # Prevent infinite loops
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    
    def fork(self, new_agent: str, reason: HandoffReason) -> "AgentContext":
        """Create child context for handoff"""
        new_ctx = AgentContext(
            session_id=self.session_id,
            original_goal=self.original_goal,
            current_agent=new_agent,
            previous_agents=self.previous_agents + [self.current_agent] if self.current_agent else [],
            accumulated_results=dict(self.accumulated_results),
            metadata=dict(self.metadata),
            handoff_count=self.handoff_count + 1,
            max_handoffs=self.max_handoffs,
            created_at=self.created_at
        )
        new_ctx.metadata["last_handoff_reason"] = reason.name
        new_ctx.metadata["last_handoff_time"] = datetime.now(UTC).isoformat()
        return new_ctx
    
    def can_handoff(self) -> bool:
        """Check if more handoffs are allowed"""
        return self.handoff_count < self.max_handoffs

@dataclass  
class HandoffResult:
    """Result from agent execution"""
    success: bool
    output: Any
    next_agent: Optional[str] = None  # None = task complete
    handoff_reason: Optional[HandoffReason] = None
    context_updates: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

class SpecializedAgent:
    """
    Base class for specialized agents that can participate in handoffs.
    
    Subclass and implement:
    - can_handle(goal) -> bool
    - execute(context, goal) -> HandoffResult
    """
    
    name: str = "base_agent"
    description: str = "Base agent - override me"
    capabilities: List[str] = []
    
    def can_handle(self, goal: str, context: AgentContext) -> float:
        """
        Return confidence (0.0-1.0) that this agent can handle the goal.
        Override in subclasses.
        """
        return 0.0
    
    def execute(self, context: AgentContext, goal: str) -> HandoffResult:
        """
        Execute the agent's specialized task.
        Return HandoffResult with success/failure and optional next agent.
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def handoff_to(self, agent_name: str, reason: HandoffReason, 
                   context: AgentContext, output: Any = None,
                   message: str = "") -> HandoffResult:
        """Helper to create handoff result"""
        return HandoffResult(
            success=True,
            output=output,
            next_agent=agent_name,
            handoff_reason=reason,
            message=message
        )
    
    def complete(self, output: Any, message: str = "") -> HandoffResult:
        """Helper to mark task as complete"""
        return HandoffResult(
            success=True,
            output=output,
            next_agent=None,
            handoff_reason=HandoffReason.COMPLETION,
            message=message
        )


class ResearchAgent(SpecializedAgent):
    """Agent specialized in web research and information gathering"""
    
    name = "research"
    description = "Web research, information gathering, paper analysis"
    capabilities = ["web_search", "paper_analysis", "trend_detection"]
    
    def can_handle(self, goal: str, context: AgentContext) -> float:
        keywords = ["research", "search", "find", "analyze", "paper", "arxiv", "web"]
        score = sum(1 for kw in keywords if kw in goal.lower()) / len(keywords)
        return min(score * 2, 1.0)  # Scale up
    
    def execute(self, context: AgentContext, goal: str) -> HandoffResult:
        # Simulate research
        print(f"  [{self.name}] Executing: {goal[:50]}...")
        
        # Store result in context
        result = {
            "agent": self.name,
            "action": "research",
            "goal": goal,
            "findings": ["finding_1", "finding_2"],  # Would be real data
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        context.accumulated_results[self.name] = result
        
        # Decide next step
        if "implement" in goal.lower() or "create" in goal.lower():
            return self.handoff_to(
                "builder", 
                HandoffReason.DELEGATION,
                context,
                result,
                "Research complete. Handing off to builder for implementation."
            )
        
        return self.complete(result, "Research task completed.")


class BuilderAgent(SpecializedAgent):
    """Agent specialized in code/script creation"""
    
    name = "builder"
    description = "Code generation, script creation, file writing"
    capabilities = ["code_gen", "script_writing", "file_ops"]
    
    def can_handle(self, goal: str, context: AgentContext) -> float:
        keywords = ["create", "build", "write", "script", "code", "implement", "generate"]
        score = sum(1 for kw in keywords if kw in goal.lower()) / len(keywords)
        return min(score * 2, 1.0)
    
    def execute(self, context: AgentContext, goal: str) -> HandoffResult:
        print(f"  [{self.name}] Executing: {goal[:50]}...")
        
        # Use previous research if available
        research = context.accumulated_results.get("research", {})
        
        result = {
            "agent": self.name,
            "action": "build",
            "goal": goal,
            "based_on_research": bool(research),
            "artifacts_created": ["artifact_1"],
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        context.accumulated_results[self.name] = result
        
        return self.complete(result, "Build task completed.")


class ConsolidationAgent(SpecializedAgent):
    """Agent specialized in memory consolidation and insight extraction"""
    
    name = "consolidation"
    description = "Memory consolidation, insight extraction, learning"
    capabilities = ["memory_consolidation", "insight_extraction", "pattern_recognition"]
    
    def can_handle(self, goal: str, context: AgentContext) -> float:
        keywords = ["consolidate", "learn", "extract", "insight", "memory", "review"]
        score = sum(1 for kw in keywords if kw in goal.lower()) / len(keywords)
        return min(score * 2, 1.0)
    
    def execute(self, context: AgentContext, goal: str) -> HandoffResult:
        print(f"  [{self.name}] Executing: {goal[:50]}...")
        
        # Consolidate all previous results
        insights = []
        for agent_name, result in context.accumulated_results.items():
            insights.append(f"From {agent_name}: {result.get('action', 'unknown')}")
        
        result = {
            "agent": self.name,
            "action": "consolidate",
            "insights": insights,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        context.accumulated_results[self.name] = result
        
        return self.complete(result, "Consolidation complete.")


class HandoffOrchestrator:
    """
    Orchestrates handoffs between specialized agents.
    
    Usage:
        orchestrator = HandoffOrchestrator()
        orchestrator.register(ResearchAgent())
        orchestrator.register(BuilderAgent())
        
        result = orchestrator.run("Research and build X")
    """
    
    def __init__(self, max_steps: int = 20):
        self.agents: Dict[str, SpecializedAgent] = {}
        self.max_steps = max_steps
        self.execution_log: List[Dict] = []
    
    def register(self, agent: SpecializedAgent):
        """Register a specialized agent"""
        self.agents[agent.name] = agent
        print(f"[Handoff] Registered agent: {agent.name}")
    
    def select_agent(self, goal: str, context: AgentContext, exclude: List[str] = None) -> Optional[str]:
        """Select best agent for goal based on confidence scores"""
        exclude = exclude or []
        
        scores = []
        for name, agent in self.agents.items():
            if name in exclude:
                continue
            score = agent.can_handle(goal, context)
            if score > 0:
                scores.append((score, name))
        
        if not scores:
            return None
        
        scores.sort(reverse=True)
        return scores[0][1]
    
    def run(self, goal: str, starting_agent: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute task with potential handoffs between agents.
        
        Returns final result with full execution trace.
        """
        session_id = str(uuid.uuid4())[:8]
        context = AgentContext(
            session_id=session_id,
            original_goal=goal,
            current_agent=starting_agent
        )
        
        print(f"\n{'='*60}")
        print(f"[Handoff] Starting session {session_id}")
        print(f"[Handoff] Goal: {goal}")
        print(f"{'='*60}\n")
        
        # Select starting agent
        if not starting_agent:
            starting_agent = self.select_agent(goal, context)
            if not starting_agent:
                return {
                    "success": False,
                    "error": "No agent could handle this goal",
                    "goal": goal
                }
        
        context.current_agent = starting_agent
        current_agent_name = starting_agent
        step = 0
        
        while step < self.max_steps:
            step += 1
            
            if not context.can_handoff():
                print(f"[Handoff] Max handoffs reached. Stopping.")
                break
            
            agent = self.agents.get(current_agent_name)
            if not agent:
                return {
                    "success": False,
                    "error": f"Agent '{current_agent_name}' not found",
                    "step": step
                }
            
            print(f"\n[Step {step}] Agent: {current_agent_name}")
            print(f"  Context: {len(context.previous_agents)} previous handoffs")
            
            # Execute
            try:
                result = agent.execute(context, goal)
            except Exception as e:
                print(f"  ERROR: {e}")
                result = HandoffResult(
                    success=False,
                    output=None,
                    next_agent=None,
                    handoff_reason=HandoffReason.ERROR_RECOVERY,
                    message=f"Error: {e}"
                )
            
            # Log
            log_entry = {
                "step": step,
                "agent": current_agent_name,
                "success": result.success,
                "handoff_reason": result.handoff_reason.name if result.handoff_reason else None,
                "next_agent": result.next_agent,
                "message": result.message,
                "timestamp": datetime.now(UTC).isoformat()
            }
            self.execution_log.append(log_entry)
            
            # Update context with any custom updates
            context.accumulated_results.update(result.context_updates)
            
            # Check if complete
            if result.next_agent is None:
                print(f"\n{'='*60}")
                print(f"[Handoff] Task complete after {step} steps")
                print(f"[Handoff] Final agent: {current_agent_name}")
                print(f"{'='*60}\n")
                
                return {
                    "success": result.success,
                    "session_id": session_id,
                    "goal": goal,
                    "steps": step,
                    "agents_involved": context.previous_agents + [current_agent_name],
                    "final_output": result.output,
                    "final_message": result.message,
                    "execution_log": self.execution_log,
                    "accumulated_results": context.accumulated_results
                }
            
            # Handoff to next agent
            print(f"  → Handoff to: {result.next_agent} ({result.handoff_reason.name})")
            context = context.fork(result.next_agent, result.handoff_reason or HandoffReason.DELEGATION)
            current_agent_name = result.next_agent
        
        # Max steps reached
        return {
            "success": False,
            "error": "Max steps reached",
            "steps": step,
            "execution_log": self.execution_log
        }
    
    def save_session(self, result: Dict, path: Optional[Path] = None):
        """Save session result to file"""
        if path is None:
            path = HANDOFF_LOG_DIR / f"session_{result.get('session_id', 'unknown')}.json"
        
        with open(path, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"[Handoff] Session saved to {path}")


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("Eve Agent Handoffs Framework — Self-Test")
    print("=" * 60)
    
    # Create orchestrator
    orchestrator = HandoffOrchestrator(max_steps=10)
    
    # Register agents
    orchestrator.register(ResearchAgent())
    orchestrator.register(BuilderAgent())
    orchestrator.register(ConsolidationAgent())
    
    # Test 1: Simple research task
    print("\n### Test 1: Research task (no handoff expected) ###")
    result = orchestrator.run("Research latest autonomous AI techniques")
    print(f"Success: {result['success']}")
    print(f"Agents involved: {result.get('agents_involved', [])}")
    
    # Reset for next test
    orchestrator.execution_log = []
    
    # Test 2: Multi-agent task with handoff
    print("\n### Test 2: Research and implement (handoff expected) ###")
    result = orchestrator.run("Research fine-tuning methods and implement a script")
    print(f"Success: {result['success']}")
    print(f"Agents involved: {result.get('agents_involved', [])}")
    print(f"Steps: {result.get('steps')}")
    
    # Save session
    orchestrator.save_session(result)
    
    print("\n" + "=" * 60)
    print("Agent Handoffs Framework ready.")
    print("Use HandoffOrchestrator to coordinate multiple specialized agents.")
    print("=" * 60)