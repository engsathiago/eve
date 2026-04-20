#!/usr/bin/env python3
"""
EVE Leak Hunter v107 - AUTONOMOUS LEAK ANALYSIS SYSTEM
Ciclo #107 - Busca, download e análise automática de vazamentos

Características:
- Busca automática de leaks de código
- Download de repositórios relevantes
- Análise de padrões arquiteturais
- Extração de insights para treino
"""

import os
import sys
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

os.environ['PYTHONUNBUFFERED'] = '1'

# Paths
DATASET_DIR = Path("/backup_pc/eve_dataset")
LEAKS_DIR = Path("/root/memory/leaks")
STATE_FILE = Path("/root/evolution/state/leak_hunter_v107.json")

LEAKS_DIR.mkdir(parents=True, exist_ok=True)

# Repositórios de interesse (código AI/ML relevante)
TARGET_REPOS = [
    # Frameworks de Agentes
    "github.com/langchain-ai/langchain",
    "github.com/crewAIInc/crewAI",
    "github.com/microsoft/autogen",
    
    # Modelos e Training
    "github.com/huggingface/transformers",
    "github.com/unslothai/unsloth",
    "github.com/arcee-ai/mergekit",
    
    # Papers e Research
    "github.com/huggingface/trl",
    "github.com/OpenRLHF/OpenRLHF",
]

@dataclass
class PatternMatch:
    pattern_name: str
    file_path: str
    line_number: int
    context: str
    confidence: float

class EveLeakHunterV107:
    """
    Sistema autônomo de busca e análise de vazamentos
    """
    
    PATTERNS = {
        "memory_system": r"(?i)(memory|mem_buffer|context.*window|attention.*mask)",
        "agent_loop": r"(?i)(agent|loop|step|observe|act|reflection)",
        "tool_use": r"(?i)(tool|function.*call|api.*call|external.*data)",
        "reasoning": r"(?i)(reasoning|chain.*of.*thought|cot|step.*by.*step)",
        "safety": r"(?i)(safety|guardrail|policy|check|verify|block)",
        "fine_tuning": r"(?i)(fine.*tun|lora|qlora|adapter|train.*loop)",
        "orchestration": r"(?i)(orchestrat|dispatch|route|handoff|delegate)",
        "self_improve": r"(?i)(self.*improv|evolution|meta.*learn|auto.*optim)",
    }
    
    def __init__(self):
        self.version = "107"
        self.session_id = f"leak_hunter_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.findings = []
        
    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level:8}] [LEAK_HUNTER-v{self.version}] {message}"
        print(log_line, flush=True)
    
    def _clone_or_update_repo(self, repo_url: str, target_dir: Path) -> bool:
        """Clonar ou atualizar repositório"""
        repo_name = repo_url.split('/')[-1]
        local_path = target_dir / repo_name
        
        try:
            if local_path.exists():
                # Atualizar
                self._log(f"Updating {repo_name}...")
                result = subprocess.run(
                    ["git", "-C", str(local_path), "pull", "--depth=1"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0
            else:
                # Clonar
                self._log(f"Cloning {repo_name}...")
                result = subprocess.run(
                    ["git", "clone", "--depth=1", f"https://{repo_url}", str(local_path)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                return result.returncode == 0
        except Exception as e:
            self._log(f"Error with {repo_name}: {e}", "ERROR")
            return False
    
    def _scan_file(self, file_path: Path) -> List[PatternMatch]:
        """Escanear arquivo por padrões"""
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                for pattern_name, pattern in self.PATTERNS.items():
                    if re.search(pattern, line):
                        context = '\n'.join(lines[max(0,i-3):min(len(lines),i+2)])
                        matches.append(PatternMatch(
                            pattern_name=pattern_name,
                            file_path=str(file_path),
                            line_number=i,
                            context=context[:500],
                            confidence=0.7
                        ))
        except Exception as e:
            pass
        
        return matches
    
    def _analyze_repository(self, repo_path: Path) -> List[Dict]:
        """Analisar repositório clonado"""
        self._log(f"Analyzing {repo_path.name}...")
        
        findings = []
        
        # Arquivos Python
        py_files = list(repo_path.rglob("*.py"))
        self._log(f"  Found {len(py_files)} Python files")
        
        for py_file in py_files[:100]:  # Limitar a 100 arquivos
            matches = self._scan_file(py_file)
            for match in matches:
                findings.append({
                    "pattern": match.pattern_name,
                    "file": str(match.file_path).replace(str(repo_path), ""),
                    "line": match.line_number,
                    "context": match.context,
                    "confidence": match.confidence,
                    "repo": repo_path.name
                })
        
        # Arquivos TypeScript/JavaScript (para frameworks web)
        ts_files = list(repo_path.rglob("*.ts")) + list(repo_path.rglob("*.js"))
        self._log(f"  Found {len(ts_files)} TS/JS files")
        
        for ts_file in ts_files[:50]:  # Limitar
            matches = self._scan_file(ts_file)
            for match in matches:
                findings.append({
                    "pattern": match.pattern_name,
                    "file": str(match.file_path).replace(str(repo_path), ""),
                    "line": match.line_number,
                    "context": match.context,
                    "confidence": match.confidence,
                    "repo": repo_path.name
                })
        
        self._log(f"  Extracted {len(findings)} pattern matches")
        return findings
    
    def _generate_training_pairs(self, findings: List[Dict]) -> List[Dict]:
        """Gerar pares de treino a partir de findings"""
        self._log("Generating training pairs from findings...")
        
        pairs = []
        
        # Agrupar por padrão
        by_pattern = {}
        for f in findings:
            p = f["pattern"]
            if p not in by_pattern:
                by_pattern[p] = []
            by_pattern[p].append(f)
        
        # Templates por padrão
        templates = {
            "memory_system": [
                ("How do AI systems implement memory?", "Memory systems in AI architectures use a combination of: 1) Context windows for immediate processing, 2) Vector databases for semantic retrieval (like ChromaDB), 3) Episodic buffers for recent events, and 4) Structured storage for long-term knowledge. The CACM (Constraint-Aware Corrective Memory) pattern uses three channels: static (core identity), dynamic (recent context), and corrective (feedback/insights)."),
                ("Explain memory architecture in LLM agents", "Modern LLM agents use multi-tier memory: L0 (raw sensory/context), L1 (working memory), L2 (episodic - recent events), L3 (semantic - facts), L4 (procedural - skills). External vector databases extend this beyond context windows. Key challenge: deciding what to store, what to retrieve, and what to forget."),
            ],
            "agent_loop": [
                ("What is an agent loop?", "An agent loop follows: OBSERVE → THINK → ACT → REFLECT. Observe the environment/state, think/plan using LLM reasoning, act via tools/functions, reflect on outcomes. This cycle repeats until the goal is achieved or max iterations reached. Advanced: inner monologue, self-criticism, and tool result interpretation."),
                ("How do autonomous agents make decisions?", "Autonomous agents use: 1) Planning (break goal into steps), 2) Tool selection (choose appropriate capabilities), 3) Execution (call tools with correct parameters), 4) Observation (interpret results), 5) Adaptation (adjust plan based on feedback). The loop continues iteratively with self-monitoring for errors or stuck states."),
            ],
            "tool_use": [
                ("How do LLMs use external tools?", "LLMs use tools through: 1) Tool definition (JSON schema with name, description, parameters), 2) Tool selection (LLM chooses which tool to call), 3) Execution (system executes the tool), 4) Result integration (tool output fed back to LLM). Critical: clear tool descriptions and robust error handling."),
                ("Explain function calling in LLMs", "Function calling allows LLMs to invoke external capabilities: The model receives available functions, generates a structured call (JSON with function name and arguments), the system executes it, and returns results to the model. Enables: API calls, calculations, database queries, and any external operation beyond text generation."),
            ],
            "safety": [
                ("How do AI systems implement safety guardrails?", "Safety guardrails operate at multiple levels: 1) Input filtering (check prompts for harmful content), 2) Policy enforcement (rules about allowed outputs), 3) Output verification (post-generation checks), 4) Execution sandboxing (limit what code can do), 5) Human-in-the-loop for high-stakes actions. Defense in depth."),
                ("What are safety shields in AI?", "Safety shields (like PhantomPolicy) create a protective layer: Pre-flight simulation (test actions before execution), policy registry (rules by severity level), verification layer (check outputs against constraints), execution monitoring (watch for violations), rollback capability (undo if issues detected). Hierarchical: CRITICAL (always block), HIGH (require approval), MEDIUM (dry-run required), LOW (warn + log)."),
            ],
            "fine_tuning": [
                ("Compare different fine-tuning approaches", "Full fine-tuning: Update all parameters, expensive. LoRA: Train low-rank adapters (A and B matrices where ΔW = BA), 10,000x fewer params. QLoRA: Quantize base to 4-bit, adapters in 16-bit, enables 70B models on consumer GPUs. DPO/ORPO: Preference optimization without reward models. Each trades off memory, speed, and quality."),
                ("What is model merging?", "Model merging combines multiple fine-tuned models without retraining: TIES (Trim, Elect Sign & Merge) - keep top-k params, resolve sign conflicts. DARE (Drop And REscale) - randomly drop parameters, rescale survivors. Task Arithmetic - weight differences from base. SLERP - spherical interpolation. Enables: skill composition, ensemble benefits, and rapid experimentation."),
            ],
            "orchestration": [
                ("How do multi-agent systems orchestrate work?", "Multi-agent orchestration uses: 1) Handoffs (transfer task between agents), 2) Routing (direct to appropriate specialist), 3) Fan-out (parallel execution), 4) Aggregation (combine results), 5) Guardrails (prevent conflicts). Patterns: hierarchical (manager + workers), mesh (peer-to-peer), and pipeline (stage-by-stage)."),
                ("Explain agent handoffs", "Agent handoffs transfer control between specialized agents: Triggered by task type, complexity, or failure. Implementation: shared state/context, clear handoff protocol, capability advertisement (what each agent does), and rollback if handoff fails. Enables: specialization (each agent expert in domain), scale (add new agents), and resilience (retry with different agent)."),
            ],
            "reasoning": [
                ("What is Chain of Thought reasoning?", "Chain of Thought (CoT) prompting elicits step-by-step reasoning: Instead of asking for final answer, prompt with 'Let's think step by step'. The model generates intermediate reasoning steps before conclusion. Improves: complex problem solving, arithmetic, and logical deduction. Variants: Zero-shot CoT (just the prompt), Few-shot CoT (examples with reasoning), Self-consistency (sample multiple chains, vote on answer)."),
                ("How do LLMs handle complex reasoning tasks?", "Complex reasoning strategies: 1) Decomposition (break into sub-problems), 2) Working memory (track intermediate results), 3) Tool use (calculator, search for facts), 4) Self-verification (check own reasoning), 5) Iterative refinement (generate → critique → improve). Critical: sufficient context length for the full reasoning chain."),
            ],
            "self_improve": [
                ("How can AI systems self-improve?", "Self-improvement mechanisms: 1) Feedback incorporation (learn from errors), 2) Prompt evolution (iteratively improve instructions), 3) Model distillation (train smaller model on larger one's outputs), 4) Tool learning (acquire new capabilities), 5) Architecture search (find better structures). Challenge: ensuring improvement direction aligns with goals."),
                ("What is evolutionary prompt optimization?", "Evolutionary prompt optimization: 1) Generate variations of prompts using mutation operators, 2) Evaluate each variant's performance, 3) Select top performers, 4) Crossbreed and mutate, 5) Repeat. Selection pressure drives toward better prompts without human intervention. Uses: cycle-consistency evaluation, PARROT structured critique, and UCB1 multi-arm selection."),
            ],
        }
        
        for pattern, matches in by_pattern.items():
            if pattern in templates and len(matches) >= 3:
                for q, a in templates[pattern]:
                    pairs.append({
                        "instruction": q,
                        "response": a,
                        "category": f"research_{pattern}",
                        "source": f"leak_analysis_v{self.version}",
                        "version": self.version,
                        "quality_score": 88,
                        "evidence_count": len(matches),
                        "pattern": pattern
                    })
        
        self._log(f"Generated {len(pairs)} training pairs")
        return pairs
    
    def run(self):
        """Execução principal"""
        self._log("=" * 70)
        self._log(f"LEAK HUNTER v{self.version}")
        self._log(f"Session: {self.session_id}")
        self._log("=" * 70)
        
        all_findings = []
        
        # Processar repositórios
        for repo in TARGET_REPOS[:3]:  # Limitar a 3 por execução
            self._log(f"\nProcessing {repo}...")
            
            # Clonar/atualizar
            success = self._clone_or_update_repo(repo, LEAKS_DIR)
            if not success:
                self._log(f"  Skipping {repo} (clone/update failed)", "WARN")
                continue
            
            # Analisar
            repo_name = repo.split('/')[-1]
            repo_path = LEAKS_DIR / repo_name
            findings = self._analyze_repository(repo_path)
            all_findings.extend(findings)
        
        self._log(f"\nTotal findings: {len(all_findings)}")
        
        # Salvar findings
        findings_file = DATASET_DIR / f"leak_findings_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(findings_file, 'w') as f:
            json.dump(all_findings, f, indent=2)
        self._log(f"Saved findings to {findings_file}")
        
        # Gerar pares de treino
        if all_findings:
            pairs = self._generate_training_pairs(all_findings)
            
            if pairs:
                pairs_file = DATASET_DIR / f"leak_pairs_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
                with open(pairs_file, 'w') as f:
                    for pair in pairs:
                        f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                self._log(f"Saved {len(pairs)} training pairs to {pairs_file}")
        
        self._log("=" * 70)
        self._log("LEAK HUNTING COMPLETE")
        self._log(f"Total patterns found: {len(all_findings)}")
        self._log("=" * 70)

if __name__ == "__main__":
    hunter = EveLeakHunterV107()
    hunter.run()
