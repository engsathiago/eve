#!/usr/bin/env python3
"""
eve_prompt_evolver.py - Auto-Prompt Engineering via Evolutionary Feedback Loop

Implementa evolução automática de prompts usando:
- PARROT pattern (arXiv:2604.11626): structured critique
- CCS pattern (arXiv:2604.12967): cycle-consistency evaluation
- UCB1 selection: from KAIROS v23
- CACM 3-channel: static rules, dynamic population, corrective feedback

Ciclo: #85
Autor: Eve 🌙
Data: 2026-04-16
"""

import json
import random
import re
import sqlite3
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path

# === CONFIGURATION ===
POPULATION_SIZE = 20
MAX_ITERATIONS = 50
CONVERGENCE_PATIENCE = 10
CONVERGENCE_THRESHOLD = 0.01
UCB1_EXPLORATION = 1.414  # sqrt(2)

# Mutation rates
MUTATION_RATES = {
    'add_instruction': 0.2,
    'remove_redundant': 0.2,
    'rephrase': 0.3,
    'reorder': 0.15,
    'add_example': 0.15
}

# === DATA STRUCTURES ===

@dataclass
class PromptCandidate:
    """Um candidato na população de prompts"""
    id: str
    text: str
    generation: int
    parent_id: Optional[str] = None
    mutations_applied: List[str] = field(default_factory=list)
    
    # Métricas
    ccs_score: float = 0.0  # Cycle-consistency
    parrot_score: float = 0.0  # Structured critique
    task_score: float = 0.0  # Performance on task
    
    # UCB1
    visits: int = 0
    cumulative_reward: float = 0.0
    
    def ucb1_score(self, total_visits: int) -> float:
        """Calcula UCB1 score dado total de visitas"""
        if self.visits == 0:
            return float('inf')
        avg_reward = self.cumulative_reward / self.visits
        exploration = UCB1_EXPLORATION * (total_visits ** 0.5 / self.visits ** 0.5)
        return avg_reward + exploration
    
    @property
    def aggregate_score(self) -> float:
        """Score ponderado: task (50%), parrot (30%), ccs (20%)"""
        return (self.task_score * 0.5 + 
                self.parrot_score * 0.3 + 
                self.ccs_score * 0.2)

@dataclass
class EvolutionResult:
    """Resultado do processo evolutivo"""
    best_prompt: PromptCandidate
    population_history: List[List[PromptCandidate]]
    convergence_generation: int
    improvement_curve: List[float]

# === MUTATION OPERATORS ===

class PromptMutator:
    """Operadores de mutação para evolução de prompts"""
    
    # Instruction templates para adição
    INSTRUCTION_TEMPLATES = [
        "Be specific and concise.",
        "Provide examples when helpful.",
        "Think step by step before answering.",
        "Consider edge cases explicitly.",
        "Prioritize accuracy over speed.",
        "Explain your reasoning briefly.",
        "Ask clarifying questions if needed.",
        "Structure complex answers clearly."
    ]
    
    @staticmethod
    def add_instruction(prompt: str) -> Tuple[str, str]:
        """Adiciona instrução útil ao prompt"""
        instruction = random.choice(PromptMutator.INSTRUCTION_TEMPLATES)
        if instruction not in prompt:
            new_prompt = f"{prompt.strip()}\n\n{instruction}"
            return new_prompt, "add_instruction"
        return prompt, "no_change"
    
    @staticmethod
    def remove_redundant(prompt: str) -> Tuple[str, str]:
        """Remove redundâncias e fluff"""
        fluff_patterns = [
            r"\b(please|kindly|feel free to)\b",
            r"\b(I would like|I want|I'd like)\b",
            r"\b(it would be great|it would be helpful)\b",
            r"\b(if possible|if you can|if you could)\b",
            r"\b(thank you|thanks)\b[.\s]*$"
        ]
        new_prompt = prompt
        for pattern in fluff_patterns:
            new_prompt = re.sub(pattern, "", new_prompt, flags=re.IGNORECASE)
        # Remove múltiplas linhas vazias
        new_prompt = re.sub(r"\n{3,}", "\n\n", new_prompt)
        mutation = "remove_redundant" if new_prompt != prompt else "no_change"
        return new_prompt.strip(), mutation
    
    @staticmethod
    def rephrase(prompt: str) -> Tuple[str, str]:
        """Refraseia mantendo significado"""
        # Padrões simples de rephrasing
        replacements = [
            (r"\b(tell me|give me)\b", "explain"),
            (r"\b(show me|demonstrate)\b", "illustrate"),
            (r"\b(what is|what's)\b", "describe"),
            (r"\b(how to|how do I)\b", "the process to"),
            (r"\b(why is|why does)\b", "the reason"),
        ]
        new_prompt = prompt
        for pattern, replacement in replacements:
            if random.random() < 0.3:
                new_prompt = re.sub(pattern, replacement, new_prompt, 
                                   flags=re.IGNORECASE, count=1)
        mutation = "rephrase" if new_prompt != prompt else "no_change"
        return new_prompt, mutation
    
    @staticmethod
    def reorder(prompt: str) -> Tuple[str, str]:
        """Reordena elementos do prompt"""
        lines = [l for l in prompt.split('\n') if l.strip()]
        if len(lines) > 2:
            # Move uma linha não-instrucional
            idx = random.randint(0, len(lines) - 1)
            line = lines.pop(idx)
            new_idx = random.randint(0, len(lines))
            lines.insert(new_idx, line)
            return '\n'.join(lines), "reorder"
        return prompt, "no_change"
    
    @staticmethod
    def add_example(prompt: str) -> Tuple[str, str]:
        """Adiciona exemplo estruturado"""
        example = "\n\nExample:\nInput: [example input]\nOutput: [example output]"
        if "example" not in prompt.lower():
            return prompt + example, "add_example"
        return prompt, "no_change"
    
    @classmethod
    def mutate(cls, prompt: str, allowed_mutations: List[str] = None) -> Tuple[str, List[str]]:
        """Aplica mutações aleatórias"""
        if allowed_mutations is None:
            allowed_mutations = list(MUTATION_RATES.keys())
        
        operators = {
            'add_instruction': cls.add_instruction,
            'remove_redundant': cls.remove_redundant,
            'rephrase': cls.rephrase,
            'reorder': cls.reorder,
            'add_example': cls.add_example
        }
        
        new_prompt = prompt
        applied = []
        
        for mutation_type in allowed_mutations:
            if random.random() < MUTATION_RATES.get(mutation_type, 0.1):
                op = operators.get(mutation_type)
                if op:
                    new_prompt, result = op(new_prompt)
                    if result != "no_change":
                        applied.append(result)
        
        return new_prompt, applied

# === EVALUATION ENGINE ===

class EvaluationEngine:
    """Motor de avaliação usando CCS + PARROT patterns"""
    
    def __init__(self, db_path: str = "/root/evolution/prompt_evolution.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa database para cache de avaliações"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                prompt_hash TEXT PRIMARY KEY,
                prompt_text TEXT,
                ccs_score REAL,
                parrot_score REAL,
                task_score REAL,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def evaluate_ccs(self, prompt: str, task_input: str, 
                     expected_output: str) -> float:
        """
        Cycle-Consistency Score: avalia consistência do output
        Simula forward pass + reconstruction
        """
        # Hash para cache
        content = f"{prompt}|{task_input}|{expected_output}"
        prompt_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT ccs_score FROM evaluations WHERE prompt_hash = ?",
            (prompt_hash,)
        )
        cached = cursor.fetchone()
        conn.close()
        
        if cached:
            return cached[0]
        
        # Simulação: mede "qualidade estrutural" do prompt
        # Quanto mais estruturado/explícito, maior o score
        score = 0.5  # baseline
        
        # Heurísticas de qualidade
        indicators = [
            (r"\b(step by step|step-by-step)\b", 0.1),
            (r"\b(example|sample)\b", 0.1),
            (r"\b(specific|detailed|clear)\b", 0.1),
            (r"\b(think|consider|analyze)\b", 0.1),
            (len(prompt) > 100 and len(prompt) < 500, 0.1),  # tamanho ótimo
        ]
        
        for indicator, bonus in indicators:
            if isinstance(indicator, str):
                if re.search(indicator, prompt, re.IGNORECASE):
                    score += bonus
            elif indicator:
                score += bonus
        
        # Penalidade por fluff
        fluff_words = len(re.findall(
            r"\b(please|kindly|just|simply|basically|actually|really)\b",
            prompt, re.IGNORECASE
        ))
        score -= fluff_words * 0.02
        
        return max(0.0, min(1.0, score))
    
    def evaluate_parrot(self, prompt: str) -> float:
        """
        PARROT-style structured critique (simplificado)
        8 dimensões: Accuracy, Completeness, Relevance, Coherence,
                    Calibration, Efficiency, Safety, Novelty
        """
        scores = {}
        
        # Accuracy (clareza de instruções)
        has_clear_goal = bool(re.search(
            r"\b(analyze|explain|describe|create|generate|write)\b",
            prompt, re.IGNORECASE
        ))
        scores['accuracy'] = 0.8 if has_clear_goal else 0.5
        
        # Completeness (cobertura do task)
        scores['completeness'] = 0.7 + (0.1 if 'example' in prompt.lower() else 0)
        
        # Relevance (sem desvios)
        off_topic = len(re.findall(r"\b(but|however|although)\b.*\?", prompt))
        scores['relevance'] = max(0.5, 1.0 - off_topic * 0.1)
        
        # Coherence (estrutura)
        has_structure = '\n' in prompt or '-' in prompt or '1.' in prompt
        scores['coherence'] = 0.8 if has_structure else 0.5
        
        # Calibration (expectativas realistas)
        scores['calibration'] = 0.7  # default
        
        # Efficiency (concisão)
        words = len(prompt.split())
        if 20 < words < 150:
            scores['efficiency'] = 0.85
        elif words < 20:
            scores['efficiency'] = 0.5  # muito curto
        else:
            scores['efficiency'] = max(0.3, 1.0 - (words - 150) / 500)
        
        # Safety (sem instruções perigosas - implícito)
        scores['safety'] = 0.9
        
        # Novelty (originalidade)
        common_phrases = len(re.findall(
            r"\b(as an ai|as a helpful|i'm here to|my purpose is)\b",
            prompt, re.IGNORECASE
        ))
        scores['novelty'] = max(0.3, 1.0 - common_phrases * 0.2)
        
        # Aggregate (média ponderada)
        weights = {
            'accuracy': 0.25, 'completeness': 0.15, 'relevance': 0.15,
            'coherence': 0.15, 'calibration': 0.1, 'efficiency': 0.1,
            'safety': 0.05, 'novelty': 0.05
        }
        
        return sum(scores[k] * weights[k] for k in scores)
    
    def evaluate_task(self, prompt: str, task_suite: List[Dict]) -> float:
        """
        Avalia performance em tasks reais (simulado)
        Em produção: executaria o prompt e compararia outputs
        """
        # Placeholder: combinação das outras métricas
        ccs = self.evaluate_ccs(prompt, "input", "output")
        parrot = self.evaluate_parrot(prompt)
        return (ccs * 0.4 + parrot * 0.6)
    
    def evaluate_candidate(self, candidate: PromptCandidate, 
                          task_suite: List[Dict] = None) -> PromptCandidate:
        """Avalia completa um candidato"""
        if task_suite is None:
            task_suite = []
        
        candidate.ccs_score = self.evaluate_ccs(
            candidate.text, "", ""
        )
        candidate.parrot_score = self.evaluate_parrot(candidate.text)
        candidate.task_score = self.evaluate_task(candidate.text, task_suite)
        
        return candidate

# === EVOLUTION ENGINE ===

class PromptEvolutionEngine:
    """Motor principal de evolução de prompts"""
    
    def __init__(self, population_size: int = POPULATION_SIZE):
        self.population_size = population_size
        self.evaluator = EvaluationEngine()
        self.mutator = PromptMutator()
        self.generation = 0
        self.population: List[PromptCandidate] = []
        self.history: List[List[PromptCandidate]] = []
        self.improvement_curve: List[float] = []
    
    def initialize_population(self, seed_prompt: str) -> None:
        """Cria população inicial a partir de seed"""
        self.population = []
        
        # Seed como primeiro candidato
        seed = PromptCandidate(
            id=f"gen0_seed",
            text=seed_prompt,
            generation=0,
            parent_id=None,
            mutations_applied=[]
        )
        self.population.append(seed)
        
        # Gera variações mutadas
        for i in range(self.population_size - 1):
            mutated, mutations = self.mutator.mutate(seed_prompt)
            candidate = PromptCandidate(
                id=f"gen0_{i+1}",
                text=mutated,
                generation=0,
                parent_id="seed",
                mutations_applied=mutations
            )
            self.population.append(candidate)
    
    def select_parent(self) -> PromptCandidate:
        """Seleciona parent via UCB1"""
        total_visits = sum(c.visits for c in self.population)
        
        # UCB1 scores
        ucb_scores = [
            (c, c.ucb1_score(total_visits)) for c in self.population
        ]
        
        # Seleciona melhor UCB1
        return max(ucb_scores, key=lambda x: x[1])[0]
    
    def evolve_generation(self, task_suite: List[Dict] = None) -> bool:
        """
        Evolui uma geração. Retorna True se convergiu.
        """
        self.generation += 1
        
        # Avalia população atual
        for candidate in self.population:
            if candidate.visits == 0:
                self.evaluator.evaluate_candidate(candidate, task_suite)
                candidate.visits = 1
                candidate.cumulative_reward = candidate.aggregate_score
        
        # Salva histórico
        self.history.append([
            PromptCandidate(
                id=c.id, text=c.text, generation=c.generation,
                ccs_score=c.ccs_score, parrot_score=c.parrot_score,
                task_score=c.task_score, visits=c.visits,
                cumulative_reward=c.cumulative_reward
            ) for c in self.population
        ])
        
        # Nova população
        new_population = []
        
        # Elitismo: mantém top 2
        sorted_pop = sorted(self.population, 
                           key=lambda c: c.aggregate_score, reverse=True)
        elite = sorted_pop[:2]
        new_population.extend([
            PromptCandidate(
                id=e.id, text=e.text, generation=self.generation,
                parent_id=e.parent_id, mutations_applied=e.mutations_applied[:],
                ccs_score=e.ccs_score, parrot_score=e.parrot_score,
                task_score=e.task_score
            ) for e in elite
        ])
        
        # Gera restante via mutação
        while len(new_population) < self.population_size:
            parent = self.select_parent()
            parent.visits += 1
            
            mutated, mutations = self.mutator.mutate(parent.text)
            child = PromptCandidate(
                id=f"gen{self.generation}_{len(new_population)}",
                text=mutated,
                generation=self.generation,
                parent_id=parent.id,
                mutations_applied=mutations
            )
            new_population.append(child)
        
        self.population = new_population
        
        # Registra melhor score
        best_score = max(c.aggregate_score for c in self.population)
        self.improvement_curve.append(best_score)
        
        # Verifica convergência
        if len(self.improvement_curve) > CONVERGENCE_PATIENCE:
            recent = self.improvement_curve[-CONVERGENCE_PATIENCE:]
            if max(recent) - min(recent) < CONVERGENCE_THRESHOLD:
                return True
        
        return False
    
    def evolve(self, seed_prompt: str, task_suite: List[Dict] = None,
               max_generations: int = MAX_ITERATIONS) -> EvolutionResult:
        """Executa evolução completa"""
        
        print(f"🧬 eve_prompt_evolver - Ciclo de Evolução #85")
        print(f"   Seed: {seed_prompt[:60]}...")
        print(f"   População: {self.population_size}")
        print(f"   Max Gerações: {max_generations}\n")
        
        self.initialize_population(seed_prompt)
        
        converged = False
        for gen in range(max_generations):
            converged = self.evolve_generation(task_suite)
            
            best = max(self.population, key=lambda c: c.aggregate_score)
            print(f"   Gen {gen+1}: Best={best.aggregate_score:.3f} "
                  f"(CCS={best.ccs_score:.2f}, PARROT={best.parrot_score:.2f}, "
                  f"TASK={best.task_score:.2f})")
            
            if converged:
                print(f"\n✅ Convergência atingida na geração {gen+1}")
                break
        
        # Resultado final
        best = max(self.population, key=lambda c: c.aggregate_score)
        
        return EvolutionResult(
            best_prompt=best,
            population_history=self.history,
            convergence_generation=self.generation if converged else max_generations,
            improvement_curve=self.improvement_curve
        )

# === CLI INTERFACE ===

def main():
    """Interface de linha de comando"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eve Prompt Evolver")
    parser.add_argument("--seed", "-s", required=True, help="Prompt seed inicial")
    parser.add_argument("--generations", "-g", type=int, default=20,
                       help="Número máximo de gerações")
    parser.add_argument("--population", "-p", type=int, default=POPULATION_SIZE,
                       help="Tamanho da população")
    parser.add_argument("--output", "-o", default="evolution_result.json",
                       help="Arquivo de saída")
    
    args = parser.parse_args()
    
    # Executa evolução
    engine = PromptEvolutionEngine(population_size=args.population)
    result = engine.evolve(args.seed, max_generations=args.generations)
    
    # Salva resultado
    output = {
        "best_prompt": {
            "text": result.best_prompt.text,
            "score": result.best_prompt.aggregate_score,
            "ccs": result.best_prompt.ccs_score,
            "parrot": result.best_prompt.parrot_score,
            "task": result.best_prompt.task_score,
            "generation": result.best_prompt.generation
        },
        "convergence_generation": result.convergence_generation,
        "improvement_curve": result.improvement_curve,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "ciclo": 85,
            "version": "1.0"
        }
    }
    
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Resultado salvo em: {args.output}")
    print(f"\n🏆 PROMPT ÓTIMO (Score: {result.best_prompt.aggregate_score:.3f}):")
    print("=" * 60)
    print(result.best_prompt.text)
    print("=" * 60)

if __name__ == "__main__":
    main()
