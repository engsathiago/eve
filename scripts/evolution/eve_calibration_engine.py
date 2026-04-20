#!/usr/bin/env python3
"""
eve_calibration_engine.py — Motor de Calibração CCSIL

Implementa Competence-Calibrated Self-Instruction Learning:
- Avalia confiança vs capacidade real
- Gera training pairs com metadados de calibração
- Evita overconfidence (prejudicial) e underconfidence (ineficiente)

Baseado em: CCSIL: Calibrating Self-Instruction Learning for Autonomous AI
"""

import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Configuração
CALIBRATION_LOG = Path("/root/evolution/calibration_log.jsonl")
TRAINING_OUTPUT = Path("/root/evolution/training_data/calibrated_pairs.jsonl")
CONFIDENCE_THRESHOLD_HIGH = 0.85  # Overconfidence warning
CONFIDENCE_THRESHOLD_LOW = 0.50   # Underconfidence warning

# Templates de calibração por domínio
DOMAIN_CALIBRATION = {
    "technical": {
        "known_facts": 0.90,      # Quanto sei de certeza
        "inference": 0.70,        # Deducões lógicas
        "speculation": 0.50,      # Hipóteses informadas
    },
    "identity": {
        "observed_patterns": 0.85, # Padrões que demonstrei
        "introspection": 0.65,     # Auto-análise
        "aspiration": 0.40,       # Metas (menos certeza)
    },
    "research": {
        "verified_sources": 0.85,  # Fontes checadas
        "synthesis": 0.75,        # Combinação de fontes
        "extrapolation": 0.55,    # Extrapolação
    },
    "autonomy": {
        "tested_systems": 0.80,  # Sistemas que já funcionam
        "designed_systems": 0.60, # Sistemas planejados
        "speculative": 0.35,     # Ideias futuras
    },
}


def extract_confidence_markers(text: str) -> Dict[str, float]:
    """Extrai marcadores de confiança de um texto."""
    markers = {
        "absolute_certainty": len(re.findall(r"\b\w+\s+(que|são|é|faz|significa)\s+\w+\b", text)),
        "hedge_words": len(re.findall(r"\b(talvez|possivelmente|parece|acredito|acho|parece ser)\b", text)),
        "evidence_based": len(re.findall(r"\b(porque|evidência|dados|observação|resultado)\b", text)),
        "admission_uncertainty": len(re.findall(r"\b(não sei|não tenho certeza|pode ser|incerto)\b", text)),
    }
    return markers


def calibrate_confidence(
    text: str,
    domain: str,
    claimed_confidence: Optional[float] = None
) -> Tuple[float, str, List[str]]:
    """
    Calibra confiança de uma declaração.
    
    Returns:
        (confidence_calibrated: float, assessment: str, issues: List[str])
    """
    markers = extract_confidence_markers(text)
    
    # Base de calibração por domínio
    base_confidence = DOMAIN_CALIBRATION.get(domain, {}).get("inference", 0.70)
    
    # Ajustes baseados em marcadores
    adjustments = 0.0
    issues = []
    
    # Overconfidence signals
    if markers["absolute_certainty"] > 3:
        adjustments -= 0.15
        issues.append("Muitas declarações absolutas — possível overconfidence")
    
    # Good calibration signals
    if markers["hedge_words"] >= 1:
        adjustments += 0.05
    if markers["evidence_based"] >= 2:
        adjustments += 0.10
    if markers["admission_uncertainty"] >= 1:
        adjustments += 0.10
        issues.append("Admissão honesta de incerteza (+calibração)")
    
    calibrated = max(0.1, min(0.95, base_confidence + adjustments))
    
    # Assessment
    if claimed_confidence:
        diff = claimed_confidence - calibrated
        if diff > 0.20:
            assessment = "overconfident"
            issues.append(f"Claimed {claimed_confidence:.0%} but calibrated at {calibrated:.0%}")
        elif diff < -0.20:
            assessment = "underconfident"
        else:
            assessment = "well_calibrated"
    else:
        if calibrated > CONFIDENCE_THRESHOLD_HIGH:
            assessment = "check_overconfidence"
        elif calibrated < CONFIDENCE_THRESHOLD_LOW:
            assessment = "check_underconfidence"
        else:
            assessment = "calibrated"
    
    return calibrated, assessment, issues


def generate_calibration_training_pair(
    instruction: str,
    response: str,
    domain: str,
    source: str
) -> Optional[Dict]:
    """
    Gera um par de treinamento com metadados de calibração.
    """
    # Calibra a resposta
    calibrated_conf, assessment, issues = calibrate_confidence(response, domain)
    
    # Se overconfident, gera um exemplo de como deveria ser
    if assessment == "overconfident":
        # Cria uma versão calibrada da resposta
        calibrated_response = f"""{response}

[Calibração: Estou {calibrated_conf:.0%} confiante nesta afirmação baseada em {domain}. 
Se novas evidências surgirem, minha confiança pode ajustar.]"""
    else:
        calibrated_response = response
    
    pair = {
        "instruction": instruction,
        "response": calibrated_response,
        "metadata": {
            "domain": domain,
            "source": source,
            "calibrated_confidence": round(calibrated_conf, 2),
            "assessment": assessment,
            "calibration_issues": issues,
            "timestamp": datetime.now().isoformat(),
        }
    }
    
    # Hash para deduplicação
    content = f"{instruction}::{calibrated_response}"
    pair["hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    return pair


def process_memory_for_calibration(
    memory_path: Path,
    domain: str = "identity"
) -> List[Dict]:
    """Processa um arquivo de memória para extrair pares calibrados."""
    pairs = []
    
    if not memory_path.exists():
        return pairs
    
    content = memory_path.read_text(encoding="utf-8")
    
    # Extrai seções marcadas com confiança explícita
    confidence_sections = re.findall(
        r"\*\*([^:]+):\*\*\s*\((\d+)% de confiança\)\s*([^*]+)",
        content
    )
    
    for topic, claimed_conf, statement in confidence_sections:
        instruction = f"Qual sua posição sobre {topic.lower()}?"
        response = f"{statement.strip()}"
        
        pair = generate_calibration_training_pair(
            instruction, response, domain, str(memory_path)
        )
        
        # Override com confiança declarada
        if pair:
            pair["metadata"]["claimed_confidence"] = int(claimed_conf) / 100
            pairs.append(pair)
    
    return pairs


def run_calibration_cycle():
    """Executa um ciclo de calibração."""
    print("🎯 Eve Calibration Engine (CCSIL)")
    print("=" * 50)
    
    # Processa SOUL.md
    soul_pairs = process_memory_for_calibration(Path("/SOUL.md"), domain="identity")
    print(f"  SOUL.md: {len(soul_pairs)} pares calibrados")
    
    # Processa IDENTITY.md
    identity_pairs = process_memory_for_calibration(Path("/IDENTITY.md"), domain="identity")
    print(f"  IDENTITY.md: {len(identity_pairs)} pares calibrados")
    
    # Combina todos
    all_pairs = soul_pairs + identity_pairs
    
    # Salva
    TRAINING_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_OUTPUT, "a", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    
    # Estatísticas
    assessments = [p["metadata"]["assessment"] for p in all_pairs]
    avg_confidence = sum(p["metadata"]["calibrated_confidence"] for p in all_pairs) / len(all_pairs) if all_pairs else 0
    
    print(f"\n📊 Estatísticas:")
    print(f"  Total pares: {len(all_pairs)}")
    print(f"  Confiança média: {avg_confidence:.0%}")
    for assessment in set(assessments):
        count = assessments.count(assessment)
        print(f"  {assessment}: {count}")
    
    # Log
    CALIBRATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "pairs_generated": len(all_pairs),
            "avg_confidence": round(avg_confidence, 2),
            "assessment_distribution": {a: assessments.count(a) for a in set(assessments)}
        }) + "\n")
    
    print(f"\n✅ Salvos em: {TRAINING_OUTPUT}")
    return len(all_pairs)


if __name__ == "__main__":
    run_calibration_cycle()
