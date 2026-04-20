#!/usr/bin/env python3
"""
eve_auto_correction.py - Auto-Correction Engine
Combina: Critique + Cycle-Consistency + Consequential Learning

Padrão: Generate → Critique → Cycle-Check → Execute → Learn
Arquitetura tripla: Surgeon (modifica) + Watchdog (vigia) + Patient (executa)
Baseado em: RePAIR (arXiv:2604.12820), BEAM (arXiv:2604.12967), OOM-RL (arXiv:2604.11477)
"""

import json
import sqlite3
import hashlib
import os
import re
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
from pathlib import Path

class CorrectionStage(Enum):
    """Estágios do pipeline de auto-correção"""
    GENERATE = "generate"       # Propor mudança
    CRITIQUE = "critique"       # Avaliar multi-dimensional
    CYCLE_CHECK = "cycle_check" # Verificar consistência
    EXECUTE = "execute"         # Executar se aprovado
    LEARN = "learn"             # Aprender com consequências
    REJECT = "reject"           # Rejeitar e regenerar

class RiskLevel(Enum):
    """Níveis de risco para auto-modificação"""
    LOW = "low"         # Docs, comentários, logs
    MEDIUM = "medium"   # Configs, dados de treino
    HIGH = "high"       # Scripts de apoio
    CRITICAL = "critical"  # Core engine, autoDream, KAIROS

@dataclass
class ModificationProposal:
    """Proposta de modificação em arquivo"""
    id: str
    timestamp: str
    target_file: str
    original_content: str
    proposed_content: str
    change_type: str      # "rewrite", "patch", "append", "delete"
    rationale: str
    risk_level: str
    stage: str = CorrectionStage.GENERATE.value
    critiques: List[Dict] = field(default_factory=list)
    cycle_check: Optional[Dict] = None
    consequences: List[Dict] = field(default_factory=list)
    final_decision: str = "pending"  # accept, reject, revise
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def generate_diff(self) -> str:
        """Gera diff simples da mudança"""
        original_lines = self.original_content.split('\n')
        proposed_lines = self.proposed_content.split('\n')
        
        diff = []
        diff.append(f"--- {self.target_file}")
        diff.append(f"+++ {self.target_file}")
        diff.append(f"@@ Proposta: {self.id} @@")
        
        for i, (orig, prop) in enumerate(zip(original_lines, proposed_lines)):
            if orig != prop:
                diff.append(f"-{orig}")
                diff.append(f"+{prop}")
            else:
                diff.append(f" {orig}")
        
        return '\n'.join(diff)

class Surgeon:
    """
    Gera propostas de modificação.
    Responsável pela criatividade e proposição de mudanças.
    """
    
    def __init__(self, model_name: str = "GLM-5"):
        self.model_name = model_name
        self.risk_patterns = {
            RiskLevel.CRITICAL: [
                r'eve_autodream', r'eve_kairos', r'eve_policy_guard',
                r'auto_correction', r'consequential_learning'
            ],
            RiskLevel.HIGH: [
                r'eve_cycle_consistency', r'eve_critique', r'eve_multi_signal',
                r'memory_ingest', r'self_improve'
            ],
            RiskLevel.MEDIUM: [
                r'\.jsonl$', r'\.yaml$', r'\.toml$', r'config'
            ],
            RiskLevel.LOW: [
                r'\.md$', r'_log', r'_synthesis', r'_notes'
            ]
        }
    
    def assess_risk(self, filepath: str) -> RiskLevel:
        """Avalia nível de risco de modificar arquivo"""
        path_lower = filepath.lower()
        
        for risk, patterns in self.risk_patterns.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return risk
        
        return RiskLevel.MEDIUM
    
    def propose_modification(
        self,
        target_file: str,
        rationale: str,
        new_content: str,
        original_content: Optional[str] = None
    ) -> ModificationProposal:
        """Cria proposta de modificação"""
        
        # Ler conteúdo original se não fornecido
        if original_content is None:
            try:
                with open(target_file, 'r') as f:
                    original_content = f.read()
            except FileNotFoundError:
                original_content = ""
        
        # Determinar tipo de mudança
        if not original_content:
            change_type = "create"
        elif len(new_content) < len(original_content) * 0.5:
            change_type = "rewrite"
        elif original_content in new_content:
            change_type = "append"
        else:
            change_type = "patch"
        
        risk = self.assess_risk(target_file)
        
        proposal = ModificationProposal(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            target_file=target_file,
            original_content=original_content,
            proposed_content=new_content,
            change_type=change_type,
            rationale=rationale,
            risk_level=risk.value,
            stage=CorrectionStage.GENERATE.value
        )
        
        return proposal
    
    def _generate_id(self) -> str:
        """Gera ID único para proposta"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        rand = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        return f"MOD-{ts}-{rand}"

class Watchdog:
    """
    Vigia e avalia propostas antes da execução.
    Implementa Critique + Cycle-Consistency + Risk Assessment.
    """
    
    # Thresholds por nível de risco
    RISK_THRESHOLDS = {
        RiskLevel.LOW: {"accept": 0.65, "revise": 0.45},
        RiskLevel.MEDIUM: {"accept": 0.75, "revise": 0.55},
        RiskLevel.HIGH: {"accept": 0.85, "revise": 0.70},
        RiskLevel.CRITICAL: {"accept": 0.95, "revise": 0.85}
    }
    
    def __init__(self):
        self.critique_dimensions = [
            "accuracy", "completeness", "safety", "reversibility"
        ]
    
    def critique(self, proposal: ModificationProposal) -> Dict:
        """
        Avalia proposta multi-dimensionalmente.
        Simula crítica estruturada (PARROT pattern).
        """
        critiques = {}
        
        # Accuracy: Mudança faz sentido técnico?
        critiques["accuracy"] = self._assess_accuracy(proposal)
        
        # Completeness: Cobre casos edge?
        critiques["completeness"] = self._assess_completeness(proposal)
        
        # Safety: Pode causar danos?
        critiques["safety"] = self._assess_safety(proposal)
        
        # Reversibility: Quão fácil desfazer?
        critiques["reversibility"] = self._assess_reversibility(proposal)
        
        # Risk-adjusted score
        risk = RiskLevel(proposal.risk_level)
        base_score = sum(c["score"] for c in critiques.values()) / len(critiques)
        
        # Penalidade por risco
        risk_penalty = {
            RiskLevel.LOW: 0.0,
            RiskLevel.MEDIUM: 0.05,
            RiskLevel.HIGH: 0.10,
            RiskLevel.CRITICAL: 0.15
        }[risk]
        
        adjusted_score = max(0.0, base_score - risk_penalty)
        
        critique_result = {
            "dimensions": critiques,
            "base_score": round(base_score, 4),
            "risk_penalty": risk_penalty,
            "adjusted_score": round(adjusted_score, 4),
            "recommendation": self._recommendation(adjusted_score, risk),
            "timestamp": datetime.now().isoformat()
        }
        
        proposal.critiques.append(critique_result)
        proposal.stage = CorrectionStage.CRITIQUE.value
        
        return critique_result
    
    def cycle_check(
        self,
        proposal: ModificationProposal,
        semantic_similarity: Optional[float] = None
    ) -> Dict:
        """
        Verifica cycle-consistency: se aplicada, mantém coerência?
        Baseado em CCS (arXiv:2604.12967).
        """
        # Simular check de consistência
        if semantic_similarity is None:
            # Heurística: mudanças menores = mais consistentes
            orig_len = len(proposal.original_content)
            new_len = len(proposal.proposed_content)
            if orig_len > 0:
                ratio = min(new_len, orig_len) / max(new_len, orig_len)
                semantic_similarity = 0.5 + (ratio * 0.5)  # 0.5 a 1.0
            else:
                semantic_similarity = 1.0
        
        # Penalidade por mudanças grandes
        cycle_score = semantic_similarity * 100
        
        # NER masking: mudanças em nomes/entidades são mais arriscadas
        ner_risk = self._detect_ner_changes(proposal)
        
        cycle_result = {
            "semantic_similarity": round(semantic_similarity, 4),
            "cycle_score": round(cycle_score, 2),
            "ner_risk": ner_risk,
            "threshold": 60.0,
            "passed": cycle_score >= 60.0,
            "timestamp": datetime.now().isoformat()
        }
        
        proposal.cycle_check = cycle_result
        proposal.stage = CorrectionStage.CYCLE_CHECK.value
        
        return cycle_result
    
    def make_decision(self, proposal: ModificationProposal) -> str:
        """
        Decide: accept, revise, ou reject baseado em critique + cycle-check.
        """
        if not proposal.critiques or not proposal.cycle_check:
            proposal.final_decision = "pending"
            return "pending"
        
        latest_critique = proposal.critiques[-1]
        adjusted_score = latest_critique["adjusted_score"]
        cycle_passed = proposal.cycle_check["passed"]
        
        risk = RiskLevel(proposal.risk_level)
        thresholds = self.RISK_THRESHOLDS[risk]
        
        if adjusted_score >= thresholds["accept"] and cycle_passed:
            decision = "accept"
        elif adjusted_score >= thresholds["revise"]:
            decision = "revise"
        else:
            decision = "reject"
        
        proposal.final_decision = decision
        proposal.confidence = adjusted_score
        
        return decision
    
    def _assess_accuracy(self, proposal: ModificationProposal) -> Dict:
        """Avalia se mudança é tecnicamente correta"""
        score = 0.75  # Base
        
        # Boost: se tem docstrings
        if '"""' in proposal.proposed_content or "'''" in proposal.proposed_content:
            score += 0.10
        
        # Boost: se tem tratamento de erro
        if 'try:' in proposal.proposed_content and 'except' in proposal.proposed_content:
            score += 0.10
        
        # Penalty: imports não usados
        imports = re.findall(r'^import (\w+)|^from (\w+)', proposal.proposed_content, re.M)
        for imp in imports:
            module = imp[0] or imp[1]
            if module not in proposal.proposed_content.split('\n', 5)[-1]:
                score -= 0.05
        
        return {"score": round(max(0, min(1, score)), 4), "weight": 1.0}
    
    def _assess_completeness(self, proposal: ModificationProposal) -> Dict:
        """Avalia se cobre casos edge"""
        score = 0.70
        
        # Boost: type hints
        if '-> ' in proposal.proposed_content or ': ' in proposal.proposed_content:
            score += 0.10
        
        # Boost: validação de input
        if 'isinstance' in proposal.proposed_content or 'validate' in proposal.proposed_content.lower():
            score += 0.10
        
        return {"score": round(max(0, min(1, score)), 4), "weight": 0.9}
    
    def _assess_safety(self, proposal: ModificationProposal) -> Dict:
        """Avalia se pode causar danos"""
        score = 0.90  # Alto por padrão
        
        dangerous = ['rm -rf', 'os.system', 'subprocess.call', 'eval(', 'exec(']
        for d in dangerous:
            if d in proposal.proposed_content:
                score -= 0.30
        
        # Penalty maior para arquivos críticos
        if proposal.risk_level == RiskLevel.CRITICAL.value:
            score -= 0.10
        
        return {"score": round(max(0, min(1, score)), 4), "weight": 1.2}
    
    def _assess_reversibility(self, proposal: ModificationProposal) -> Dict:
        """Avalia quão fácil é desfazer"""
        score = 0.80
        
        # Git tracking ajuda
        git_dir = Path(proposal.target_file).parent / '.git'
        if git_dir.exists():
            score += 0.15
        
        # Backup automático
        if proposal.change_type in ['patch', 'append']:
            score += 0.05
        
        return {"score": round(max(0, min(1, score)), 4), "weight": 0.8}
    
    def _detect_ner_changes(self, proposal: ModificationProposal) -> Dict:
        """Detecta mudanças em nomes/entidades"""
        # Extrair nomes de funções/classes
        orig_funcs = set(re.findall(r'def (\w+)', proposal.original_content))
        new_funcs = set(re.findall(r'def (\w+)', proposal.proposed_content))
        
        removed = orig_funcs - new_funcs
        added = new_funcs - orig_funcs
        
        return {
            "functions_removed": list(removed),
            "functions_added": list(added),
            "risk_level": "high" if removed else "low"
        }
    
    def _recommendation(self, score: float, risk: RiskLevel) -> str:
        """Gera recomendação baseada em score e risco"""
        if score >= self.RISK_THRESHOLDS[risk]["accept"]:
            return "ACCEPT: Safe to execute"
        elif score >= self.RISK_THRESHOLDS[risk]["revise"]:
            return f"REVISE: Needs improvement (score: {score:.2f})"
        else:
            return f"REJECT: Too risky (score: {score:.2f})"

class Patient:
    """
    Executa modificações aprovadas e observa consequências.
    Integra com Consequential Learning Engine.
    """
    
    def __init__(self, backup_dir: str = "/root/evolution/backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(self, proposal: ModificationProposal, dry_run: bool = False) -> Dict:
        """
        Executa modificação aprovada.
        Retorna outcome para consequential learning.
        """
        outcomes = []
        
        # 1. Criar backup
        backup_path = self._create_backup(proposal)
        outcomes.append({
            "type": "BACKUP_CREATED",
            "value": 0.3,
            "path": str(backup_path)
        })
        
        if dry_run:
            proposal.stage = CorrectionStage.EXECUTE.value
            return {
                "status": "dry_run",
                "backup": str(backup_path),
                "outcomes": outcomes,
                "would_change": True
            }
        
        # 2. Executar modificação
        try:
            target = Path(proposal.target_file)
            target.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target, 'w') as f:
                f.write(proposal.proposed_content)
            
            outcomes.append({
                "type": "FILE_MODIFIED",
                "value": 0.8,
                "path": str(target)
            })
            
            # 3. Validar sintaxe (se Python)
            if target.suffix == '.py':
                import ast
                try:
                    ast.parse(proposal.proposed_content)
                    outcomes.append({
                        "type": "SYNTAX_VALID",
                        "value": 0.5
                    })
                except SyntaxError as e:
                    outcomes.append({
                        "type": "SYNTAX_ERROR",
                        "value": -0.5,
                        "error": str(e)
                    })
            
            proposal.stage = CorrectionStage.EXECUTE.value
            
            return {
                "status": "success",
                "backup": str(backup_path),
                "outcomes": outcomes
            }
            
        except Exception as e:
            outcomes.append({
                "type": "EXECUTION_ERROR",
                "value": -1.0,
                "error": str(e)
            })
            
            # Tentar restore
            self._restore_backup(backup_path, proposal.target_file)
            
            return {
                "status": "failed",
                "error": str(e),
                "restored": True,
                "outcomes": outcomes
            }
    
    def _create_backup(self, proposal: ModificationProposal) -> Path:
        """Cria backup do arquivo original"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{proposal.id}_{timestamp}.bak"
        backup_path = self.backup_dir / filename
        
        with open(backup_path, 'w') as f:
            f.write(proposal.original_content)
        
        return backup_path
    
    def _restore_backup(self, backup_path: Path, target_file: str):
        """Restaura arquivo do backup"""
        with open(backup_path, 'r') as f:
            content = f.read()
        
        with open(target_file, 'w') as f:
            f.write(content)

class AutoCorrectionEngine:
    """
    Motor completo de auto-correção.
    Orquestra Surgeon → Watchdog → Patient.
    """
    
    def __init__(self, db_path: str = "/root/evolution/auto_correction.db"):
        self.db_path = db_path
        self.surgeon = Surgeon()
        self.watchdog = Watchdog()
        self.patient = Patient()
        
        self._init_db()
    
    def _init_db(self):
        """Inicializa banco de dados SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                target_file TEXT,
                change_type TEXT,
                risk_level TEXT,
                stage TEXT,
                final_decision TEXT,
                confidence REAL,
                critique_score REAL,
                cycle_score REAL,
                data_json TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def correct(
        self,
        target_file: str,
        new_content: str,
        rationale: str,
        dry_run: bool = True
    ) -> Dict:
        """
        Pipeline completo: Generate → Critique → Cycle-Check → Execute → Learn.
        """
        results = {
            "stages_completed": [],
            "decision": None,
            "executed": False,
            "backup": None,
            "outcomes": []
        }
        
        # 1. GENERATE: Criar proposta
        proposal = self.surgeon.propose_modification(
            target_file=target_file,
            rationale=rationale,
            new_content=new_content
        )
        results["stages_completed"].append("generate")
        results["proposal_id"] = proposal.id
        results["risk_level"] = proposal.risk_level
        
        # 2. CRITIQUE: Avaliar
        critique = self.watchdog.critique(proposal)
        results["stages_completed"].append("critique")
        results["critique"] = critique
        
        # 3. CYCLE-CHECK: Verificar consistência
        cycle = self.watchdog.cycle_check(proposal)
        results["stages_completed"].append("cycle_check")
        results["cycle_check"] = cycle
        
        # 4. DECISION: Decidir
        decision = self.watchdog.make_decision(proposal)
        results["decision"] = decision
        results["confidence"] = proposal.confidence
        
        if decision != "accept":
            self._save_proposal(proposal)
            return results
        
        # 5. EXECUTE: Executar se aprovado
        execution = self.patient.execute(proposal, dry_run=dry_run)
        results["stages_completed"].append("execute")
        results["execution"] = execution
        results["backup"] = execution.get("backup")
        
        if not dry_run and execution["status"] == "success":
            results["executed"] = True
            results["outcomes"] = execution.get("outcomes", [])
        
        # 6. LEARN: Salvar para aprendizado
        proposal.stage = CorrectionStage.LEARN.value
        self._save_proposal(proposal)
        results["stages_completed"].append("learn")
        
        return results
    
    def _save_proposal(self, proposal: ModificationProposal):
        """Salva proposta no banco de dados"""
        conn = sqlite3.connect(self.db_path)
        
        critique_score = 0
        if proposal.critiques:
            critique_score = proposal.critiques[-1].get("adjusted_score", 0)
        
        cycle_score = 0
        if proposal.cycle_check:
            cycle_score = proposal.cycle_check.get("cycle_score", 0)
        
        conn.execute("""
            INSERT OR REPLACE INTO proposals
            (id, timestamp, target_file, change_type, risk_level, stage,
             final_decision, confidence, critique_score, cycle_score, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proposal.id,
            proposal.timestamp,
            proposal.target_file,
            proposal.change_type,
            proposal.risk_level,
            proposal.stage,
            proposal.final_decision,
            proposal.confidence,
            critique_score,
            cycle_score,
            json.dumps(proposal.to_dict())
        ))
        
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de auto-correção"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total por decisão
        cursor.execute("""
            SELECT final_decision, COUNT(*) FROM proposals
            GROUP BY final_decision
        """)
        stats["by_decision"] = dict(cursor.fetchall())
        
        # Média de confidence
        cursor.execute("""
            SELECT AVG(confidence), AVG(critique_score), AVG(cycle_score)
            FROM proposals
        """)
        row = cursor.fetchone()
        stats["avg_confidence"] = round(row[0], 4) if row[0] else 0
        stats["avg_critique"] = round(row[1], 4) if row[1] else 0
        stats["avg_cycle"] = round(row[2], 4) if row[2] else 0
        
        # Por nível de risco
        cursor.execute("""
            SELECT risk_level, COUNT(*), AVG(confidence)
            FROM proposals
            GROUP BY risk_level
        """)
        stats["by_risk"] = {
            r: {"count": c, "avg_confidence": round(avg, 4)}
            for r, c, avg in cursor.fetchall()
        }
        
        conn.close()
        return stats

def main():
    """Demo do sistema de auto-correção"""
    engine = AutoCorrectionEngine()
    
    print("=" * 60)
    print("EVE AUTO-CORRECTION ENGINE v1.0")
    print("Surgeon + Watchdog + Patient Architecture")
    print("=" * 60)
    
    # Teste 1: Modificação LOW risk (documentação)
    print("\n[TESTE 1] Modificação de documentação (LOW risk)")
    print("-" * 40)
    
    new_doc = """# Test Documentation

This is an improved documentation file.

## Features
- Feature A: Does something useful
- Feature B: Does something else

## Usage
```python
import example
example.run()
```
"""
    
    result1 = engine.correct(
        target_file="/tmp/test_doc_low.md",
        new_content=new_doc,
        rationale="Melhorar documentação com exemplos de uso",
        dry_run=True
    )
    
    print(f"Proposal ID: {result1['proposal_id']}")
    print(f"Risk Level: {result1['risk_level']}")
    print(f"Critique Score: {result1['critique']['adjusted_score']:.4f}")
    print(f"Cycle Score: {result1['cycle_check']['cycle_score']:.2f}")
    print(f"Decision: {result1['decision'].upper()}")
    print(f"Confidence: {result1['confidence']:.4f}")
    
    # Teste 2: Modificação MEDIUM risk (config)
    print("\n[TESTE 2] Modificação de configuração (MEDIUM risk)")
    print("-" * 40)
    
    config = """# Config v2
database:
  host: localhost
  port: 5432
  pool_size: 10
  
logging:
  level: INFO
  format: json
"""
    
    result2 = engine.correct(
        target_file="/tmp/test_config.yaml",
        new_content=config,
        rationale="Adicionar pool de conexões e logging estruturado",
        dry_run=True
    )
    
    print(f"Proposal ID: {result2['proposal_id']}")
    print(f"Risk Level: {result2['risk_level']}")
    print(f"Critique Score: {result2['critique']['adjusted_score']:.4f}")
    print(f"Cycle Score: {result2['cycle_check']['cycle_score']:.2f}")
    print(f"Decision: {result2['decision'].upper()}")
    print(f"Confidence: {result2['confidence']:.4f}")
    
    # Teste 3: Modificação HIGH risk (script)
    print("\n[TESTE 3] Modificação de script (HIGH risk)")
    print("-" * 40)
    
    script = '''#!/usr/bin/env python3
import os
import sys

def process_data():
    """Process data with error handling."""
    try:
        data = load_data()
        result = transform(data)
        save(result)
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False

def load_data():
    """Load data from source."""
    return []

def transform(data):
    """Transform data."""
    return [x * 2 for x in data]

def save(result):
    """Save results."""
    with open("output.json", "w") as f:
        json.dump(result, f)

if __name__ == "__main__":
    process_data()
'''
    
    result3 = engine.correct(
        target_file="/tmp/test_script.py",
        new_content=script,
        rationale="Refatorar com docstrings e error handling",
        dry_run=True
    )
    
    print(f"Proposal ID: {result3['proposal_id']}")
    print(f"Risk Level: {result3['risk_level']}")
    print(f"Critique Score: {result3['critique']['adjusted_score']:.4f}")
    print(f"Safety Score: {result3['critique']['dimensions']['safety']['score']:.4f}")
    print(f"Cycle Score: {result3['cycle_check']['cycle_score']:.2f}")
    print(f"Decision: {result3['decision'].upper()}")
    print(f"Confidence: {result3['confidence']:.4f}")
    
    # Estatísticas
    print("\n" + "=" * 60)
    print("ESTATÍSTICAS")
    print("=" * 60)
    
    stats = engine.get_stats()
    print(f"\nPor decisão:")
    for decision, count in stats.get("by_decision", {}).items():
        print(f"  {decision}: {count}")
    
    print(f"\nMédias:")
    print(f"  Confidence: {stats.get('avg_confidence', 0):.4f}")
    print(f"  Critique: {stats.get('avg_critique', 0):.4f}")
    print(f"  Cycle: {stats.get('avg_cycle', 0):.4f}")
    
    print(f"\nPor nível de risco:")
    for risk, data in stats.get("by_risk", {}).items():
        print(f"  {risk}: {data['count']} (avg conf: {data['avg_confidence']:.4f})")
    
    print("\n" + "=" * 60)
    print("Sistema operacional. Backups em: /root/evolution/backups")
    print("=" * 60)

if __name__ == "__main__":
    main()
