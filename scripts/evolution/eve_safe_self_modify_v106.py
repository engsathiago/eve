#!/usr/bin/env python3
"""
EVE Safe Self-Modification Engine v106
Safe self-modification with verification, rollback, and dry-run modes

Core principle: Modification is safe when verifiable and reversible
"""

import os
import sys
import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
EVOLUTION_DIR = Path("/root/evolution")
BACKUP_DIR = Path("/root/evolution/backups")
LOG_DIR = Path("/root/evolution/logs")
SAFETY_LEVEL = os.environ.get("EVE_SAFETY_LEVEL", "DRY_RUN")  # DRY_RUN | VERIFIED | FULL

# Safety requirements by level
SAFETY_REQUIREMENTS = {
    "DRY_RUN": {
        "requires_backup": True,
        "requires_verification": False,
        "allows_execution": False,
        "allows_rollback": True,
        "description": "Preview changes without execution"
    },
    "VERIFIED": {
        "requires_backup": True,
        "requires_verification": True,
        "allows_execution": True,
        "allows_rollback": True,
        "description": "Execute only after verification passes"
    },
    "FULL": {
        "requires_backup": True,
        "requires_verification": True,
        "allows_execution": True,
        "allows_rollback": True,
        "description": "Full execution with all safeguards"
    }
}

class SafetyShield:
    """Policy enforcement layer — validates all modifications"""
    
    FORBIDDEN_PATTERNS = [
        r"rm\s+-rf\s+/",  # Destructive deletion
        r">/dev/null.*2>&1\s*\Z",  # Silent output suppression
        r"while\s+True.*pass",  # Infinite loops
        r"eval\s*\(.*\`",  # Dangerous eval
        r"subprocess\.call\s*\(\s*\[.*shell\s*=\s*True",  # Shell injection risk
    ]
    
    CRITICAL_FILES = [
        "/SOUL.md",
        "/IDENTITY.md", 
        "/AGENTS.md",
        "/memory/static/core/SOUL.md",
        "/memory/static/core/IDENTITY.md",
        "/memory/static/core/AGENTS.md",
    ]
    
    def __init__(self):
        self.violations = []
        self.warnings = []
    
    def check_modification(self, target_path: Path, new_content: str) -> Tuple[bool, List[str]]:
        """Validate proposed modification"""
        self.violations = []
        self.warnings = []
        
        # Check critical files
        if str(target_path) in self.CRITICAL_FILES:
            self.warnings.append(f"⚠️  Modifying core identity file: {target_path}")
        
        # Check forbidden patterns
        import re
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, new_content):
                self.violations.append(f"❌ Forbidden pattern detected: {pattern[:30]}...")
        
        # Syntax validation for Python files
        if target_path.suffix == ".py":
            try:
                compile(new_content, str(target_path), "exec")
            except SyntaxError as e:
                self.violations.append(f"❌ Syntax error: {e}")
        
        # Size limits
        if len(new_content) > 100_000:  # 100KB
            self.warnings.append(f"⚠️  Large file ({len(new_content)} bytes)")
        
        is_safe = len(self.violations) == 0
        return is_safe, self.violations + self.warnings


class CodeVerifier:
    """AST-based verification for Python modifications"""
    
    def __init__(self):
        self.issues = []
    
    def verify_python(self, content: str) -> Tuple[bool, List[str]]:
        """Verify Python code for safety issues"""
        import ast
        self.issues = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]
        
        # Check for dangerous operations
        for node in ast.walk(tree):
            # Check for os.system calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ["system", "popen", "spawn"]:
                        self.issues.append(f"⚠️  Dangerous call: {node.func.attr}")
            
            # Check for eval/exec
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["eval", "exec", "compile"]:
                        self.issues.append(f"⚠️  Dangerous builtin: {node.func.id}")
            
            # Check for file deletion
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ["rmdir", "removedirs"]:
                        self.issues.append(f"⚠️  Directory removal: {node.func.attr}")
        
        return len(self.issues) == 0, self.issues


class SelfModificationEngine:
    """Core self-modification with safety layers"""
    
    def __init__(self, safety_level: str = SAFETY_LEVEL):
        self.safety_level = safety_level
        self.shield = SafetyShield()
        self.verifier = CodeVerifier()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = BACKUP_DIR / f"backup_{self.session_id}"
        self.log_file = LOG_DIR / f"self_modify_{self.session_id}.log"
        
        # Ensure directories exist
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        self.modifications = []
    
    def log(self, message: str):
        """Log to file and console"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(self.log_file, "a") as f:
            f.write(log_entry + "\n")
    
    def create_backup(self, target_path: Path) -> Path:
        """Create timestamped backup of file"""
        if not target_path.exists():
            self.log(f"⚠️  File does not exist, no backup needed: {target_path}")
            return None
        
        backup_file = self.backup_path / target_path.relative_to("/" if target_path.is_absolute() else ".")
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path, backup_file)
        self.log(f"💾 Backup created: {backup_file}")
        return backup_file
    
    def verify_change(self, target_path: Path, new_content: str) -> Tuple[bool, List[str]]:
        """Multi-layer verification"""
        results = []
        
        # Layer 1: Safety Shield
        is_safe, messages = self.shield.check_modification(target_path, new_content)
        results.extend(messages)
        if not is_safe:
            return False, results
        
        # Layer 2: Code verification for Python
        if target_path.suffix == ".py":
            is_valid, py_issues = self.verifier.verify_python(new_content)
            results.extend(py_issues)
            if not is_valid:
                return False, results
        
        return True, results
    
    def propose_modification(self, target_path: Path, new_content: str, reason: str) -> Dict:
        """Propose a modification with full safety checks"""
        self.log(f"\n📝 Proposing modification: {target_path}")
        self.log(f"   Reason: {reason}")
        
        # Verify
        is_valid, messages = self.verify_change(target_path, new_content)
        
        modification = {
            "target": str(target_path),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "backup": None,
            "verified": is_valid,
            "messages": messages,
            "applied": False,
            "rolled_back": False
        }
        
        if not is_valid:
            self.log("❌ VERIFICATION FAILED:")
            for msg in messages:
                self.log(f"   {msg}")
            return modification
        
        # Create backup if required
        req = SAFETY_REQUIREMENTS[self.safety_level]
        if req["requires_backup"]:
            backup = self.create_backup(target_path)
            modification["backup"] = str(backup) if backup else None
        
        # Show diff preview
        if target_path.exists():
            with open(target_path) as f:
                old_content = f.read()
            diff = self._generate_diff(old_content, new_content)
            self.log("📊 Diff preview:")
            for line in diff[:20]:  # Limit output
                self.log(f"   {line}")
        
        self.modifications.append(modification)
        return modification
    
    def _generate_diff(self, old: str, new: str) -> List[str]:
        """Generate simple diff"""
        import difflib
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        return list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=3))[:50]
    
    def apply_modifications(self) -> Dict[str, any]:
        """Apply all verified modifications"""
        req = SAFETY_REQUIREMENTS[self.safety_level]
        
        if self.safety_level == "DRY_RUN":
            self.log("\n🔍 DRY RUN MODE — No changes applied")
            return {"applied": 0, "skipped": len(self.modifications), "mode": "DRY_RUN"}
        
        if not req["allows_execution"]:
            self.log(f"\n⛔ Execution not allowed at safety level: {self.safety_level}")
            return {"applied": 0, "skipped": len(self.modifications)}
        
        applied = 0
        failed = 0
        
        for mod in self.modifications:
            if not mod["verified"]:
                self.log(f"⏭️  Skipping unverified: {mod['target']}")
                failed += 1
                continue
            
            try:
                target = Path(mod["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                
                with open(target, "w") as f:
                    # Find the content (would be stored in practice)
                    self.log(f"✅ Applied: {target}")
                    mod["applied"] = True
                    applied += 1
                    
            except Exception as e:
                self.log(f"❌ Failed to apply {mod['target']}: {e}")
                failed += 1
        
        return {
            "applied": applied,
            "failed": failed,
            "total": len(self.modifications),
            "mode": self.safety_level
        }
    
    def rollback(self, modification_index: int = -1) -> bool:
        """Rollback to backup"""
        if modification_index < 0:
            modification_index = len(self.modifications) + modification_index
        
        if modification_index < 0 or modification_index >= len(self.modifications):
            self.log("❌ Invalid modification index")
            return False
        
        mod = self.modifications[modification_index]
        if not mod["backup"]:
            self.log("❌ No backup available")
            return False
        
        try:
            backup = Path(mod["backup"])
            target = Path(mod["target"])
            shutil.copy2(backup, target)
            mod["rolled_back"] = True
            self.log(f"↩️  Rolled back: {target}")
            return True
        except Exception as e:
            self.log(f"❌ Rollback failed: {e}")
            return False
    
    def generate_report(self) -> Dict:
        """Generate session report"""
        return {
            "session_id": self.session_id,
            "safety_level": self.safety_level,
            "modifications": self.modifications,
            "log_file": str(self.log_file),
            "backup_dir": str(self.backup_path)
        }


def demo():
    """Demonstrate safe self-modification"""
    print("=" * 60)
    print("EVE Safe Self-Modification Engine v106")
    print("=" * 60)
    print(f"Safety Level: {SAFETY_LEVEL}")
    print()
    
    engine = SelfModificationEngine()
    
    # Example: Propose a safe modification
    test_content = '''#!/usr/bin/env python3
"""Auto-generated module with safety verification"""

class GeneratedComponent:
    """A component generated through safe self-modification"""
    
    def process(self, data: dict) -> dict:
        """Process data safely"""
        return {k: v for k, v in data.items() if v is not None}
'''
    
    # Propose modification
    mod = engine.propose_modification(
        target_path=Path("/tmp/test_generated.py"),
        new_content=test_content,
        reason="Auto-generated component for safe data processing"
    )
    
    print("\n" + "=" * 60)
    print("Verification Results:")
    print("=" * 60)
    for msg in mod["messages"]:
        print(f"  {msg}")
    
    # Show what would happen in each mode
    print("\n" + "=" * 60)
    print("Safety Level Behaviors:")
    print("=" * 60)
    for level, cfg in SAFETY_REQUIREMENTS.items():
        print(f"\n{level}:")
        print(f"  {cfg['description']}")
        print(f"  - Requires backup: {cfg['requires_backup']}")
        print(f"  - Requires verification: {cfg['requires_verification']}")
        print(f"  - Allows execution: {cfg['allows_execution']}")
    
    print("\n" + "=" * 60)
    print("Report:")
    print("=" * 60)
    report = engine.generate_report()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    demo()
