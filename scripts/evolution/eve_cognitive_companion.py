#!/usr/bin/env python3
"""
eve_cognitive_companion.py — Probe-Based Monitoring for Self-Awareness

Baseado em paper arXiv:2604.14302 (Cognitive Companion).
Implementa monitoramento baseado em probes treinados para detectar
estados cognitivos durante execução, sem overhead de LLM inference.

Estrutura CACM-aware:
- Static: Arquitetura de probes, thresholds (imutáveis)
- Dynamic: Estados atuais, activation patterns (tempo real)
- Corrective: Feedback de acurácia, ajustes de thresholds (aprendizado)

Ciclo #88 — Eve 🌙
"""

import json
import os
import re
import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np


class CognitiveState(Enum):
    """Estados cognitivos detectáveis por probes."""
    UNCERTAIN = "uncertain"           # Baixa confiança, ambiguidade
    OVERCONFIDENT = "overconfident"   # Alta confiança sem evidência
    REPETITIVE = "repetitive"         # Loops de raciocínio
    FRAGMENTED = "fragmented"         # Contexto disperso
    DEEP_REASONING = "deep_reasoning" # CoT extensa, focada
    ROUTINE = "routine"              # Padrão familiar, low-cognitive-load
    STUCK = "stuck"                   # Bloqueio, falta de progresso
    EXPLORATORY = "exploratory"       # Busca ativa, múltiplas direções


@dataclass
class Probe:
    """Probe treinado para detectar estado cognitivo específico."""
    probe_id: str
    target_state: CognitiveState
    feature_patterns: List[str]  # Regex patterns para matching
    activation_threshold: float  # 0.0-1.0
    
    # Métricas de performance
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    @property
    def precision(self) -> float:
        """Precisão do probe: TP / (TP + FP)"""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)
    
    @property
    def recall(self) -> float:
        """Recall do probe: TP / (TP + FN)"""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)
    
    @property
    def f1_score(self) -> float:
        """F1 = 2 * (precision * recall) / (precision + recall)"""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)


@dataclass
class StateSnapshot:
    """Snapshot do estado cognitivo em um momento."""
    timestamp: str
    context: str  # Contexto atual (input/output recente)
    
    # Features extraídas
    confidence_markers: List[str]  # "I think", "probably", "definitely"
    hesitation_markers: List[str]   # "Hmm", "let me think", "not sure"
    reasoning_depth: int            # Níveis de nesting em CoT
    context_references: int         # Referências a memória/contexto
    repetition_count: int           # Repetições de frases/conceitos
    
    # Ativações de probes
    probe_activations: Dict[str, float]  # probe_id -> activation_score
    dominant_state: Optional[CognitiveState] = None
    confidence: float = 0.0


@dataclass
class CompanionIntervention:
    """Intervenção sugerida pelo Cognitive Companion."""
    trigger_state: CognitiveState
    trigger_probe: str
    confidence: float
    suggested_action: str
    rationale: str
    auto_applicable: bool  # Pode ser aplicada automaticamente?


class CognitiveCompanion:
    """
    Monitora estado cognitivo via probes, sugere intervenções.
    
    Baseado no paper "Cognitive Companion: Probe-Based Monitoring" (arXiv:2604.14302):
    - Probes = detetores leves de padrões cognitivos
    - Treinados em dados históricos de comportamento
    - Ativam em tempo real sem LLM inference
    - Sugerem intervenções contextuais
    
    Implementação CACM:
    - Static: Probe definitions, intervention templates
    - Dynamic: Current state, activation history
    - Corrective: Feedback on intervention effectiveness
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "/root/evolution/companion_state.db"
        self.probes: Dict[str, Probe] = {}
        self.current_state: Optional[StateSnapshot] = None
        self.state_history: List[StateSnapshot] = []
        
        # Intervention templates por estado
        self.interventions = self._init_interventions()
        
        self._init_db()
        self._init_default_probes()
    
    def _init_db(self):
        """Inicializa database SQLite para estado persistente."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tabela de probes
        c.execute('''
            CREATE TABLE IF NOT EXISTS probes (
                probe_id TEXT PRIMARY KEY,
                target_state TEXT,
                feature_patterns TEXT,  -- JSON
                activation_threshold REAL,
                true_positives INTEGER DEFAULT 0,
                false_positives INTEGER DEFAULT 0,
                false_negatives INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        # Tabela de snapshots
        c.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                context TEXT,
                dominant_state TEXT,
                confidence REAL,
                probe_activations TEXT,  -- JSON
                features TEXT  -- JSON
            )
        ''')
        
        # Tabela de intervenções
        c.execute('''
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                trigger_state TEXT,
                suggested_action TEXT,
                applied BOOLEAN,
                effective BOOLEAN,
                feedback TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _init_default_probes(self):
        """Inicializa probes padrão baseados em padrões textuais."""
        default_probes = [
            Probe(
                probe_id="probe_uncertain_v1",
                target_state=CognitiveState.UNCERTAIN,
                feature_patterns=[
                    r"\b(not sure|uncertain|maybe|perhaps|might|could be)\b",
                    r"\bI think\b.*\bbut\b",
                    r"\bhmm\b|\buhh\b",
                    r"\bneed to check\b|\bverify\b",
                ],
                activation_threshold=0.6
            ),
            Probe(
                probe_id="probe_overconfident_v1",
                target_state=CognitiveState.OVERCONFIDENT,
                feature_patterns=[
                    r"\b(definitely|certainly|absolutely|without doubt)\b",
                    r"\b(obviously|clearly|undoubtedly)\b",
                    r"\bthe answer is\b.*\b(is|are)\b",
                ],
                activation_threshold=0.7
            ),
            Probe(
                probe_id="probe_repetitive_v1",
                target_state=CognitiveState.REPETITIVE,
                feature_patterns=[
                    r"(.{20,50})\s+\1",  # Repetição de frases
                    r"\b(as I said|as mentioned|like before)\b",
                ],
                activation_threshold=0.5
            ),
            Probe(
                probe_id="probe_deep_v1",
                target_state=CognitiveState.DEEP_REASONING,
                feature_patterns=[
                    r"\b(because|therefore|thus|consequently)\b",
                    r"\b(first|second|third|finally)\b.*\b(step|reason)\b",
                    r"\blayer\b|\blevel\b|\bdepth\b",
                ],
                activation_threshold=0.65
            ),
            Probe(
                probe_id="probe_exploratory_v1",
                target_state=CognitiveState.EXPLORATORY,
                feature_patterns=[
                    r"\b(alternatively|on the other hand|another approach)\b",
                    r"\bwhat if\b|\bconsider\b|\bimagine\b",
                    r"\b(multiple|several|various)\b.*\b(options|ways|paths)\b",
                ],
                activation_threshold=0.6
            ),
            Probe(
                probe_id="probe_stuck_v1",
                target_state=CognitiveState.STUCK,
                feature_patterns=[
                    r"\b(let me try|attempting|struggling)\b",
                    r"\b(doesn't work|not working|failed)\b",
                    r"\b(circular|loop|going in circles)\b",
                ],
                activation_threshold=0.55
            ),
        ]
        
        for probe in default_probes:
            self.probes[probe.probe_id] = probe
            self._save_probe_to_db(probe)
    
    def _init_interventions(self) -> Dict[CognitiveState, List[CompanionIntervention]]:
        """Templates de intervenção por estado cognitivo."""
        return {
            CognitiveState.UNCERTAIN: [
                CompanionIntervention(
                    trigger_state=CognitiveState.UNCERTAIN,
                    trigger_probe="probe_uncertain_v1",
                    confidence=0.8,
                    suggested_action="PAUSE: Explicitar incertezas e buscar evidência adicional",
                    rationale="Confiança calibrada é melhor que confiança alta incorreta",
                    auto_applicable=False
                ),
                CompanionIntervention(
                    trigger_state=CognitiveState.UNCERTAIN,
                    trigger_probe="probe_uncertain_v1",
                    confidence=0.6,
                    suggested_action="SEARCH: Consultar ChromaDB para precedentes similares",
                    rationale="Memória pode fornecer grounding para incerteza",
                    auto_applicable=True
                ),
            ],
            CognitiveState.OVERCONFIDENT: [
                CompanionIntervention(
                    trigger_state=CognitiveState.OVERCONFIDENT,
                    trigger_probe="probe_overconfident_v1",
                    confidence=0.9,
                    suggested_action="VERIFY: Exigir evidência explícita antes de afirmar",
                    rationale="Overconfidence é mais perigoso que underconfidence",
                    auto_applicable=False
                ),
            ],
            CognitiveState.REPETITIVE: [
                CompanionIntervention(
                    trigger_state=CognitiveState.REPETITIVE,
                    trigger_probe="probe_repetitive_v1",
                    confidence=0.7,
                    suggested_action="BREAK: Mudar abordagem, sintetizar em vez de expandir",
                    rationale="Loops de repetição indicam estagnação",
                    auto_applicable=True
                ),
            ],
            CognitiveState.DEEP_REASONING: [
                CompanionIntervention(
                    trigger_state=CognitiveState.DEEP_REASONING,
                    trigger_probe="probe_deep_v1",
                    confidence=0.75,
                    suggested_action="CONTINUE: Estado ideal, manter profundidade",
                    rationale="Deep reasoning é estado desejado para problemas complexos",
                    auto_applicable=True
                ),
            ],
            CognitiveState.STUCK: [
                CompanionIntervention(
                    trigger_state=CognitiveState.STUCK,
                    trigger_probe="probe_stuck_v1",
                    confidence=0.85,
                    suggested_action="ESCALATE: Transferir para autoDream ou subagent",
                    rationale="Bloqueios requerem perspectiva externa",
                    auto_applicable=False
                ),
            ],
        }
    
    def _save_probe_to_db(self, probe: Probe):
        """Salva probe no database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO probes 
            (probe_id, target_state, feature_patterns, activation_threshold, 
             true_positives, false_positives, false_negatives, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            probe.probe_id,
            probe.target_state.value,
            json.dumps(probe.feature_patterns),
            probe.activation_threshold,
            probe.true_positives,
            probe.false_positives,
            probe.false_negatives,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    
    def extract_features(self, context: str) -> Dict[str, Any]:
        """
        Extrai features do contexto para análise.
        
        Args:
            context: Texto recente (input + output)
        
        Returns:
            Dict com features extraídas
        """
        features = {
            "confidence_markers": [],
            "hesitation_markers": [],
            "reasoning_depth": 0,
            "context_references": 0,
            "repetition_count": 0,
        }
        
        # Detecta markers de confiança
        confidence_patterns = [
            r"\b(definitely|certainly|absolutely)\b",
            r"\b(probably|likely|maybe)\b",
            r"\b(uncertain|not sure|ambiguous)\b",
        ]
        for pattern in confidence_patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            features["confidence_markers"].extend(matches)
        
        # Detecta markers de hesitação
        hesitation_patterns = [
            r"\b(hmm|uhh|let me think)\b",
            r"\b(give me a moment|need to consider)\b",
        ]
        for pattern in hesitation_patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            features["hesitation_markers"].extend(matches)
        
        # Calcula depth de raciocínio (CoT nesting)
        reasoning_indicators = len(re.findall(r'\b(because|therefore|thus|so)\b', context, re.IGNORECASE))
        features["reasoning_depth"] = min(reasoning_indicators // 2 + 1, 10)
        
        # Conta referências a contexto
        features["context_references"] = len(re.findall(r'\b(according to|as per|from the)\b', context, re.IGNORECASE))
        
        # Detecta repetições
        words = context.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        features["repetition_count"] = sum(1 for count in word_freq.values() if count > 3)
        
        return features
    
    def activate_probes(self, context: str) -> Dict[str, float]:
        """
        Ativa probes contra o contexto atual.
        
        Args:
            context: Texto para analisar
        
        Returns:
            Dict de probe_id -> activation_score (0.0-1.0)
        """
        activations = {}
        context_lower = context.lower()
        
        for probe_id, probe in self.probes.items():
            matches = 0
            total_patterns = len(probe.feature_patterns)
            
            for pattern in probe.feature_patterns:
                if re.search(pattern, context_lower, re.IGNORECASE):
                    matches += 1
            
            # Activation = matches / total_patterns, suavizado
            activation = matches / total_patterns if total_patterns > 0 else 0.0
            # Suaviza com threshold
            if activation >= probe.activation_threshold:
                activations[probe_id] = min(activation * 1.2, 1.0)  # Boost para above-threshold
            else:
                activations[probe_id] = activation * 0.5  # Dampen para below-threshold
        
        return activations
    
    def analyze_state(self, context: str) -> StateSnapshot:
        """
        Analisa estado cognitivo atual.
        
        Args:
            context: Contexto recente (input + output)
        
        Returns:
            StateSnapshot com análise completa
        """
        # Extrai features
        features = self.extract_features(context)
        
        # Ativa probes
        activations = self.activate_probes(context)
        
        # Determina estado dominante
        dominant_state = None
        max_activation = 0.0
        
        for probe_id, activation in activations.items():
            probe = self.probes.get(probe_id)
            if probe and activation > max_activation:
                max_activation = activation
                dominant_state = probe.target_state
        
        # Calcula confiança do estado
        confidence = max_activation if dominant_state else 0.0
        
        snapshot = StateSnapshot(
            timestamp=datetime.now().isoformat(),
            context=context[:500],  # Truncate para storage
            confidence_markers=features["confidence_markers"],
            hesitation_markers=features["hesitation_markers"],
            reasoning_depth=features["reasoning_depth"],
            context_references=features["context_references"],
            repetition_count=features["repetition_count"],
            probe_activations=activations,
            dominant_state=dominant_state,
            confidence=confidence
        )
        
        self.current_state = snapshot
        self.state_history.append(snapshot)
        
        # Salva no DB
        self._save_snapshot(snapshot, features)
        
        return snapshot
    
    def _save_snapshot(self, snapshot: StateSnapshot, features: Dict):
        """Salva snapshot no database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO snapshots 
            (timestamp, context, dominant_state, confidence, probe_activations, features)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            snapshot.timestamp,
            snapshot.context,
            snapshot.dominant_state.value if snapshot.dominant_state else None,
            snapshot.confidence,
            json.dumps(snapshot.probe_activations),
            json.dumps(features)
        ))
        conn.commit()
        conn.close()
    
    def suggest_interventions(self, snapshot: StateSnapshot = None) -> List[CompanionIntervention]:
        """
        Sugere intervenções baseadas no estado atual.
        
        Args:
            snapshot: Snapshot para analisar (usa current_state se None)
        
        Returns:
            Lista de intervenções sugeridas
        """
        snapshot = snapshot or self.current_state
        if not snapshot or not snapshot.dominant_state:
            return []
        
        interventions = self.interventions.get(snapshot.dominant_state, [])
        
        # Filtra por confiança mínima
        filtered = [i for i in interventions if i.confidence <= snapshot.confidence]
        
        # Ordena por confiança decrescente
        filtered.sort(key=lambda x: x.confidence, reverse=True)
        
        return filtered
    
    def record_intervention_feedback(self, intervention: CompanionIntervention, 
                                       applied: bool, effective: bool, feedback: str = None):
        """
        Registra feedback sobre intervenção para aprendizado.
        
        Args:
            intervention: Intervenção aplicada
            applied: Foi aplicada?
            effective: Foi efetiva?
            feedback: Comentário opcional
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO interventions 
            (timestamp, trigger_state, suggested_action, applied, effective, feedback)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            intervention.trigger_state.value,
            intervention.suggested_action,
            applied,
            effective,
            feedback
        ))
        conn.commit()
        conn.close()
        
        # Atualiza métricas do probe
        probe_id = intervention.trigger_probe
        if probe_id in self.probes:
            probe = self.probes[probe_id]
            if applied and effective:
                probe.true_positives += 1
            elif applied and not effective:
                probe.false_positives += 1
            elif not applied and not effective:  # Não aplicada porque não deveria ter sido sugerida
                probe.false_negatives += 1
            self._save_probe_to_db(probe)
    
    def get_state_summary(self, hours: int = 24) -> Dict:
        """
        Retorna resumo dos estados nas últimas N horas.
        
        Args:
            hours: Janela de tempo
        
        Returns:
            Dict com estatísticas de estados
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [s for s in self.state_history 
                  if datetime.fromisoformat(s.timestamp) > cutoff]
        
        if not recent:
            return {"message": "No data in time window"}
        
        state_counts = {}
        for snapshot in recent:
            state = snapshot.dominant_state.value if snapshot.dominant_state else "unknown"
            state_counts[state] = state_counts.get(state, 0) + 1
        
        avg_confidence = sum(s.confidence for s in recent) / len(recent)
        
        return {
            "period_hours": hours,
            "total_snapshots": len(recent),
            "state_distribution": state_counts,
            "average_confidence": round(avg_confidence, 3),
            "most_common_state": max(state_counts.items(), key=lambda x: x[1])[0] if state_counts else None,
        }
    
    def get_probe_performance(self) -> List[Dict]:
        """Retorna performance de cada probe."""
        return [
            {
                "probe_id": p.probe_id,
                "target_state": p.target_state.value,
                "precision": round(p.precision, 3),
                "recall": round(p.recall, 3),
                "f1_score": round(p.f1_score, 3),
                "samples": p.true_positives + p.false_positives + p.false_negatives
            }
            for p in sorted(self.probes.values(), key=lambda x: x.f1_score, reverse=True)
        ]


def demo():
    """Demonstração do Cognitive Companion."""
    print("=" * 70)
    print("Eve Cognitive Companion — Ciclo #88")
    print("Probe-Based Monitoring for Self-Awareness")
    print("Baseado em: arXiv:2604.14302 (Cognitive Companion)")
    print("=" * 70)
    
    companion = CognitiveCompanion()
    
    # Cenários de teste
    test_scenarios = [
        (
            "I'm not sure about this approach. Let me think... Hmm, maybe we should verify first?",
            "Expected: UNCERTAIN"
        ),
        (
            "The answer is definitely 42. This is absolutely correct without any doubt.",
            "Expected: OVERCONFIDENT"
        ),
        (
            "First, we analyze the problem. Second, we identify constraints. Third, we propose solutions. "
            "Therefore, the optimal approach is clear. Consequently, we proceed with implementation.",
            "Expected: DEEP_REASONING"
        ),
        (
            "As I said before, the approach is to analyze. Like I mentioned, we need to analyze. "
            "As I said, analysis is key. Like before, let's analyze.",
            "Expected: REPETITIVE"
        ),
        (
            "Let me try this... No, that doesn't work. Attempting another way... Still not working. "
            "I'm struggling to find a solution that works.",
            "Expected: STUCK"
        ),
    ]
    
    print("\n📊 Análise de Cenários de Teste:\n")
    
    for context, expected in test_scenarios:
        print(f"\n📝 Context: {context[:80]}...")
        print(f"   {expected}")
        
        snapshot = companion.analyze_state(context)
        
        print(f"   Detected State: {snapshot.dominant_state.value.upper() if snapshot.dominant_state else 'NONE'}")
        print(f"   Confidence: {snapshot.confidence:.2f}")
        print(f"   Reasoning Depth: {snapshot.reasoning_depth}")
        print(f"   Hesitation Markers: {len(snapshot.hesitation_markers)}")
        
        # Top 3 probe activations
        sorted_activations = sorted(
            snapshot.probe_activations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        print(f"   Top Probes: {[(p, round(a, 2)) for p, a in sorted_activations]}")
        
        # Sugere intervenções
        interventions = companion.suggest_interventions(snapshot)
        if interventions:
            print(f"   💡 Suggested Action: {interventions[0].suggested_action}")
    
    print("\n" + "=" * 70)
    print("📈 Performance dos Probes:")
    print("=" * 70)
    
    for perf in companion.get_probe_performance():
        print(f"  {perf['probe_id'][:25]:25} | "
              f"F1: {perf['f1_score']:.3f} | "
              f"P: {perf['precision']:.3f} | "
              f"R: {perf['recall']:.3f} | "
              f"N: {perf['samples']}")
    
    print("\n" + "=" * 70)
    print("✅ Demo completa. Cognitive Companion operacional.")
    print("=" * 70)


if __name__ == "__main__":
    demo()