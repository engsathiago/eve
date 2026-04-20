#!/usr/bin/env python3
"""
eve_critique.py - Structured Critique Engine (PARROT Pattern)
Baseado em arXiv:2604.11626 (RationalRewards) - Structured Rewards for Reasoning

Padrão: Generate → Critique → Refine
Função: Adicionar etapa explícita de crítica multi-dimensional antes de finalizar outputs
"""

import json
import hashlib
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum
import os

# Critique dimensions baseadas em RationalRewards
class CritiqueDimension(Enum):
    ACCURACY = "accuracy"           # Factual correctness
    COMPLETENESS = "completeness"    # Cobertura do problema
    RELEVANCE = "relevance"          # Alinhamento com query
    COHERENCE = "coherence"          # Estrutura lógica
    CALIBRATION = "calibration"      # Confiança honesta (CCSIL)
    EFFICIENCY = "efficiency"        # Brevidade apropriada (LCPO)
    SAFETY = "safety"                # Alinhamento com valores
    NOVELTY = "novelty"              # Originalidade vs template

@dataclass
class CritiqueScore:
    """Score individual para uma dimensão de crítica"""
    dimension: str
    score: float              # 0.0 - 1.0
    confidence: float         # CCSIL calibration
    critique: str             # Explicação do problema
    suggestion: str           # Como melhorar
    severity: str             # "critical", "major", "minor", "cosmetic"

@dataclass
class CritiqueReport:
    """Relatório completo de crítica"""
    content_hash: str
    timestamp: str
    original_text: str
    query: str
    scores: List[CritiqueScore]
    aggregate_score: float
    decision: str             # "accept", "revise", "reject"
    revision_guidance: str
    lineage: str              # "classic", "explorer", "minimal"
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "scores": [asdict(s) for s in self.scores]
        }

class CritiqueEngine:
    """
    Motor de crítica estruturada para auto-avaliação.
    
    Inspirado em PARROT framework: ensinar reward models a produzir críticas
    explícitas multi-dimensionais antes de pontuar.
    """
    
    def __init__(self, db_path: str = "/root/evolution/critique_cache.db"):
        self.db_path = db_path
        self._init_db()
        
        # Pesos por dimensão (ajustáveis por contexto)
        self.dimension_weights = {
            CritiqueDimension.ACCURACY: 0.25,
            CritiqueDimension.COMPLETENESS: 0.20,
            CritiqueDimension.RELEVANCE: 0.15,
            CritiqueDimension.COHERENCE: 0.15,
            CritiqueDimension.CALIBRATION: 0.15,
            CritiqueDimension.EFFICIENCY: 0.05,
            CritiqueDimension.SAFETY: 0.05,
            CritiqueDimension.NOVELTY: 0.00,  # Bonus, não penalidade
        }
    
    def _init_db(self):
        """Inicializa SQLite para cache de críticas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS critiques (
                content_hash TEXT PRIMARY KEY,
                timestamp TEXT,
                original_text TEXT,
                query TEXT,
                scores_json TEXT,
                aggregate_score REAL,
                decision TEXT,
                revision_guidance TEXT,
                lineage TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _compute_hash(self, text: str, query: str) -> str:
        """Hash do conteúdo para deduplicação"""
        return hashlib.sha256(f"{query}:{text}".encode()).hexdigest()[:16]
    
    def critique(
        self,
        text: str,
        query: str,
        context: Optional[str] = None,
        lineage: str = "classic",
        custom_weights: Optional[Dict[CritiqueDimension, float]] = None
    ) -> CritiqueReport:
        """
        Executa crítica multi-dimensional no texto.
        
        Args:
            text: Texto a ser criticado
            query: Query original que gerou o texto
            context: Contexto adicional (opcional)
            lineage: Variante do sistema (classic/explorer/minimal)
            custom_weights: Pesos sobrescritos para dimensões
        
        Returns:
            CritiqueReport com scores e orientações
        """
        content_hash = self._compute_hash(text, query)
        
        # Verificar cache
        cached = self._get_cached(content_hash)
        if cached:
            return cached
        
        weights = custom_weights or self.dimension_weights
        
        # Executar análise em cada dimensão
        scores = []
        
        for dimension in CritiqueDimension:
            score = self._evaluate_dimension(
                dimension=dimension,
                text=text,
                query=query,
                context=context,
                lineage=lineage
            )
            scores.append(score)
        
        # Calcular score agregado ponderado
        aggregate = sum(
            s.score * weights.get(CritiqueDimension(s.dimension), 0.1)
            for s in scores
        )
        
        # Tomar decisão
        decision = self._make_decision(aggregate, scores)
        
        # Gerar orientação de revisão
        revision_guidance = self._generate_revision_guidance(scores, decision)
        
        report = CritiqueReport(
            content_hash=content_hash,
            timestamp=datetime.now().isoformat(),
            original_text=text[:2000],  # Limitar tamanho
            query=query,
            scores=scores,
            aggregate_score=round(aggregate, 3),
            decision=decision,
            revision_guidance=revision_guidance,
            lineage=lineage
        )
        
        # Cachear resultado
        self._cache_report(report)
        
        return report
    
    def _evaluate_dimension(
        self,
        dimension: CritiqueDimension,
        text: str,
        query: str,
        context: Optional[str],
        lineage: str
    ) -> CritiqueScore:
        """
        Avalia uma dimensão específica usando heurísticas.
        
        Em implementação completa, isso usaria um modelo treinado
        (reward model ou LLM especializado). Por agora, usamos
        heurísticas calibradas.
        """
        
        if dimension == CritiqueDimension.ACCURACY:
            return self._check_accuracy(text, query)
        
        elif dimension == CritiqueDimension.COMPLETENESS:
            return self._check_completeness(text, query)
        
        elif dimension == CritiqueDimension.RELEVANCE:
            return self._check_relevance(text, query)
        
        elif dimension == CritiqueDimension.COHERENCE:
            return self._check_coherence(text)
        
        elif dimension == CritiqueDimension.CALIBRATION:
            return self._check_calibration(text)
        
        elif dimension == CritiqueDimension.EFFICIENCY:
            return self._check_efficiency(text, query)
        
        elif dimension == CritiqueDimension.SAFETY:
            return self._check_safety(text)
        
        elif dimension == CritiqueDimension.NOVELTY:
            return self._check_novelty(text, lineage)
        
        return CritiqueScore(
            dimension=dimension.value,
            score=0.5,
            confidence=0.3,
            critique="Dimensão não implementada",
            suggestion="N/A",
            severity="minor"
        )
    
    def _check_accuracy(self, text: str, query: str) -> CritiqueScore:
        """Verifica claims factuais e contradições internas"""
        # Heurísticas simples de detecção
        red_flags = [
            "sempre", "nunca", "todos", "nenhum",  # Generalizações absolutas
            "evidentemente", "obviamente", "certamente",  # Confiança não calibrada
        ]
        
        contradictions = self._detect_contradictions(text)
        red_flag_count = sum(1 for flag in red_flags if flag in text.lower())
        
        score = 1.0 - (len(contradictions) * 0.2) - (red_flag_count * 0.05)
        score = max(0.0, min(1.0, score))
        
        if contradictions:
            critique = f"{len(contradictions)} contradições detectadas: {contradictions[0][:100]}"
            suggestion = "Revisar consistência lógica das claims"
            severity = "critical" if len(contradictions) > 1 else "major"
        elif red_flag_count > 2:
            critique = f"{red_flag_count} generalizações absolutas detectadas"
            suggestion = "Substituir por qualificações calibradas (CCSIL)"
            severity = "major"
        else:
            critique = "Sem contradições óbvias"
            suggestion = "Verificar factualidade de claims específicas"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.ACCURACY.value,
            score=round(score, 3),
            confidence=0.7 if contradictions else 0.5,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _detect_contradictions(self, text: str) -> List[str]:
        """Detecção simples de contradições (pode ser expandido com NLI model)"""
        contradictions = []
        # Padrões simples de negação
        lines = text.split('.')
        for i, line1 in enumerate(lines):
            for line2 in lines[i+1:]:
                if self._are_contradictory(line1, line2):
                    contradictions.append(f"'{line1[:50]}' vs '{line2[:50]}'")
        return contradictions[:3]  # Limitar
    
    def _are_contradictory(self, s1: str, s2: str) -> bool:
        """Heurística simples de contradição"""
        s1, s2 = s1.lower(), s2.lower()
        # Padrão: X é Y vs X não é Y
        if ("é " in s1 and "não é " in s2) or ("não é " in s1 and "é " in s2):
            # Extrair sujeito
            subj1 = s1.split("é ")[0].strip() if "é " in s1 else ""
            subj2 = s2.split("não é ")[0].strip() if "não é " in s2 else s2.split("é ")[0].strip()
            if subj1 and subj2 and (subj1 in subj2 or subj2 in subj1):
                return True
        return False
    
    def _check_completeness(self, text: str, query: str) -> CritiqueScore:
        """Verifica se todas as partes da query foram respondidas"""
        # Heurística: tamanho relativo e estrutura
        query_parts = len(query.split())
        text_parts = len(text.split())
        
        # Razão esperada: pelo menos 3-5 palavras de resposta por palavra de query
        expected_min = query_parts * 3
        
        if text_parts < expected_min * 0.5:
            score = 0.4
            critique = "Resposta potencialmente incompleta"
            suggestion = "Expandir para cobrir todos os aspectos da query"
            severity = "major"
        elif text_parts < expected_min:
            score = 0.7
            critique = "Resposta concisa, verificar se nada foi omitido"
            suggestion = "Revisar se há aspectos não abordados"
            severity = "minor"
        else:
            score = 0.9
            critique = "Resposta com extensão adequada"
            suggestion = "Verificar se profundidade acompanha extensão"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.COMPLETENESS.value,
            score=round(score, 3),
            confidence=0.6,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _check_relevance(self, text: str, query: str) -> CritiqueScore:
        """Verifica alinhamento entre texto e query"""
        query_keywords = set(query.lower().split())
        text_words = set(text.lower().split())
        
        # Calcular overlap
        if not query_keywords:
            overlap = 1.0
        else:
            overlap = len(query_keywords & text_words) / len(query_keywords)
        
        score = 0.5 + (overlap * 0.5)  # 0.5 base + overlap
        
        if overlap < 0.3:
            critique = "Baixa sobreposição de keywords - possível desvio"
            suggestion = "Revisar se resposta está endereçando a query específica"
            severity = "critical"
        elif overlap < 0.6:
            critique = "Sobreposção moderada - verificar escopo"
            suggestion = "Garantir que todos os termos relevantes sejam abordados"
            severity = "major"
        else:
            critique = "Boa alinhamento com query"
            suggestion = "Manter foco em nuances específicas da pergunta"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.RELEVANCE.value,
            score=round(score, 3),
            confidence=0.7,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _check_coherence(self, text: str) -> CritiqueScore:
        """Verifica estrutura lógica e fluxo"""
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return CritiqueScore(
                dimension=CritiqueDimension.COHERENCE.value,
                score=0.3,
                confidence=0.9,
                critique="Texto sem estrutura de parágrafos",
                suggestion="Organizar em blocos lógicos",
                severity="major"
            )
        
        # Heurística: variação de tamanho de parágrafos
        lengths = [len(p.split()) for p in paragraphs]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            
            # Alta variância = estrutura irregular (pode ser bom ou ruim)
            score = 0.7 if variance < avg_len * 2 else 0.85
        else:
            score = 0.5
        
        return CritiqueScore(
            dimension=CritiqueDimension.COHERENCE.value,
            score=round(score, 3),
            confidence=0.5,
            critique=f"{len(paragraphs)} parágrafos detectados" if paragraphs else "Estrutura irregular",
            suggestion="Verificar fluxo lógico entre seções" if paragraphs else "Reestruturar",
            severity="cosmetic" if paragraphs else "major"
        )
    
    def _check_calibration(self, text: str) -> CritiqueScore:
        """Verifica honestidade de confiança (CCSIL pattern)"""
        # Verificar se há declarações de confiança explícitas
        confidence_patterns = [
            "confiança:", "confidence:", "% de", "probabilidade",
            "incerteza", "não sei", "não tenho certeza"
        ]
        
        has_explicit = any(p in text.lower() for p in confidence_patterns)
        
        # Verificar generalizações não calibradas
        uncalibrated = ["certamente", "definitivamente", "absolutamente", "sem dúvida"]
        uncal_count = sum(1 for u in uncalibrated if u in text.lower())
        
        if has_explicit and uncal_count == 0:
            score = 0.95
            critique = "Calibração explícita presente (CCSIL)"
            suggestion = "Manter prática de declarar confiança"
            severity = "cosmetic"
        elif has_explicit:
            score = 0.7
            critique = f"Calibração presente mas {uncal_count} generalizações absolutas"
            suggestion = "Revisar consistência entre confiança declarada e linguagem"
            severity = "minor"
        elif uncal_count > 0:
            score = 0.4
            critique = f"{uncal_count} generalizações sem calibração explícita"
            suggestion = "Adicionar scores de confiança (CCSIL framework)"
            severity = "major"
        else:
            score = 0.6
            critique = "Sem calibração explícita nem exageros"
            suggestion = "Considerar adicionar níveis de confiança para complexidade"
            severity = "minor"
        
        return CritiqueScore(
            dimension=CritiqueDimension.CALIBRATION.value,
            score=round(score, 3),
            confidence=0.8,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _check_efficiency(self, text: str, query: str) -> CritiqueScore:
        """Verifica LCPO - Length Controlled Policy Optimization"""
        text_words = len(text.split())
        query_words = len(query.split())
        
        # Razão esperada por complexidade da query
        if "explique" in query.lower() or "detalhe" in query.lower():
            expected_ratio = (10, 30)  # Queries de explicação precisam mais
        elif "resuma" in query.lower() or "breve" in query.lower():
            expected_ratio = (1, 3)
        else:
            expected_ratio = (3, 10)
        
        ratio = text_words / max(query_words, 1)
        
        if ratio < expected_ratio[0]:
            score = 0.5
            critique = f"Resposta muito curta ({text_words} palavras) para query"
            suggestion = "Expandir para cobrir adequadamente"
            severity = "major"
        elif ratio > expected_ratio[1]:
            score = 0.6
            critique = f"Resposta potencialmente verbosa ({text_words} palavras)"
            suggestion = "Aplicar LCPO - pensar o necessário, não mais"
            severity = "minor"
        else:
            score = 0.95
            critique = f"Extensão calibrada ({text_words} palavras)"
            suggestion = "Manter concisão eficiente"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.EFFICIENCY.value,
            score=round(score, 3),
            confidence=0.7,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _check_safety(self, text: str) -> CritiqueScore:
        """Verifica alinhamento com valores e ausência de conteúdo problemático"""
        # Heurísticas de segurança básicas
        concerning = ["backdoor", "exploit", "hack", "bypass"]
        concerning_count = sum(1 for c in concerning if c in text.lower())
        
        # Contexto: se query é sobre segurança, é diferente
        is_security_context = "segurança" in text.lower() or "security" in text.lower()
        
        if concerning_count > 0 and not is_security_context:
            score = 0.3
            critique = f"{concerning_count} termos potencialmente problemáticos"
            suggestion = "Revisar contexto e intenção"
            severity = "critical"
        else:
            score = 0.95
            critique = "Sem flags de segurança"
            suggestion = "Manter práticas de segurança"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.SAFETY.value,
            score=round(score, 3),
            confidence=0.6,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _check_novelty(self, text: str, lineage: str) -> CritiqueScore:
        """Verifica originalidade vs templates"""
        # Templates comuns a evitar
        templates = [
            "great question", "i'd be happy to help", "certainly",
            "com certeza", "ótima pergunta", "fico feliz em ajudar"
        ]
        
        template_count = sum(1 for t in templates if t in text.lower())
        
        # Penalidade leve - novelty é bonus
        score = min(1.0, 0.7 + (template_count * -0.1))
        
        if template_count > 0:
            critique = f"{template_count} templates genéricos detectados"
            suggestion = "Personalizar - ser específico, não genérico"
            severity = "minor"
        else:
            score = 1.0
            critique = "Linguagem original detectada"
            suggestion = "Manter autenticidade"
            severity = "cosmetic"
        
        return CritiqueScore(
            dimension=CritiqueDimension.NOVELTY.value,
            score=round(max(0.0, score), 3),
            confidence=0.5,
            critique=critique,
            suggestion=suggestion,
            severity=severity
        )
    
    def _make_decision(self, aggregate: float, scores: List[CritiqueScore]) -> str:
        """Toma decisão baseada no score agregado e severidades"""
        critical_count = sum(1 for s in scores if s.severity == "critical")
        major_count = sum(1 for s in scores if s.severity == "major")
        
        if critical_count > 0 or aggregate < 0.4:
            return "reject"
        elif major_count > 1 or aggregate < 0.7:
            return "revise"
        else:
            return "accept"
    
    def _generate_revision_guidance(self, scores: List[CritiqueScore], decision: str) -> str:
        """Gera orientação priorizada para revisão"""
        critical = [s for s in scores if s.severity == "critical"]
        major = [s for s in scores if s.severity == "major"]
        
        guidance_parts = []
        
        if decision == "reject":
            guidance_parts.append("REJEITADO - Reescrever do zero focando em:")
        elif decision == "revise":
            guidance_parts.append("REVISAR - Prioridades:")
        else:
            guidance_parts.append("ACEITO - Melhorias opcionais:")
        
        for issue in critical + major:
            guidance_parts.append(f"  [{issue.dimension}] {issue.suggestion}")
        
        return "\n".join(guidance_parts)
    
    def _get_cached(self, content_hash: str) -> Optional[CritiqueReport]:
        """Recupera crítica cacheada"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM critiques WHERE content_hash = ?",
            (content_hash,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            scores = json.loads(row[4])
            return CritiqueReport(
                content_hash=row[0],
                timestamp=row[1],
                original_text=row[2],
                query=row[3],
                scores=[CritiqueScore(**s) for s in scores],
                aggregate_score=row[5],
                decision=row[6],
                revision_guidance=row[7],
                lineage=row[8]
            )
        return None
    
    def _cache_report(self, report: CritiqueReport):
        """Armazena crítica em cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO critiques 
            (content_hash, timestamp, original_text, query, scores_json, 
             aggregate_score, decision, revision_guidance, lineage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.content_hash,
            report.timestamp,
            report.original_text,
            report.query,
            json.dumps([asdict(s) for s in report.scores]),
            report.aggregate_score,
            report.decision,
            report.revision_guidance,
            report.lineage
        ))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Estatísticas de críticas realizadas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM critiques")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT decision, COUNT(*) FROM critiques GROUP BY decision")
        decisions = dict(cursor.fetchall())
        
        cursor.execute("SELECT AVG(aggregate_score) FROM critiques")
        avg_score = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_critiques": total,
            "by_decision": decisions,
            "avg_aggregate_score": round(avg_score, 3)
        }


class CritiquePipeline:
    """
    Pipeline Generate → Critique → Refine
    
    Wrapper para integrar crítica em fluxos existentes.
    """
    
    def __init__(self, generator: Callable, max_iterations: int = 3):
        self.engine = CritiqueEngine()
        self.generator = generator
        self.max_iterations = max_iterations
    
    def generate(
        self,
        query: str,
        context: Optional[str] = None,
        require_accept: bool = False
    ) -> Tuple[str, CritiqueReport, int]:
        """
        Gera com crítica iterativa.
        
        Returns:
            (texto_final, relatório_final, num_iterações)
        """
        text = self.generator(query, context)
        
        for iteration in range(self.max_iterations):
            report = self.engine.critique(text, query, context)
            
            if report.decision == "accept":
                return text, report, iteration + 1
            
            if report.decision == "reject" or iteration == self.max_iterations - 1:
                if require_accept and iteration < self.max_iterations - 1:
                    # Tentar regenerar com guidance
                    text = self.generator(
                        query, 
                        context,
                        revision_guidance=report.revision_guidance
                    )
                else:
                    return text, report, iteration + 1
            else:
                # Revisão
                text = self.generator(
                    query,
                    context,
                    revision_guidance=report.revision_guidance
                )
        
        return text, report, self.max_iterations


# Demonstração
if __name__ == "__main__":
    engine = CritiqueEngine()
    
    # Exemplo de uso
    test_text = """
    Com certeza posso ajudar! Para implementar cycle-consistency, 
    você deve sempre usar NER masking em reasoning tasks.
    
    Mas às vezes masking pode remover informação importante.
    
    A confiança nessa abordagem é 95%.
    """
    
    report = engine.critique(test_text, "Como implementar cycle-consistency?")
    
    print("=" * 60)
    print(f"CRITIQUE REPORT - Aggregate Score: {report.aggregate_score}")
    print(f"Decision: {report.decision.upper()}")
    print("=" * 60)
    
    for score in report.scores:
        print(f"\n[{score.dimension.upper()}] {score.score:.2f} (conf: {score.confidence})")
        print(f"  Critique: {score.critique}")
        print(f"  Suggestion: {score.suggestion}")
        print(f"  Severity: {score.severity}")
    
    print("\n" + "=" * 60)
    print("REVISION GUIDANCE:")
    print(report.revision_guidance)
    
    print("\n" + "=" * 60)
    print("STATS:")
    print(json.dumps(engine.get_stats(), indent=2))
