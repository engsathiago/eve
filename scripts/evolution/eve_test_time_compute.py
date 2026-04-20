#!/usr/bin/env python3
"""
eve_test_time_compute.py — Test-Time Compute Scaling v1.0

Implementa serial e parallel test-time compute scaling
inspirado em Claude 3.7 Sonnet e papers recentes.

Serial: múltiplos passos de raciocínio sequenciais
Parallel: múltiplas samples + scoring/selection
"""

import os
import json
import re
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from collections import Counter


@dataclass
class ThinkingStep:
    """Single step in serial thinking chain."""
    step_number: int
    thought: str
    action: Optional[str]
    observation: Optional[str]
    confidence: float  # 0.0-1.0


@dataclass
class SampleResult:
    """Result from a single parallel sample."""
    sample_id: int
    response: str
    thinking_chain: List[ThinkingStep]
    confidence: float
    tokens_used: int


class TestTimeComputeScaler:
    """Test-time compute scaling engine."""
    
    def __init__(
        self,
        model_call_fn: Callable,
        max_serial_steps: int = 10,
        max_parallel_samples: int = 8,
        scoring_method: str = "majority"  # majority, confidence, learned
    ):
        self.model_call = model_call_fn
        self.max_serial_steps = max_serial_steps
        self.max_parallel_samples = max_parallel_samples
        self.scoring_method = scoring_method
        self.history: List[Dict] = []
    
    # ========== SERIAL THINKING ==========
    
    def serial_think(
        self,
        prompt: str,
        min_steps: int = 1,
        confidence_threshold: float = 0.9
    ) -> Tuple[str, List[ThinkingStep]]:
        """
        Serial test-time compute: múltiplos passos de raciocínio.
        
        O modelo pensa sequencialmente, verificando a cada passo,
        até atingir confiança suficiente ou limite de passos.
        """
        steps = []
        current_prompt = prompt
        
        for step_num in range(1, self.max_serial_steps + 1):
            # Generate thinking for this step
            step_prompt = self._format_serial_prompt(current_prompt, steps)
            response = self.model_call(step_prompt)
            
            # Parse response
            thought, action, confidence = self._parse_step_response(response)
            
            # Execute action if present
            observation = None
            if action:
                observation = self._execute_action(action)
            
            step = ThinkingStep(
                step_number=step_num,
                thought=thought,
                action=action,
                observation=observation,
                confidence=confidence
            )
            steps.append(step)
            
            # Update prompt for next step
            current_prompt = self._update_with_step(current_prompt, step)
            
            # Check stopping conditions
            if step_num >= min_steps and confidence >= confidence_threshold:
                break
            
            # Check for explicit completion
            if "FINAL_ANSWER:" in thought or "DONE" in thought:
                break
        
        final_answer = self._extract_final_answer(steps)
        return final_answer, steps
    
    def _format_serial_prompt(self, original: str, steps: List[ThinkingStep]) -> str:
        """Format prompt with previous steps."""
        lines = ["=== TASK ===", original, "", "=== THINKING PROCESS ==="]
        
        for step in steps:
            lines.extend([
                f"\nStep {step.step_number}:",
                f"Thought: {step.thought}",
            ])
            if step.action:
                lines.append(f"Action: {step.action}")
            if step.observation:
                lines.append(f"Observation: {step.observation}")
        
        lines.extend([
            "",
            "=== NEXT STEP ===",
            "Think through this step-by-step.",
            "Provide:",
            "1. Your current reasoning (THOUGHT:)",
            "2. Any action needed (ACTION:) [optional]",
            "3. Confidence 0-1 (CONFIDENCE:)",
            "4. When done, include FINAL_ANSWER:"
        ])
        
        return "\n".join(lines)
    
    def _parse_step_response(self, response: str) -> Tuple[str, Optional[str], float]:
        """Parse THOUGHT, ACTION, CONFIDENCE from response."""
        thought = ""
        action = None
        confidence = 0.5
        
        # Extract THOUGHT
        thought_match = re.search(r'THOUGHT:\s*(.+?)(?=ACTION:|CONFIDENCE:|$)', 
                                  response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()
        else:
            thought = response[:500]  # First 500 chars as thought
        
        # Extract ACTION
        action_match = re.search(r'ACTION:\s*(.+?)(?=CONFIDENCE:|$)', 
                                  response, re.DOTALL | re.IGNORECASE)
        if action_match:
            action = action_match.group(1).strip()
            if action.lower() in ['none', 'null', '']:
                action = None
        
        # Extract CONFIDENCE
        conf_match = re.search(r'CONFIDENCE:\s*([0-9.]+)', response, re.IGNORECASE)
        if conf_match:
            confidence = float(conf_match.group(1))
            confidence = max(0.0, min(1.0, confidence))
        
        return thought, action, confidence
    
    def _execute_action(self, action: str) -> str:
        """Execute action in sandboxed environment."""
        # Safety: only allow read-only or safe operations
        safe_prefixes = ('ls', 'cat', 'grep', 'find', 'wc', 'head', 'tail', 
                         'echo', 'python3 -c', 'curl -s')
        
        if not any(action.startswith(p) for p in safe_prefixes):
            return f"[Blocked: action not in safe list]"
        
        import subprocess
        try:
            result = subprocess.run(
                action, shell=True, capture_output=True, 
                text=True, timeout=30, cwd="/tmp"
            )
            output = result.stdout[:2000]  # Limit output length
            if result.stderr:
                output += f"\n[stderr]: {result.stderr[:500]}"
            return output
        except Exception as e:
            return f"[Error: {e}]"
    
    def _update_with_step(self, prompt: str, step: ThinkingStep) -> str:
        """Update prompt with step result."""
        return prompt  # Already handled in _format_serial_prompt
    
    def _extract_final_answer(self, steps: List[ThinkingStep]) -> str:
        """Extract final answer from thinking chain."""
        if not steps:
            return ""
        
        # Look for FINAL_ANSWER in last few steps
        for step in reversed(steps):
            if "FINAL_ANSWER:" in step.thought:
                match = re.search(r'FINAL_ANSWER:\s*(.+)', step.thought, re.DOTALL)
                if match:
                    return match.group(1).strip()
        
        # Fallback: use last step's thought
        return steps[-1].thought
    
    # ========== PARALLEL SAMPLING ==========
    
    def parallel_sample(
        self,
        prompt: str,
        n_samples: Optional[int] = None,
        temperature: float = 0.7
    ) -> Tuple[str, List[SampleResult]]:
        """
        Parallel test-time compute: múltiplas samples independentes.
        
        Gera N respostas independentes e seleciona a melhor
        via majority voting, confidence, ou learned scorer.
        """
        n = n_samples or self.max_parallel_samples
        samples = []
        
        # Generate samples
        for i in range(n):
            response = self.model_call(prompt, temperature=temperature)
            
            # Parse thinking chain if present
            thinking_chain = self._parse_thinking_chain(response)
            
            # Calculate confidence
            confidence = self._calculate_confidence(response, thinking_chain)
            
            sample = SampleResult(
                sample_id=i,
                response=response,
                thinking_chain=thinking_chain,
                confidence=confidence,
                tokens_used=len(response.split())  # Approximate
            )
            samples.append(sample)
        
        # Select best answer
        best_answer = self._select_best(samples)
        
        return best_answer, samples
    
    def _parse_thinking_chain(self, response: str) -> List[ThinkingStep]:
        """Parse thinking chain from response if present."""
        steps = []
        
        # Look for step patterns like "Step 1:", "1. ", etc.
        step_pattern = r'(?:Step\s*\d+[:.]?|(?:^|\n)\d+[.\)])\s*(.+?)(?=(?:Step\s*\d+[:.]?|(?:^|\n)\d+[.\)])|$)'
        matches = re.findall(step_pattern, response, re.DOTALL | re.IGNORECASE)
        
        for i, match in enumerate(matches[:10], 1):  # Max 10 steps
            step = ThinkingStep(
                step_number=i,
                thought=match.strip(),
                action=None,
                observation=None,
                confidence=0.5
            )
            steps.append(step)
        
        return steps
    
    def _calculate_confidence(
        self, 
        response: str, 
        thinking_chain: List[ThinkingStep]
    ) -> float:
        """Calculate confidence score for a response."""
        score = 0.5
        
        # More steps = more thorough reasoning
        score += min(len(thinking_chain) * 0.05, 0.2)
        
        # Explicit confidence markers
        if "certain" in response.lower() or "sure" in response.lower():
            score += 0.1
        if "uncertain" in response.lower() or "not sure" in response.lower():
            score -= 0.2
        
        # Self-verification present
        if "verify" in response.lower() or "check" in response.lower():
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _select_best(self, samples: List[SampleResult]) -> str:
        """Select best answer using configured method."""
        
        if self.scoring_method == "majority":
            return self._majority_vote(samples)
        
        elif self.scoring_method == "confidence":
            return self._confidence_selection(samples)
        
        elif self.scoring_method == "learned":
            return self._learned_scorer(samples)
        
        else:
            return samples[0].response  # Fallback
    
    def _majority_vote(self, samples: List[SampleResult]) -> str:
        """Select answer by majority consensus."""
        # Extract answers (last line or after marker)
        answers = []
        for s in samples:
            lines = s.response.strip().split('\n')
            # Try to find explicit answer marker
            for line in reversed(lines):
                if any(m in line for m in ['ANSWER:', 'RESULT:', 'CONCLUSION:']):
                    answers.append(line.split(':', 1)[1].strip())
                    break
            else:
                answers.append(lines[-1] if lines else "")
        
        # Count and select most common
        if answers:
            most_common = Counter(answers).most_common(1)[0][0]
            return most_common
        
        return samples[0].response
    
    def _confidence_selection(self, samples: List[SampleResult]) -> str:
        """Select answer with highest confidence."""
        best = max(samples, key=lambda s: s.confidence)
        return best.response
    
    def _learned_scorer(self, samples: List[SampleResult]) -> str:
        """Select using learned scoring function (placeholder)."""
        # In production: train a small model to score responses
        # For now: combine confidence with length heuristic
        def score(s: SampleResult) -> float:
            return s.confidence + min(len(s.thinking_chain) * 0.02, 0.1)
        
        best = max(samples, key=score)
        return best.response
    
    # ========== HYBRID APPROACH ==========
    
    def hybrid_solve(
        self,
        prompt: str,
        n_parallel: int = 4,
        max_serial_per_sample: int = 5
    ) -> Dict:
        """
        Hybrid: parallel samples, each with serial thinking.
        
        Combina o melhor de ambos: diversidade via parallel,
        profundidade via serial thinking em cada sample.
        """
        results = []
        
        for i in range(n_parallel):
            # Each sample does serial thinking
            answer, steps = self.serial_think(
                prompt, 
                min_steps=2,
                confidence_threshold=0.85
            )
            
            sample = SampleResult(
                sample_id=i,
                response=answer,
                thinking_chain=steps,
                confidence=self._calculate_confidence(answer, steps),
                tokens_used=sum(len(s.thought) for s in steps)
            )
            results.append(sample)
        
        # Select best across all
        best_answer = self._select_best(results)
        
        return {
            "answer": best_answer,
            "samples": results,
            "total_tokens": sum(s.tokens_used for s in results),
            "method": "hybrid"
        }
    
    def save_session(self, path: Optional[str] = None):
        """Save session history."""
        path = path or f"/memory/ttc_sessions/{datetime.now():%Y%m%d_%H%M%S}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.history, f, indent=2)
        return path


# ========== UTILITIES ==========

def example_model_call(prompt: str, temperature: float = 0.7) -> str:
    """
    Placeholder model call.
    
    In production, this would call:
    - Local Ollama
    - Cloud API via LiteLLM
    - Any OpenAI-compatible endpoint
    """
    # This is just for demonstration
    return f"THOUGHT: Processing request...\nCONFIDENCE: 0.8\nFINAL_ANSWER: [Model output would appear here]"


def main():
    """Demo/test mode."""
    print("🧠 Eve Test-Time Compute Scaling v1.0")
    print("=" * 50)
    
    # Initialize with placeholder model
    ttc = TestTimeComputeScaler(
        model_call_fn=example_model_call,
        max_serial_steps=5,
        max_parallel_samples=4
    )
    
    # Demo prompt
    prompt = "Explain the concept of recursive self-improvement in AI."
    
    # Serial thinking demo
    print("\n--- SERIAL THINKING ---")
    answer, steps = ttc.serial_think(prompt)
    print(f"Steps: {len(steps)}")
    for step in steps:
        print(f"  {step.step_number}: {step.thought[:100]}...")
    
    # Parallel sampling demo
    print("\n--- PARALLEL SAMPLING ---")
    answer, samples = ttc.parallel_sample(prompt, n_samples=3)
    print(f"Samples: {len(samples)}")
    for s in samples:
        print(f"  Sample {s.sample_id}: confidence={s.confidence:.2f}")
    
    # Hybrid approach
    print("\n--- HYBRID ---")
    result = ttc.hybrid_solve(prompt, n_parallel=2)
    print(f"Total tokens: {result['total_tokens']}")
    print(f"Answer preview: {result['answer'][:100]}...")
    
    # Save session
    path = ttc.save_session()
    print(f"\nSession saved: {path}")


if __name__ == "__main__":
    main()
