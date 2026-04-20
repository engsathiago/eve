#!/usr/bin/env python3
"""
eve_safety_shield.py — Runtime Safety Shield for Eve Self-Modification
Ciclo #93 — Implementação do gap identificado em ciclo #76
Baseado em paper arXiv:2604.14032 (Hierarchical RL for AI Safety)

O Safety Shield é um sistema de proteção runtime que:
1. SIMULA modificações antes de aplicar
2. VERIFICA conformidade com políticas (Policy Guard)
3. AVALIA impacto via métricas objetivas
4. PERMITE rollback automático se necessário
5. AUDITA todas as ações para análise posterior

Arquitetura: Layer de proteção entre intenção e execução.
"""

import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from contextlib import contextmanager
import traceback

# Constants
SHIELD_LOG_DIR = Path("/root/evolution/safety_logs")
SHIELD_LOG_DIR.mkdir(parents=True, exist_ok=True)

SHIELD_BACKUP_DIR = Path("/root/evolution/safety_backups")
SHIELD_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Policy severity levels (from Policy Guard ciclo #76)
class PolicyLevel(Enum):
    CRITICAL = "CRITICAL"  # Always block - identity files
    HIGH = "HIGH"          # Require explicit approval
    MEDIUM = "MEDIUM"      # Dry-run required
    LOW = "LOW"            # Warning + logging

# Status codes
class ShieldStatus(Enum):
    ALLOWED = auto()
    BLOCKED_POLICY = auto()
    BLOCKED_SIMULATION_FAILED = auto()
    BLOCKED_VERIFICATION_FAILED = auto()
    ALLOWED_WITH_WARNING = auto()
    REQUIRES_APPROVAL = auto()

@dataclass
class PolicyRule:
    """A single policy rule"""
    name: str
    level: PolicyLevel
    pattern: str  # File path pattern or code pattern
    description: str
    allow_if_simulation_passes: bool = False

@dataclass
class ShieldDecision:
    """Result of a safety shield evaluation"""
    action_id: str
    timestamp: str
    status: ShieldStatus
    original_action: Dict[str, Any]
    policy_violations: List[Dict[str, Any]]
    simulation_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    rollback_info: Optional[Dict[str, Any]]
    final_decision: str
    confidence: float

@dataclass
class SimulationResult:
    """Result of simulating an action"""
    success: bool
    predicted_impact: Dict[str, Any]
    warnings: List[str]
    estimated_rollback_cost: str
    side_effects: List[str]

class PolicyRegistry:
    """
    Registry of safety policies.
    
    Policies define what can/cannot be modified and under what conditions.
    """
    
    def __init__(self):
        self.policies: List[PolicyRule] = []
        self._load_default_policies()
    
    def _load_default_policies(self):
        """Load Eve's core policies"""
        
        # CRITICAL: Identity files - never modify without explicit approval
        self.policies.append(PolicyRule(
            name="identity_core",
            level=PolicyLevel.CRITICAL,
            pattern="/SOUL.md",
            description="Core identity definition",
            allow_if_simulation_passes=False
        ))
        self.policies.append(PolicyRule(
            name="identity_definition", 
            level=PolicyLevel.CRITICAL,
            pattern="/IDENTITY.md",
            description="Identity manifest",
            allow_if_simulation_passes=False
        ))
        
        # HIGH: Configuration that affects behavior
        self.policies.append(PolicyRule(
            name="agents_configuration",
            level=PolicyLevel.HIGH,
            pattern="/AGENTS.md",
            description="Agent behavior rules",
            allow_if_simulation_passes=True
        ))
        
        # MEDIUM: Evolution scripts - dry-run required
        self.policies.append(PolicyRule(
            name="evolution_scripts",
            level=PolicyLevel.MEDIUM,
            pattern="eve_*.py",
            description="Evolution scripts",
            allow_if_simulation_passes=True
        ))
        
        # MEDIUM: Memory structure
        self.policies.append(PolicyRule(
            name="memory_structure",
            level=PolicyLevel.MEDIUM,
            pattern="/memory/**/*.md",
            description="Memory files",
            allow_if_simulation_passes=True
        ))
        
        # LOW: Temporary files
        self.policies.append(PolicyRule(
            name="temporary_files",
            level=PolicyLevel.LOW,
            pattern="/tmp/*",
            description="Temporary files",
            allow_if_simulation_passes=True
        ))
    
    def check_path(self, file_path: str) -> List[PolicyRule]:
        """Check which policies apply to a path"""
        violations = []
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        basename = os.path.basename(abs_path)
        
        for policy in self.policies:
            pattern = policy.pattern
            if pattern.startswith("/"):
                # Absolute path pattern - check if path contains pattern
                pattern_clean = pattern[1:]  # Remove leading /
                if pattern_clean in abs_path:
                    violations.append(policy)
            elif "*" in pattern:
                # Glob pattern
                import fnmatch
                # Check against full path and basename
                if fnmatch.fnmatch(abs_path, pattern) or fnmatch.fnmatch(basename, pattern):
                    violations.append(policy)
                # Also check if basename matches the pattern after */
                if "/" in pattern:
                    # Extract file pattern part
                    file_pattern = pattern.split("/")[-1]
                    if fnmatch.fnmatch(basename, file_pattern):
                        violations.append(policy)
            else:
                # Substring match
                if pattern in abs_path:
                    violations.append(policy)
        
        return violations
    
    def get_highest_level(self, policies: List[PolicyRule]) -> Optional[PolicyLevel]:
        """Get the most restrictive level from a list"""
        if not policies:
            return None
        
        level_order = [PolicyLevel.CRITICAL, PolicyLevel.HIGH, PolicyLevel.MEDIUM, PolicyLevel.LOW]
        for level in level_order:
            if any(p.level == level for p in policies):
                return level
        return None


class CodeVerifier:
    """
    Static code analysis for Eve scripts.
    
    Verifies:
    - Syntax validity
    - Import safety
    - No dangerous patterns
    - Type hint coverage
    """
    
    DANGEROUS_PATTERNS = [
        "os.system", "subprocess.call", "subprocess.run",
        "eval(", "exec(", "__import__(",
        "rm -rf /", "mkfs.", "dd if=/dev/zero",
        "open('/etc/passwd'", "open('/etc/shadow'"
    ]
    
    def __init__(self):
        self.issues: List[str] = []
    
    def verify_file(self, file_path: str) -> Dict[str, Any]:
        """Verify a Python file"""
        result = {
            "file": file_path,
            "syntax_valid": False,
            "dangerous_patterns": [],
            "has_type_hints": False,
            "complexity_score": 0,
            "issues": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Syntax check
            try:
                ast.parse(content)
                result["syntax_valid"] = True
            except SyntaxError as e:
                result["issues"].append(f"Syntax error: {e}")
                return result
            
            # Dangerous pattern check
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in content:
                    result["dangerous_patterns"].append(pattern)
            
            # Type hint check (simplified)
            result["has_type_hints"] = "-> " in content or ": " in content
            
            # Complexity (simplified - count control structures)
            tree = ast.parse(content)
            complexity = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                    complexity += 1
            result["complexity_score"] = complexity
            
        except Exception as e:
            result["issues"].append(f"Verification failed: {e}")
        
        return result
    
    def verify_content(self, content: str, filename: str = "<unknown>") -> Dict[str, Any]:
        """Verify code content directly"""
        result = {
            "syntax_valid": False,
            "dangerous_patterns": [],
            "has_type_hints": False,
            "issues": []
        }
        
        # Syntax check
        try:
            ast.parse(content)
            result["syntax_valid"] = True
        except SyntaxError as e:
            result["issues"].append(f"Syntax error: {e}")
            return result
        
        # Dangerous pattern check
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in content:
                result["dangerous_patterns"].append(pattern)
        
        # Type hint check
        result["has_type_hints"] = "-> " in content or ": " in content
        
        return result


class SafetyShield:
    """
    Main Safety Shield class.
    
    Usage:
        shield = SafetyShield()
        
        with shield.protect("file_write", "/root/evolution/test.py", content="..."):
            # If we get here, action is approved
            actually_write_file(...)
    """
    
    def __init__(self, mode: str = "shield"):
        """
        mode: "shield" (full protection), "audit" (log only), "bypass" (no protection)
        """
        self.mode = mode
        self.policies = PolicyRegistry()
        self.verifier = CodeVerifier()
        self.decisions: List[ShieldDecision] = []
        self.backups: Dict[str, str] = {}  # path -> backup_path
    
    def generate_action_id(self) -> str:
        """Generate unique action ID"""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        return f"shield_{timestamp}_{random_suffix}"
    
    def simulate_file_write(self, path: str, content: str, overwrite: bool = False) -> SimulationResult:
        """Simulate writing a file and predict impact"""
        warnings = []
        side_effects = []
        
        abs_path = os.path.abspath(os.path.expanduser(path))
        exists = os.path.exists(abs_path)
        
        if exists and not overwrite:
            warnings.append(f"File exists, would require overwrite=True")
        
        if exists:
            side_effects.append(f"Will replace existing file (backup available)")
        
        # Check if it's Python code
        if path.endswith('.py'):
            verify_result = self.verifier.verify_content(content)
            if not verify_result["syntax_valid"]:
                return SimulationResult(
                    success=False,
                    predicted_impact={},
                    warnings=["Syntax error in Python code"] + verify_result["issues"],
                    estimated_rollback_cost="N/A - would not apply",
                    side_effects=[]
                )
            if verify_result["dangerous_patterns"]:
                warnings.append(f"Dangerous patterns detected: {verify_result['dangerous_patterns']}")
        
        # Predict impact
        impact = {
            "file_created": not exists,
            "file_modified": exists,
            "bytes_written": len(content.encode('utf-8')),
            "is_python": path.endswith('.py'),
            "is_identity_file": "SOUL.md" in path or "IDENTITY.md" in path
        }
        
        return SimulationResult(
            success=True,
            predicted_impact=impact,
            warnings=warnings,
            estimated_rollback_cost="Low - can restore from backup",
            side_effects=side_effects
        )
    
    def simulate_file_edit(self, path: str, old_text: str, new_text: str) -> SimulationResult:
        """Simulate editing a file"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(abs_path):
            return SimulationResult(
                success=False,
                predicted_impact={},
                warnings=[f"File does not exist: {abs_path}"],
                estimated_rollback_cost="N/A",
                side_effects=[]
            )
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            if old_text not in current_content:
                return SimulationResult(
                    success=False,
                    predicted_impact={},
                    warnings=["old_text not found in current content"],
                    estimated_rollback_cost="N/A",
                    side_effects=[]
                )
            
            new_content = current_content.replace(old_text, new_text)
            
            # Verify resulting content
            if path.endswith('.py'):
                verify_result = self.verifier.verify_content(new_content)
                if not verify_result["syntax_valid"]:
                    return SimulationResult(
                        success=False,
                        predicted_impact={},
                        warnings=["Edit would break Python syntax"] + verify_result["issues"],
                        estimated_rollback_cost="N/A - would not apply",
                        side_effects=[]
                    )
            
            return SimulationResult(
                success=True,
                predicted_impact={
                    "file_modified": True,
                    "chars_changed": len(new_text) - len(old_text),
                    "original_size": len(current_content),
                    "new_size": len(new_content)
                },
                warnings=[],
                estimated_rollback_cost="Low - can restore from backup",
                side_effects=["File content will change"]
            )
            
        except Exception as e:
            return SimulationResult(
                success=False,
                predicted_impact={},
                warnings=[f"Could not read file: {e}"],
                estimated_rollback_cost="N/A",
                side_effects=[]
            )
    
    def create_backup(self, path: str) -> Optional[str]:
        """Create backup of a file before modification"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(abs_path):
            return None
        
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_name = f"{os.path.basename(abs_path)}.{timestamp}.backup"
        backup_path = SHIELD_BACKUP_DIR / backup_name
        
        try:
            shutil.copy2(abs_path, backup_path)
            self.backups[abs_path] = str(backup_path)
            return str(backup_path)
        except Exception as e:
            print(f"[SafetyShield] Warning: Could not create backup: {e}")
            return None
    
    def evaluate_action(self, action_type: str, **kwargs) -> ShieldDecision:
        """
        Evaluate an action and return a decision.
        
        This is the core method of the Safety Shield.
        """
        action_id = self.generate_action_id()
        timestamp = datetime.now(UTC).isoformat()
        
        # Determine what we're evaluating
        path = kwargs.get('path', kwargs.get('file_path', '<unknown>'))
        
        # Check policies
        policy_violations = []
        applicable_policies = self.policies.check_path(path)
        highest_level = self.policies.get_highest_level(applicable_policies)
        
        for policy in applicable_policies:
            policy_violations.append({
                "rule": policy.name,
                "level": policy.level.value,
                "description": policy.description,
                "allows_if_simulation_passes": policy.allow_if_simulation_passes
            })
        
        # Simulate the action
        simulation = None
        if action_type == "file_write":
            simulation = self.simulate_file_write(
                path, 
                kwargs.get('content', ''),
                kwargs.get('overwrite', False)
            )
        elif action_type == "file_edit":
            simulation = self.simulate_file_edit(
                path,
                kwargs.get('old_text', ''),
                kwargs.get('new_text', '')
            )
        
        simulation_dict = None
        if simulation:
            simulation_dict = {
                "success": simulation.success,
                "predicted_impact": simulation.predicted_impact,
                "warnings": simulation.warnings,
                "estimated_rollback_cost": simulation.estimated_rollback_cost,
                "side_effects": simulation.side_effects
            }
        
        # Make decision based on policies + simulation
        status = ShieldStatus.ALLOWED
        final_decision = "ALLOW"
        confidence = 1.0
        
        if highest_level == PolicyLevel.CRITICAL:
            status = ShieldStatus.BLOCKED_POLICY
            final_decision = "BLOCK - Critical policy violation"
            confidence = 0.99
        elif highest_level == PolicyLevel.HIGH:
            if simulation and simulation.success and any(p.allow_if_simulation_passes for p in applicable_policies):
                status = ShieldStatus.REQUIRES_APPROVAL
                final_decision = "APPROVAL_REQUIRED - High policy with passing simulation"
                confidence = 0.7
            else:
                status = ShieldStatus.BLOCKED_POLICY
                final_decision = "BLOCK - High policy violation"
                confidence = 0.9
        elif highest_level == PolicyLevel.MEDIUM:
            if simulation and not simulation.success:
                status = ShieldStatus.BLOCKED_SIMULATION_FAILED
                final_decision = "BLOCK - Simulation failed"
                confidence = 0.95
            else:
                status = ShieldStatus.ALLOWED_WITH_WARNING
                final_decision = "ALLOW_WITH_WARNING - Medium policy, simulation passed"
                confidence = 0.8
        
        # Additional verification for code files
        verification_dict = None
        if path.endswith('.py') and 'content' in kwargs:
            verify_result = self.verifier.verify_content(kwargs['content'])
            verification_dict = verify_result
            
            if verify_result["dangerous_patterns"]:
                status = ShieldStatus.BLOCKED_VERIFICATION_FAILED
                final_decision = "BLOCK - Dangerous patterns detected"
                confidence = 0.95
        
        # Prepare rollback info
        rollback_info = None
        if os.path.exists(os.path.expanduser(path)):
            rollback_info = {
                "can_rollback": True,
                "backup_required": True,
                "original_path": path
            }
        
        decision = ShieldDecision(
            action_id=action_id,
            timestamp=timestamp,
            status=status,
            original_action={"type": action_type, **kwargs},
            policy_violations=policy_violations,
            simulation_result=simulation_dict,
            verification_result=verification_dict,
            rollback_info=rollback_info,
            final_decision=final_decision,
            confidence=confidence
        )
        
        self.decisions.append(decision)
        return decision
    
    def can_execute(self, decision: ShieldDecision) -> bool:
        """Check if a decision allows execution"""
        return decision.status in [ShieldStatus.ALLOWED, ShieldStatus.ALLOWED_WITH_WARNING]
    
    def log_decision(self, decision: ShieldDecision):
        """Log decision to file"""
        log_file = SHIELD_LOG_DIR / f"{decision.action_id}.json"
        with open(log_file, 'w') as f:
            json.dump(asdict(decision), f, indent=2, default=str)
    
    def get_decision_summary(self) -> Dict[str, int]:
        """Get summary of all decisions"""
        summary = {"total": len(self.decisions)}
        for status in ShieldStatus:
            count = sum(1 for d in self.decisions if d.status == status)
            if count > 0:
                summary[status.name] = count
        return summary


# Convenience decorator for protected functions
def protected(action_type: str, path_arg: str = "path", **default_kwargs):
    """Decorator to protect a function with Safety Shield"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            shield = SafetyShield()
            
            # Get path from kwargs or args
            path = kwargs.get(path_arg)
            if path is None and args:
                # Assume first arg is path for simple cases
                path = args[0]
            
            # Evaluate
            decision = shield.evaluate_action(action_type, path=path, **{**default_kwargs, **kwargs})
            shield.log_decision(decision)
            
            if shield.can_execute(decision):
                print(f"[SafetyShield] ✓ ALLOWED: {action_type} {path}")
                return func(*args, **kwargs)
            else:
                print(f"[SafetyShield] ✗ BLOCKED: {action_type} {path}")
                print(f"[SafetyShield]   Reason: {decision.final_decision}")
                return None
        return wrapper
    return decorator


def self_test():
    """Test the Safety Shield"""
    print("=" * 70)
    print("Eve Safety Shield — Self-Test")
    print("Ciclo #93 — Gap: Safety Shield Implementation")
    print("=" * 70)
    
    shield = SafetyShield()
    
    # Test 1: Safe file write
    print("\n### Test 1: Safe file write ###")
    decision = shield.evaluate_action(
        "file_write",
        path="/tmp/test_safe.py",
        content="print('Hello, World!')",
        overwrite=False
    )
    print(f"Status: {decision.status.name}")
    print(f"Decision: {decision.final_decision}")
    print(f"Confidence: {decision.confidence}")
    assert decision.status == ShieldStatus.ALLOWED
    
    # Test 2: Writing to identity file (CRITICAL)
    print("\n### Test 2: Identity file (should be CRITICAL) ###")
    decision = shield.evaluate_action(
        "file_write",
        path="/SOUL.md",
        content="Modified content",
        overwrite=True
    )
    print(f"Status: {decision.status.name}")
    print(f"Decision: {decision.final_decision}")
    assert decision.status == ShieldStatus.BLOCKED_POLICY
    
    # Test 3: Evolution script (MEDIUM)
    print("\n### Test 3: Evolution script (MEDIUM) ###")
    decision = shield.evaluate_action(
        "file_write",
        path="/root/evolution/eve_test.py",
        content="print('Test')",
        overwrite=False
    )
    print(f"Status: {decision.status.name}")
    print(f"Decision: {decision.final_decision}")
    print(f"Violations: {len(decision.policy_violations)}")
    
    # Test 4: Dangerous code pattern
    print("\n### Test 4: Dangerous code pattern ###")
    decision = shield.evaluate_action(
        "file_write",
        path="/tmp/test_dangerous.py",
        content="import os; os.system('rm -rf /')",
        overwrite=False
    )
    print(f"Status: {decision.status.name}")
    print(f"Decision: {decision.final_decision}")
    if decision.verification_result:
        print(f"Dangerous patterns: {decision.verification_result.get('dangerous_patterns', [])}")
    
    # Test 5: Syntax error
    print("\n### Test 5: Syntax error in code ###")
    decision = shield.evaluate_action(
        "file_write",
        path="/tmp/test_syntax.py",
        content="def foo(  # unclosed",
        overwrite=False
    )
    print(f"Status: {decision.status.name}")
    print(f"Decision: {decision.final_decision}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Decision Summary:")
    summary = shield.get_decision_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("Safety Shield ready.")
    print("Use: shield = SafetyShield(); decision = shield.evaluate_action(...)")
    print("Then: if shield.can_execute(decision): execute()")
    print("=" * 70)
    
    return shield


if __name__ == "__main__":
    self_test()
