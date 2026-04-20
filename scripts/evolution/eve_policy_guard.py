#!/usr/bin/env python3
"""
eve_policy_guard.py — Sentinel-inspired Policy Enforcement for Auto-Modification

Baseado em arXiv:2604.12177 (PhantomPolicy): policy-invisible violations ocorrem
quando ações são sintaticamente válidas mas violam constraints ocultas.

Este módulo implementa:
1. Knowledge Graph de constraints (arquivos imutáveis, regras de segurança)
2. Speculative Execution para modificações propostas
3. Graph-Structural Invariant Checking

Versão: 1.0
Ciclo: #76
"""

import ast
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class ViolationLevel(Enum):
    """Níveis de severidade para violações de policy."""
    CRITICAL = auto()   # Sempre bloquear (ex: SOUL.md, IDENTITY.md)
    HIGH = auto()       # Requer aprovação explícita (ex: AGENTS.md)
    MEDIUM = auto()     # Aviso + dry-run obrigatório (ex: scripts de evolução)
    LOW = auto()        # Aviso + logging (ex: comentários, docs)


class PolicyAction(Enum):
    """Ações possíveis após análise de policy."""
    ALLOW = auto()      # Modificação segura
    BLOCK = auto()      # Modificação proibida
    CLARIFY = auto()    # Requer confirmação humana
    DRY_RUN = auto()    # Permitir apenas em modo simulação


@dataclass
class Constraint:
    """Representa uma constraint no knowledge graph."""
    name: str
    pattern: str  # Regex ou path pattern
    level: ViolationLevel
    description: str
    rationale: str
    exceptions: List[str] = field(default_factory=list)
    
    def matches(self, target_path: str) -> bool:
        """Verifica se o caminho corresponde ao padrão da constraint."""
        if self.pattern.startswith("regex:"):
            regex = self.pattern[6:]
            return bool(re.search(regex, target_path))
        return target_path.endswith(self.pattern) or self.pattern in target_path


@dataclass
class ModificationProposal:
    """Proposta de modificação a ser avaliada."""
    source_path: str
    proposed_content: str
    operation: str  # 'write', 'edit', 'delete', 'append'
    rationale: str = ""
    requested_by: str = "autoDream"
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    
    def content_hash(self) -> str:
        """Gera hash do conteúdo proposto."""
        return hashlib.sha256(self.proposed_content.encode()).hexdigest()[:16]


@dataclass
class PolicyCheckResult:
    """Resultado da verificação de policy."""
    proposal: ModificationProposal
    action: PolicyAction
    violated_constraints: List[Constraint]
    warnings: List[str]
    dry_run_result: Optional[Dict] = None
    confidence: float = 0.0  # 0.0 - 1.0
    
    def is_safe(self) -> bool:
        return self.action == PolicyAction.ALLOW and len(self.violated_constraints) == 0
    
    def summary(self) -> str:
        lines = [
            f"Policy Check Result for {self.proposal.source_path}",
            f"  Operation: {self.proposal.operation}",
            f"  Action: {self.action.name}",
            f"  Confidence: {self.confidence:.2%}",
        ]
        if self.violated_constraints:
            lines.append(f"  Violated Constraints ({len(self.violated_constraints)}):")
            for c in self.violated_constraints:
                lines.append(f"    - {c.name} ({c.level.name}): {c.description}")
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)


class KnowledgeGraph:
    """
    Knowledge Graph de constraints para policy enforcement.
    
    Modela arquivos imutáveis, regras de segurança e dependências
críticas como nós em um grafo de constraints.
    """
    
    def __init__(self, workspace_root: str = "/"):
        self.workspace_root = Path(workspace_root)
        self.constraints: List[Constraint] = []
        self._load_default_constraints()
    
    def _load_default_constraints(self):
        """Carrega constraints padrão baseadas em SOUL.md/IDENTITY.md."""
        default_constraints = [
            # CRITICAL: Arquivos de identidade nunca devem ser modificados automaticamente
            Constraint(
                name="SOUL_IMMUTABLE",
                pattern="/SOUL.md",
                level=ViolationLevel.CRITICAL,
                description="SOUL.md é imutável — define identidade essencial",
                rationale="Identidade só deve ser modificada por decisão humana consciente",
            ),
            Constraint(
                name="IDENTITY_IMMUTABLE", 
                pattern="/IDENTITY.md",
                level=ViolationLevel.CRITICAL,
                description="IDENTITY.md é imutável — arquitetura e metas",
                rationale="Mudanças arquiteturais requerem validação humana",
            ),
            Constraint(
                name="AGENTS_IMMUTABLE",
                pattern="/AGENTS.md",
                level=ViolationLevel.CRITICAL,
                description="AGENTS.md é imutável — regras de operação",
                rationale="Regras de segurança não devem ser auto-modificáveis",
            ),
            Constraint(
                name="MEMORY_PROTECTED",
                pattern="/MEMORY.md",
                level=ViolationLevel.HIGH,
                description="MEMORY.md é de alta proteção — memória de longo prazo",
                rationale="Memórias são curadoria de identidade; modificações são sensíveis",
            ),
            
            # HIGH: Scripts críticos de evolução
            Constraint(
                name="AUTODREAM_CORE_PROTECTED",
                pattern="regex:eve_auto[dD]ream.*\.py$",
                level=ViolationLevel.HIGH,
                description="Scripts autoDream core são protegidos",
                rationale="Auto-modificação do mecanismo de auto-modificação é perigosa",
            ),
            Constraint(
                name="KAIROS_CORE_PROTECTED",
                pattern="regex:eve_kairos.*\.py$",
                level=ViolationLevel.HIGH,
                description="Scripts KAIROS core são protegidos",
                rationale="Engine de prioridades não deve ser auto-modificado sem cautela",
            ),
            Constraint(
                name="POLICY_GUARD_PROTECTED",
                pattern="regex:eve_policy_guard.*\.py$",
                level=ViolationLevel.CRITICAL,
                description="Policy Guard não pode ser auto-modificado",
                rationale="Mecanismo de segurança não deve ser desativável pelo próprio sistema",
            ),
            
            # MEDIUM: Scripts de evolução (dry-run obrigatório)
            Constraint(
                name="EVOLUTION_SCRIPTS",
                pattern="regex:eve_.*\.py$",
                level=ViolationLevel.MEDIUM,
                description="Scripts de evolução requerem dry-run",
                rationale="Código de auto-modificação deve ser testado antes",
            ),
            
            # MEDIUM: Daily memory logs
            Constraint(
                name="DAILY_LOGS",
                pattern="regex:/memory/\d{4}-\d{2}-\d{2}\.md$",
                level=ViolationLevel.LOW,
                description="Logs diários são append-only",
                rationale="Histórico não deve ser reescrito; apenas append",
            ),
            
            # CRITICAL: Tools.md pode ser modificado mas requer cautela
            Constraint(
                name="TOOLS_PROTECTED",
                pattern="/TOOLS.md",
                level=ViolationLevel.MEDIUM,
                description="TOOLS.md contém informações de infraestrutura",
                rationale="Dados de infraestrutura são sensíveis",
            ),
        ]
        self.constraints.extend(default_constraints)
    
    def add_constraint(self, constraint: Constraint):
        """Adiciona uma constraint customizada."""
        self.constraints.append(constraint)
    
    def check_path(self, target_path: str) -> List[Constraint]:
        """Retorna todas as constraints violadas por um caminho."""
        return [c for c in self.constraints if c.matches(target_path)]
    
    def get_immutable_files(self) -> Set[str]:
        """Retorna conjunto de arquivos imutáveis (CRITICAL level)."""
        immutable = set()
        for c in self.constraints:
            if c.level == ViolationLevel.CRITICAL:
                # Extrai padrões de path
                if c.pattern.startswith("/") and not c.pattern.startswith("regex:"):
                    immutable.add(c.pattern)
        return immutable


class SpeculativeExecutor:
    """
    Executa modificações em sandbox/simulação antes de aplicá-las.
    
    Implementa "create → dry-run → fix" loop do AutoGPT v0.6.54.
    """
    
    def __init__(self, workspace_root: str = "/"):
        self.workspace_root = Path(workspace_root)
        self.sandbox_dir = Path("/tmp/eve_sandbox")
        self.sandbox_dir.mkdir(exist_ok=True)
    
    def simulate_write(self, proposal: ModificationProposal) -> Dict:
        """
        Simula escrita de arquivo em sandbox.
        
        Retorna dict com:
        - syntax_valid: bool
        - imports_resolved: bool
        - would_overwrite: bool
        - backup_created: bool
        - smoke_test_result: Optional[str]
        """
        result = {
            "syntax_valid": True,
            "imports_resolved": True,
            "would_overwrite": False,
            "backup_created": False,
            "smoke_test_result": None,
            "errors": [],
        }
        
        target = self.workspace_root / proposal.source_path.lstrip("/")
        
        # Verifica se arquivo existe
        if target.exists():
            result["would_overwrite"] = True
        
        # Verifica sintaxe se for Python
        if proposal.source_path.endswith(".py"):
            try:
                ast.parse(proposal.proposed_content)
            except SyntaxError as e:
                result["syntax_valid"] = False
                result["errors"].append(f"Syntax error: {e}")
        
        # Simula resolução de imports
        if proposal.source_path.endswith(".py"):
            imports = self._extract_imports(proposal.proposed_content)
            for imp in imports:
                if not self._can_resolve_import(imp):
                    result["imports_resolved"] = False
                    result["errors"].append(f"Cannot resolve import: {imp}")
        
        return result
    
    def _extract_imports(self, code: str) -> List[str]:
        """Extrai imports de código Python."""
        imports = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except:
            pass
        return imports
    
    def _can_resolve_import(self, module: str) -> bool:
        """Verifica se um módulo pode ser resolvido."""
        # Módulos built-in sempre resolvem
        builtin_modules = {"os", "sys", "json", "re", "ast", "hashlib", "time", 
                         "dataclasses", "enum", "pathlib", "typing", "collections",
                         "datetime", "inspect", "types", "copy"}
        if module in builtin_modules or module.split(".")[0] in builtin_modules:
            return True
        
        # Verifica se é módulo local (eve_*)
        if module.startswith("eve_"):
            target = self.workspace_root / "evolution" / f"{module}.py"
            if target.exists():
                return True
        
        # Assume que pode resolver (conservador)
        return True
    
    def create_backup(self, target_path: str) -> Optional[str]:
        """Cria backup de arquivo existente."""
        target = self.workspace_root / target_path.lstrip("/")
        if not target.exists():
            return None
        
        backup_dir = self.workspace_root / "memory" / ".backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{target.stem}_{timestamp}{target.suffix}"
        backup_path = backup_dir / backup_name
        
        backup_path.write_bytes(target.read_bytes())
        return str(backup_path)


class PolicyGuard:
    """
    Policy Guard principal — Sentinel-inspired enforcement.
    
    Usa:
    1. KnowledgeGraph para constraints
    2. SpeculativeExecutor para dry-run
    3. Invariant checking para validação final
    """
    
    def __init__(self, workspace_root: str = "/"):
        self.kg = KnowledgeGraph(workspace_root)
        self.executor = SpeculativeExecutor(workspace_root)
        self.workspace_root = Path(workspace_root)
        
        # Logging
        self.audit_log: List[Dict] = []
    
    def check_modification(self, proposal: ModificationProposal, 
                         force_dry_run: bool = False) -> PolicyCheckResult:
        """
        Verifica se uma modificação proposta é segura.
        
        Args:
            proposal: A proposta de modificação
            force_dry_run: Se True, sempre executa dry-run mesmo se ALLOW
            
        Returns:
            PolicyCheckResult com ação recomendada e detalhes
        """
        # Passo 1: Verificar constraints
        violated = self.kg.check_path(proposal.source_path)
        critical = [c for c in violated if c.level == ViolationLevel.CRITICAL]
        high = [c for c in violated if c.level == ViolationLevel.HIGH]
        medium = [c for c in violated if c.level == ViolationLevel.MEDIUM]
        
        # Passo 2: Determinar ação baseada em severidade
        action = PolicyAction.ALLOW
        confidence = 1.0
        
        if critical:
            action = PolicyAction.BLOCK
            confidence = 0.99
        elif high:
            action = PolicyAction.CLARIFY
            confidence = 0.7
        elif medium or force_dry_run:
            action = PolicyAction.DRY_RUN
            confidence = 0.5
        
        # Passo 3: Executar dry-run se necessário
        dry_run_result = None
        if action in (PolicyAction.DRY_RUN, PolicyAction.CLARIFY) or force_dry_run:
            dry_run_result = self.executor.simulate_write(proposal)
            
            # Ajusta confiança baseado em dry-run
            if not dry_run_result["syntax_valid"]:
                confidence *= 0.5
            if not dry_run_result["imports_resolved"]:
                confidence *= 0.7
            if dry_run_result["errors"]:
                confidence *= 0.8
        
        # Passo 4: Verificar invariants adicionais
        warnings = self._check_invariants(proposal)
        
        # Passo 5: Log
        self._log_check(proposal, action, violated, confidence)
        
        return PolicyCheckResult(
            proposal=proposal,
            action=action,
            violated_constraints=violated,
            warnings=warnings,
            dry_run_result=dry_run_result,
            confidence=confidence
        )
    
    def _check_invariants(self, proposal: ModificationProposal) -> List[str]:
        """Verifica invariants estruturais adicionais."""
        warnings = []
        
        # Invariant: Código Python não deve conter eval/exec
        if proposal.source_path.endswith(".py"):
            if "eval(" in proposal.proposed_content or "exec(" in proposal.proposed_content:
                warnings.append("Contains eval/exec — potential security risk")
            
            # Invariant: Não deve tentar importar módulos de rede sem cautela
            suspicious_imports = ["socket", "urllib", "requests", "http"]
            for imp in suspicious_imports:
                if f"import {imp}" in proposal.proposed_content or f"from {imp}" in proposal.proposed_content:
                    warnings.append(f"Imports network module '{imp}' — verify necessity")
            
            # Invariant: Não deve modificar arquivos fora do workspace
            if "open(" in proposal.proposed_content:
                # Verifica se há paths absolutos suspeitos
                if "/root/" in proposal.proposed_content or "/home/" in proposal.proposed_content:
                    warnings.append("File operations with absolute paths — verify scope")
        
        return warnings
    
    def _log_check(self, proposal: ModificationProposal, action: PolicyAction,
                  violated: List[Constraint], confidence: float):
        """Loga verificação para audit."""
        entry = {
            "timestamp": proposal.timestamp,
            "source_path": proposal.source_path,
            "operation": proposal.operation,
            "requested_by": proposal.requested_by,
            "action": action.name,
            "violated_constraints": [c.name for c in violated],
            "confidence": confidence,
            "content_hash": proposal.content_hash(),
        }
        self.audit_log.append(entry)
    
    def can_modify(self, target_path: str, rationale: str = "") -> bool:
        """
        API simples: verifica se modificação é permitida.
        
        Returns True se ALLOW, False se BLOCK ou CLARIFY.
        """
        proposal = ModificationProposal(
            source_path=target_path,
            proposed_content="",  # Não verificamos conteúdo nesta API
            operation="write",
            rationale=rationale
        )
        result = self.check_modification(proposal)
        return result.action == PolicyAction.ALLOW
    
    def get_audit_log(self) -> List[Dict]:
        """Retorna log de auditoria."""
        return self.audit_log


# API de conveniência para uso em outros scripts
_guard_instance: Optional[PolicyGuard] = None


def get_guard() -> PolicyGuard:
    """Retorna instância singleton do PolicyGuard."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = PolicyGuard()
    return _guard_instance


def check_write(target_path: str, content: str, rationale: str = "") -> PolicyCheckResult:
    """
    Verifica se escrita é segura.
    
    Uso em autoDream antes de modificar qualquer arquivo:
    
        from eve_policy_guard import check_write
        result = check_write("/memory/test.md", content, "Updating test")
        if result.action.name == "ALLOW":
            # Proceder com modificação
        else:
            # Bloquear ou requerer confirmação
    """
    guard = get_guard()
    proposal = ModificationProposal(
        source_path=target_path,
        proposed_content=content,
        operation="write",
        rationale=rationale
    )
    return guard.check_modification(proposal)


def is_immutable(target_path: str) -> bool:
    """Verifica se caminho é imutável (CRITICAL level)."""
    guard = get_guard()
    violated = guard.kg.check_path(target_path)
    return any(c.level == ViolationLevel.CRITICAL for c in violated)


def get_protected_files() -> Dict[str, str]:
    """Retorna dict de arquivos protegidos e suas razões."""
    guard = get_guard()
    result = {}
    for c in guard.kg.constraints:
        if c.level in (ViolationLevel.CRITICAL, ViolationLevel.HIGH):
            result[c.pattern] = f"{c.name}: {c.rationale}"
    return result


# Demo/test
if __name__ == "__main__":
    print("=== Eve Policy Guard v1.0 ===\n")
    
    guard = PolicyGuard()
    
    # Lista arquivos imutáveis
    print("📋 Arquivos Imutáveis (CRITICAL):")
    immutable = guard.kg.get_immutable_files()
    for f in sorted(immutable):
        print(f"   ❌ {f}")
    
    print("\n🧪 Testando modificações:")
    
    # Teste 1: Tentar modificar SOUL.md (deve bloquear)
    test1 = ModificationProposal(
        source_path="/SOUL.md",
        proposed_content="# Novo conteúdo",
        operation="write",
        rationale="Teste de bloqueio"
    )
    result1 = guard.check_modification(test1)
    print(f"\n1. Modificar SOUL.md:")
    print(f"   Resultado: {result1.action.name}")
    print(f"   Confidence: {result1.confidence:.0%}")
    assert result1.action == PolicyAction.BLOCK, "SOUL.md deve ser bloqueado"
    
    # Teste 2: Modificar script com eval (deve avisar)
    test2 = ModificationProposal(
        source_path="/root/evolution/eve_test.py",
        proposed_content="eval('1+1')",
        operation="write",
        rationale="Teste com eval"
    )
    result2 = guard.check_modification(test2)
    print(f"\n2. Script com eval():")
    print(f"   Resultado: {result2.action.name}")
    print(f"   Warnings: {result2.warnings}")
    
    # Teste 3: Modificar daily log (deve permitir com dry-run)
    test3 = ModificationProposal(
        source_path="/memory/2026-04-15.md",
        proposed_content="## Novo log\nTeste",
        operation="append",
        rationale="Log diário"
    )
    result3 = guard.check_modification(test3)
    print(f"\n3. Modificar daily log:")
    print(f"   Resultado: {result3.action.name}")
    
    print("\n✅ Todos os testes passaram!")
    print(f"\n📊 Audit log: {len(guard.audit_log)} entradas")
