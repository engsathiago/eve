#!/usr/bin/env python3
"""
eve_consequential_learning.py - Consequential Learning Engine (OOM-RL Pattern)
Baseado em arXiv:2604.11477 - Outcome-Oriented Reinforcement Learning

Princípio: Consequências reais são "un-hackable negative gradients".
Feedback humano (RLHF) tem sycophancy e test evasion.
Consequências reais são matematicamente incorruptíveis.

Padrão: Action → Real Outcome → Learning Signal
"""

import json
import sqlite3
import hashlib
import random
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import os

# Counter para IDs únicos
_id_counter = 0

class OutcomeType(Enum):
    """Tipos de outcome que podem ser medidos"""
    FILE_CREATED = "file_created"           # Arquivo foi criado com sucesso
    FILE_MODIFIED = "file_modified"        # Arquivo foi modificado
    SCRIPT_EXECUTED = "script_executed"    # Script rodou sem erro
    ERROR_OCCURRED = "error_occurred"      # Erro foi gerado
    USER_FEEDBACK = "user_feedback"        # Feedback explícito do usuário
    EXTERNAL_API = "external_api"          # Resposta de API externa
    RESOURCE_USED = "resource_used"        # CPU/memória/tempo consumido
    GOAL_ACHIEVED = "goal_achieved"        # Objetivo declarado foi atingido

class SignalQuality(Enum):
    """Qualidade do sinal de aprendizado"""
    REAL = "real"           # Consequência real, irreversível
    SIMULATED = "simulated" # Simulação, pode ser hackeada
    PREDICTED = "predicted" # Modelo prediz outcome, incerto
    EXTERNAL = "external"   # Feedback de fonte externa

@dataclass
class Consequence:
    """Uma consequência observada de uma ação"""
    id: str
    action_id: str
    timestamp: str
    outcome_type: str
    outcome_value: float      # -1.0 a 1.0 (negativo = ruim, positivo = bom)
    outcome_data: Dict          # Metadados específicos do outcome
    signal_quality: str       # real/simulated/predicted/external
    latency_hours: float        # Quanto tempo até observar
    reversibility: float        # 0.0 = irreversível, 1.0 = totalmente reversível
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class Action:
    """Uma ação tomada com intent e expected outcomes"""
    id: str
    timestamp: str
    action_type: str          # "file_edit", "script_run", "web_search", etc.
    description: str          # O que foi feito
    intent: str               # Objetivo esperado
    expected_outcomes: List[Dict]  # O que se esperava que acontecesse
    actual_outcomes: List[Consequence] = field(default_factory=list)
    status: str = "pending"   # pending, completed, failed
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class LearningSignal:
    """Sinal de aprendizado derivado de consequências"""
    action_id: str
    signal_strength: float    # Magnitude do sinal (-1.0 a 1.0)
    signal_quality: str       # real/simulated/predicted/external
    weight: float             # Peso baseado em qualidade e irreversibilidade
    explanation: str          # Por que este sinal foi gerado
    training_pairs: List[Dict]  # Pares de treino derivados
    
    def to_dict(self) -> Dict:
        return asdict(self)

class ConsequentialLearningEngine:
    """
    Motor de aprendizado baseado em consequências reais.
    
    Princípios OOM-RL:
    1. Consequências reais > Feedback simulado
    2. Irreversibilidade = Qualidade do sinal
    3. Latência é aceitável se o sinal for real
    4. Sycophancy é impossível com consequências objetivas
    """
    
    def __init__(self, db_path: str = "/root/evolution/consequential.db"):
        self.db_path = db_path
        self._init_db()
        
        # Quality multipliers (quanto mais real, mais peso)
        self.quality_weights = {
            SignalQuality.REAL: 1.0,
            SignalQuality.EXTERNAL: 0.8,
            SignalQuality.SIMULATED: 0.5,
            SignalQuality.PREDICTED: 0.3
        }
    
    def _init_db(self):
        """Inicializa SQLite para tracking de ações e consequências"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                action_type TEXT,
                description TEXT,
                intent TEXT,
                expected_outcomes TEXT,  -- JSON
                actual_outcomes TEXT,    -- JSON
                status TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consequences (
                id TEXT PRIMARY KEY,
                action_id TEXT,
                timestamp TEXT,
                outcome_type TEXT,
                outcome_value REAL,
                outcome_data TEXT,       -- JSON
                signal_quality TEXT,
                latency_hours REAL,
                reversibility REAL,
                FOREIGN KEY (action_id) REFERENCES actions(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_signals (
                id TEXT PRIMARY KEY,
                action_id TEXT,
                timestamp TEXT,
                signal_strength REAL,
                signal_quality TEXT,
                weight REAL,
                explanation TEXT,
                training_pairs TEXT,     -- JSON
                FOREIGN KEY (action_id) REFERENCES actions(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _generate_id(self, prefix: str) -> str:
        """Gera ID único"""
        global _id_counter
        _id_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = random.randint(1000, 9999)
        return f"{prefix}-{timestamp}-{random_part}-{_id_counter:04d}"
    
    def record_action(
        self,
        action_type: str,
        description: str,
        intent: str,
        expected_outcomes: List[Dict]
    ) -> str:
        """
        Registra uma ação antes de executá-la.
        
        Args:
            action_type: Tipo da ação (file_edit, script_run, etc.)
            description: Descrição do que será feito
            intent: Objetivo esperado
            expected_outcomes: Lista de outcomes esperados
        
        Returns:
            action_id para rastreamento posterior
        """
        action_id = self._generate_id("ACT")
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO actions 
            (id, timestamp, action_type, description, intent, expected_outcomes, actual_outcomes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            action_id,
            timestamp,
            action_type,
            description,
            intent,
            json.dumps(expected_outcomes),
            json.dumps([]),
            "pending"
        ))
        
        conn.commit()
        conn.close()
        
        return action_id
    
    def record_outcome(
        self,
        action_id: str,
        outcome_type: OutcomeType,
        outcome_value: float,
        outcome_data: Dict,
        signal_quality: SignalQuality,
        latency_hours: float = 0,
        reversibility: float = 0.5
    ) -> str:
        """
        Registra uma consequência observada.
        
        Args:
            action_id: ID da ação que causou esta consequência
            outcome_type: Tipo de outcome
            outcome_value: Valor (-1.0 a 1.0)
            outcome_data: Metadados específicos
            signal_quality: Qualidade do sinal
            latency_hours: Quanto tempo até observar
            reversibility: Quão reversível é (0.0 = irreversível)
        
        Returns:
            consequence_id
        """
        consequence_id = self._generate_id("OUT")
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO consequences
            (id, action_id, timestamp, outcome_type, outcome_value, outcome_data, signal_quality, latency_hours, reversibility)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            consequence_id,
            action_id,
            timestamp,
            outcome_type.value,
            outcome_value,
            json.dumps(outcome_data),
            signal_quality.value,
            latency_hours,
            reversibility
        ))
        
        conn.commit()
        conn.close()
        
        # Atualizar action com novo outcome
        self._update_action_outcomes(action_id)
        
        return consequence_id
    
    def _update_action_outcomes(self, action_id: str):
        """Atualiza a lista de outcomes em actions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM consequences WHERE action_id = ?", (action_id,))
        rows = cursor.fetchall()
        
        outcomes = []
        for row in rows:
            outcomes.append({
                "id": row[0],
                "type": row[3],
                "value": row[4],
                "quality": row[6]
            })
        
        cursor.execute(
            "UPDATE actions SET actual_outcomes = ? WHERE id = ?",
            (json.dumps(outcomes), action_id)
        )
        
        conn.commit()
        conn.close()
    
    def generate_learning_signal(self, action_id: str) -> Optional[LearningSignal]:
        """
        Gera sinal de aprendizado a partir das consequências de uma ação.
        
        Fórmula: signal = Σ(outcome_value × quality_weight × (1 - reversibility))
        
        Quanto mais irreversível e real, maior o peso do sinal.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Buscar action
        cursor.execute("SELECT * FROM actions WHERE id = ?", (action_id,))
        action_row = cursor.fetchone()
        
        if not action_row:
            conn.close()
            return None
        
        # Buscar consequências
        cursor.execute("SELECT * FROM consequences WHERE action_id = ?", (action_id,))
        consequence_rows = cursor.fetchall()
        
        conn.close()
        
        if not consequence_rows:
            return None
        
        # Calcular sinal agregado
        total_signal = 0.0
        total_weight = 0.0
        explanations = []
        
        for row in consequence_rows:
            outcome_value = row[4]
            quality_str = row[6]
            reversibility = row[8]
            
            quality = SignalQuality(quality_str)
            quality_weight = self.quality_weights.get(quality, 0.5)
            
            # Fórmula OOM-RL: mais peso para sinais reais e irreversíveis
            irreversibility_factor = 1.0 - reversibility
            weight = quality_weight * irreversibility_factor
            
            weighted_signal = outcome_value * weight
            total_signal += weighted_signal
            total_weight += weight
            
            explanations.append(
                f"{row[3]}: {outcome_value:+.2f} × {quality.value}({quality_weight}) × "
                f"irreversibility({irreversibility_factor:.2f}) = {weighted_signal:+.3f}"
            )
        
        # Normalizar
        if total_weight > 0:
            normalized_signal = total_signal / total_weight
        else:
            normalized_signal = 0.0
        
        # Gerar training pairs
        training_pairs = self._generate_training_pairs(action_row, consequence_rows, normalized_signal)
        
        # Determinar quality dominante
        qualities = [SignalQuality(row[6]) for row in consequence_rows]
        dominant_quality = max(set(qualities), key=lambda q: self.quality_weights.get(q, 0))
        
        signal = LearningSignal(
            action_id=action_id,
            signal_strength=round(normalized_signal, 4),
            signal_quality=dominant_quality.value,
            weight=round(total_weight, 4),
            explanation="\n".join(explanations),
            training_pairs=training_pairs
        )
        
        # Salvar sinal
        self._save_learning_signal(signal)
        
        return signal
    
    def _generate_training_pairs(
        self,
        action_row: tuple,
        consequence_rows: List[tuple],
        signal_strength: float
    ) -> List[Dict]:
        """
        Gera pares de treino a partir do sinal.
        
        Se signal_strength > 0: reforçar comportamento
        Se signal_strength < 0: aprender com erro
        """
        action_type = action_row[2]
        description = action_row[3]
        intent = action_row[4]
        
        pairs = []
        
        # Par 1: Instruction → Action (se positivo, reforçar; se negativo, evitar)
        if signal_strength > 0.3:
            instruction = f"Given the intent: '{intent}', produce the correct action."
            response = description
            label = "chosen"
        elif signal_strength < -0.3:
            instruction = f"Given the intent: '{intent}', identify why this action failed."
            response = f"Action failed with signal {signal_strength:.2f}. Lessons learned from consequences."
            label = "rejected"
        else:
            instruction = f"Given the intent: '{intent}', evaluate this action."
            response = f"Action had mixed outcomes (signal: {signal_strength:.2f})."
            label = "neutral"
        
        pairs.append({
            "instruction": instruction,
            "response": response,
            "label": label,
            "signal": signal_strength,
            "category": "action_outcome"
        })
        
        # Par 2: Consequence prediction (se houver outcomes negativos)
        negative_outcomes = [r for r in consequence_rows if r[4] < 0]
        if negative_outcomes:
            instruction = f"Predict outcomes of: {description[:100]}"
            response = "; ".join([
                f"May lead to {r[3]} with value {r[4]:.2f}"
                for r in negative_outcomes[:3]
            ])
            pairs.append({
                "instruction": instruction,
                "response": response,
                "label": "teaching",
                "signal": -0.5,
                "category": "consequence_prediction"
            })
        
        return pairs
    
    def _save_learning_signal(self, signal: LearningSignal):
        """Salva sinal de aprendizado no banco"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        signal_id = self._generate_id("SIG")
        timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO learning_signals
            (id, action_id, timestamp, signal_strength, signal_quality, weight, explanation, training_pairs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_id,
            signal.action_id,
            timestamp,
            signal.signal_strength,
            signal.signal_quality,
            signal.weight,
            signal.explanation,
            json.dumps(signal.training_pairs)
        ))
        
        conn.commit()
        conn.close()
    
    def get_pending_actions(self, max_age_hours: int = 24) -> List[Dict]:
        """
        Retorna ações pendentes que precisam de outcomes registrados.
        Útil para cron jobs que verificam resultados.
        """
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM actions 
            WHERE status = 'pending' AND timestamp > ?
        """, (cutoff,))
        
        rows = cursor.fetchall()
        conn.close()
        
        actions = []
        for row in rows:
            actions.append({
                "id": row[0],
                "timestamp": row[1],
                "type": row[2],
                "description": row[3],
                "intent": row[4],
                "expected_outcomes": json.loads(row[5])
            })
        
        return actions
    
    def get_learning_signals(
        self,
        min_quality: SignalQuality = SignalQuality.SIMULATED,
        min_strength: float = 0.1,
        limit: int = 100
    ) -> List[Dict]:
        """
        Retorna sinais de aprendizado filtrados por qualidade e força.
        """
        quality_order = [q.value for q in SignalQuality]
        min_idx = quality_order.index(min_quality.value)
        allowed_qualities = quality_order[min_idx:]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in allowed_qualities])
        cursor.execute(f"""
            SELECT * FROM learning_signals 
            WHERE signal_quality IN ({placeholders})
            AND ABS(signal_strength) >= ?
            ORDER BY weight DESC, timestamp DESC
            LIMIT ?
        """, (*allowed_qualities, min_strength, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        signals = []
        for row in rows:
            signals.append({
                "id": row[0],
                "action_id": row[1],
                "timestamp": row[2],
                "strength": row[3],
                "quality": row[4],
                "weight": row[5],
                "explanation": row[6],
                "training_pairs": json.loads(row[7])
            })
        
        return signals
    
    def export_training_data(
        self,
        output_path: str = "/root/evolution/consequential_training.jsonl",
        min_quality: SignalQuality = SignalQuality.REAL
    ) -> int:
        """
        Exporta pares de treino para arquivo JSONL.
        
        Returns:
            Número de pares exportados
        """
        signals = self.get_learning_signals(min_quality=min_quality)
        
        count = 0
        with open(output_path, 'w') as f:
            for signal in signals:
                for pair in signal["training_pairs"]:
                    record = {
                        "instruction": pair["instruction"],
                        "response": pair["response"],
                        "label": pair["label"],
                        "signal": pair["signal"],
                        "category": pair["category"],
                        "quality": signal["quality"],
                        "weight": signal["weight"],
                        "source": "consequential_learning",
                        "timestamp": signal["timestamp"]
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1
        
        return count
    
    def get_stats(self) -> Dict:
        """Estatísticas do sistema de consequential learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM actions")
        total_actions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM consequences")
        total_consequences = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM learning_signals")
        total_signals = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(signal_strength) FROM learning_signals")
        avg_signal = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT signal_quality, COUNT(*) FROM learning_signals GROUP BY signal_quality
        """)
        quality_dist = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "total_actions": total_actions,
            "total_consequences": total_consequences,
            "total_signals": total_signals,
            "avg_signal_strength": round(avg_signal, 4),
            "quality_distribution": quality_dist
        }


class ConsequenceTracker:
    """
    Context manager para tracking automático de ações.
    
    Uso:
        with ConsequenceTracker(engine, "file_edit", "Fix bug in script") as tracker:
            # Fazer ação
            edit_file(...)
            tracker.add_expected_outcome("file_saved", "File should exist")
        
        # No futuro, registrar outcome:
        tracker.record_actual_outcome(OutcomeType.FILE_CREATED, 1.0, {...})
    """
    
    def __init__(self, engine: ConsequentialLearningEngine, action_type: str, intent: str):
        self.engine = engine
        self.action_type = action_type
        self.intent = intent
        self.action_id = None
        self.expected_outcomes = []
    
    def __enter__(self):
        self.action_id = self.engine.record_action(
            action_type=self.action_type,
            description="Pending...",
            intent=self.intent,
            expected_outcomes=[]
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Atualizar descrição final
        if exc_type:
            status = "failed"
            description = f"Failed with {exc_type.__name__}: {exc_val}"
        else:
            status = "completed"
            description = self._get_description()
        
        conn = sqlite3.connect(self.engine.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE actions SET description = ?, expected_outcomes = ?, status = ? WHERE id = ?",
            (description, json.dumps(self.expected_outcomes), status, self.action_id)
        )
        conn.commit()
        conn.close()
        
        return False  # Não suprimir exceções
    
    def set_description(self, description: str):
        """Define descrição da ação"""
        self._description = description
    
    def add_expected_outcome(self, outcome_type: str, description: str):
        """Adiciona outcome esperado"""
        self.expected_outcomes.append({
            "type": outcome_type,
            "description": description
        })
    
    def record_outcome(
        self,
        outcome_type: OutcomeType,
        value: float,
        data: Dict,
        quality: SignalQuality = SignalQuality.REAL
    ):
        """Registra outcome atual"""
        return self.engine.record_outcome(
            action_id=self.action_id,
            outcome_type=outcome_type,
            outcome_value=value,
            outcome_data=data,
            signal_quality=quality
        )
    
    def _get_description(self) -> str:
        return getattr(self, '_description', f"Action {self.action_type} for intent: {self.intent}")


# Demonstração e teste
if __name__ == "__main__":
    engine = ConsequentialLearningEngine()
    
    print("=" * 60)
    print("CONSEQUENTIAL LEARNING ENGINE - OOM-RL Pattern")
    print("=" * 60)
    
    # Simular uma ação
    action_id = engine.record_action(
        action_type="script_run",
        description="Executar eve_critique.py para testar implementação",
        intent="Verificar se critique engine funciona corretamente",
        expected_outcomes=[
            {"type": "script_executed", "description": "Script roda sem erro"},
            {"type": "file_created", "description": "Cache SQLite criado"}
        ]
    )
    
    print(f"\n[1] Action recorded: {action_id}")
    
    # Registrar outcomes positivos
    engine.record_outcome(
        action_id=action_id,
        outcome_type=OutcomeType.SCRIPT_EXECUTED,
        outcome_value=1.0,
        outcome_data={"exit_code": 0, "output_lines": 42},
        signal_quality=SignalQuality.REAL,
        latency_hours=0.1,
        reversibility=0.0  # Irreversível
    )
    
    engine.record_outcome(
        action_id=action_id,
        outcome_type=OutcomeType.FILE_CREATED,
        outcome_value=0.8,
        outcome_data={"file": "critique_cache.db", "size_bytes": 20480},
        signal_quality=SignalQuality.REAL,
        latency_hours=0.1,
        reversibility=0.3  # Parcialmente reversível (pode deletar)
    )
    
    print("[2] Outcomes recorded: SCRIPT_EXECUTED, FILE_CREATED")
    
    # Gerar sinal de aprendizado
    signal = engine.generate_learning_signal(action_id)
    
    if signal:
        print(f"\n[3] Learning Signal Generated:")
        print(f"    Strength: {signal.signal_strength:+.4f}")
        print(f"    Quality: {signal.signal_quality}")
        print(f"    Weight: {signal.weight:.4f}")
        print(f"    Training pairs: {len(signal.training_pairs)}")
        
        print(f"\n    Explanation:")
        for line in signal.explanation.split('\n'):
            print(f"      {line}")
    
    # Estatísticas
    print("\n[4] Stats:")
    print(json.dumps(engine.get_stats(), indent=2))
    
    # Exportar
    count = engine.export_training_data("/tmp/test_consequential.jsonl")
    print(f"\n[5] Exported {count} training pairs to /tmp/test_consequential.jsonl")
    
    print("\n" + "=" * 60)
    print("Consequential Learning: Real outcomes > Simulated feedback")
    print("OOM-RL Principle: Un-hackable negative gradients from reality")
    print("=" * 60)
