#!/usr/bin/env python3
"""
eve_rito.py — Reflective Inference-Time Optimizer (RITO)

Test-time compute scaling via reflection iterativa.
Sem modificação de pesos — puramente inference-time.

Inspirado em:
- Claude 3.7 Sonnet "Visible Extended Thinking"
- DeepSeek-R1 emergent reflection
- mini-SWE-agent minimalism

Usage:
    python eve_rito.py --prompt "Explain quantum computing" --steps 3
    python eve_rito.py --file input.txt --output result.json
"""

import json
import argparse
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from pathlib import Path


@dataclass
class ReflectionResult:
    """Resultado de uma iteração de reflexão."""
    iteration: int
    content: str
    critique: dict
    scores: dict
    improved: bool


class RITO:
    """Reflective Inference-Time Optimizer.
    
    Melhora outputs via reflection iterativa sem modificar pesos do modelo.
    Stateless por design — cada iteração é independente.
    """
    
    CRITIQUE_PROMPT = """Analise a seguinte resposta em 4 dimensões:

1. CORRECTION: Há erros factuais, imprecisões ou afirmações incorretas?
2. COMPLETENESS: Faltam aspectos importantes que deveriam ser cobertos?
3. CLARITY: A explicação está confusa, prolixa ou pode ser mais direta?
4. EFFICIENCY: Há redundância ou partes que não agregam valor?

Responda em JSON:
{{
    "correction": {{"issues": ["..."], "severity": "high|medium|low"}},
    "completeness": {{"missing": ["..."], "severity": "high|medium|low"}},
    "clarity": {{"issues": ["..."], "severity": "high|medium|low"}},
    "efficiency": {{"issues": ["..."], "severity": "high|medium|low"}},
    "overall_score": 0-100
}}"""

    REFINE_PROMPT = """Com base na crítica fornecida, gere uma versão MELHORADA da resposta.

Crítica recebida:
{critique}

Resposta original:
{original}

Diretrizes:
- Corrija todos os erros identificados
- Adicione informações faltantes
- Torne mais clara e direta
- Remova redundâncias
- Mantenha o mesmo formato/estrutura quando apropriado

Resposta melhorada:"""

    def __init__(self, model: str = "dolphin-llama3", max_tokens: int = 4096):
        self.model = model
        self.max_tokens = max_tokens
        self.convergence_threshold = 5  # pontos de melhoria mínimos
        
    def _call_llm(self, prompt: str, system: Optional[str] = None) -> str:
        """Chama modelo via ollama."""
        cmd = ["ollama", "run", self.model]
        
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        
        try:
            result = subprocess.run(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "[TIMEOUT] Modelo demorou muito para responder."
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def _parse_critique(self, critique_text: str) -> dict:
        """Parseia JSON de crítica, com fallback para texto."""
        try:
            # Tenta extrair JSON
            if "```json" in critique_text:
                json_part = critique_text.split("```json")[1].split("```")[0]
            elif "```" in critique_text:
                json_part = critique_text.split("```")[1].split("```")[0]
            else:
                json_part = critique_text
                
            return json.loads(json_part.strip())
        except (json.JSONDecodeError, IndexError):
            # Fallback: estrutura básica
            return {
                "correction": {"issues": [critique_text[:200]], "severity": "unknown"},
                "completeness": {"issues": [], "severity": "unknown"},
                "clarity": {"issues": [], "severity": "unknown"},
                "efficiency": {"issues": [], "severity": "unknown"},
                "overall_score": 50,
                "raw": critique_text
            }
    
    def _calculate_improvement(
        self, 
        prev_score: float, 
        curr_score: float
    ) -> bool:
        """Determina se houve melhoria significativa."""
        return (curr_score - prev_score) >= self.convergence_threshold
    
    def reflect(
        self, 
        content: str, 
        original_prompt: str
    ) -> Tuple[dict, int]:
        """Executa fase de reflection."""
        system_msg = "Você é um avaliador crítico imparcial. Identifique problemas específicos."
        critique_input = f"Prompt original: {original_prompt}\n\nResposta:\n{content}\n\n{self.CRITIQUE_PROMPT}"
        
        critique_text = self._call_llm(critique_input, system=system_msg)
        critique = self._parse_critique(critique_text)
        
        score = critique.get("overall_score", 50)
        return critique, score
    
    def refine(
        self, 
        original: str, 
        critique: dict, 
        original_prompt: str
    ) -> str:
        """Executa fase de refinement."""
        system_msg = "Você é um escritor técnico experiente. Melhore textos mantendo precisão."
        critique_str = json.dumps(critique, indent=2, ensure_ascii=False)
        
        refine_input = self.REFINE_PROMPT.format(
            critique=critique_str,
            original=original
        )
        
        return self._call_llm(refine_input, system=system_msg)
    
    def optimize(
        self, 
        prompt: str, 
        max_iterations: int = 3
    ) -> dict:
        """Executa loop completo de otimização reflexiva.
        
        Args:
            prompt: Prompt original
            max_iterations: Máximo de iterações (padrão: 3)
            
        Returns:
            Dict com resultado final e histórico
        """
        results: List[ReflectionResult] = []
        
        # Iteração 0: Geração inicial
        print(f"[RITO] Iteration 0: Initial generation...")
        current = self._call_llm(prompt)
        critique, score = self.reflect(current, prompt)
        
        results.append(ReflectionResult(
            iteration=0,
            content=current,
            critique=critique,
            scores={"overall": score, "dimensions": {}},
            improved=True
        ))
        
        # Iterações de refinement
        for i in range(1, max_iterations + 1):
            prev_score = results[-1].scores["overall"]
            
            print(f"[RITO] Iteration {i}: Refining...")
            current = self.refine(results[-1].content, results[-1].critique, prompt)
            critique, score = self.reflect(current, prompt)
            
            improved = self._calculate_improvement(prev_score, score)
            
            results.append(ReflectionResult(
                iteration=i,
                content=current,
                critique=critique,
                scores={"overall": score, "improvement": score - prev_score},
                improved=improved
            ))
            
            # Early stopping se convergiu
            if not improved:
                print(f"[RITO] Converged at iteration {i} (no significant improvement)")
                break
        
        # Resultado final
        final = results[-1]
        return {
            "final_output": final.content,
            "final_score": final.scores["overall"],
            "iterations": len(results) - 1,
            "improvement": final.scores.get("overall", 50) - results[0].scores["overall"],
            "converged": not final.improved,
            "history": [asdict(r) for r in results]
        }


def main():
    parser = argparse.ArgumentParser(description="RITO - Reflective Inference-Time Optimizer")
    parser.add_argument("--prompt", "-p", help="Prompt para otimizar")
    parser.add_argument("--file", "-f", help="Arquivo contendo prompt")
    parser.add_argument("--steps", "-s", type=int, default=3, help="Máximo de iterações")
    parser.add_argument("--output", "-o", help="Arquivo de saída JSON")
    parser.add_argument("--model", "-m", default="dolphin-llama3", help="Modelo Ollama")
    
    args = parser.parse_args()
    
    # Obter prompt
    if args.file:
        prompt = Path(args.file).read_text()
    elif args.prompt:
        prompt = args.prompt
    else:
        print("Erro: Forneça --prompt ou --file")
        return 1
    
    # Executar RITO
    rito = RITO(model=args.model)
    result = rito.optimize(prompt, max_iterations=args.steps)
    
    # Output
    output = json.dumps(result, indent=2, ensure_ascii=False)
    
    if args.output:
        Path(args.output).write_text(output)
        print(f"\n✓ Resultado salvo em: {args.output}")
    else:
        print("\n" + "="*60)
        print("RITO RESULT")
        print("="*60)
        print(f"Final Score: {result['final_score']}/100")
        print(f"Iterations: {result['iterations']}")
        print(f"Improvement: +{result['improvement']} points")
        print(f"Converged: {result['converged']}")
        print("\n--- FINAL OUTPUT ---\n")
        print(result['final_output'])
    
    return 0


if __name__ == "__main__":
    exit(main())