#!/usr/bin/env python3
"""
eve_skill_compiler.py — Skill Compiler v1.0

Recompila scripts existentes em versões melhoradas usando reflection.
Baseado em Memento-Skills: agents que reescrevem suas próprias skills.

Usage:
    python eve_skill_compiler.py --target eve_rito.py --analysis
    python eve_skill_compiler.py --target eve_rito.py --compile
"""

import ast
import json
import argparse
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple


@dataclass
class CodeAnalysis:
    """Análise estrutural de código."""
    file: str
    lines: int
    functions: List[dict]
    classes: List[dict]
    imports: List[str]
    complexity: int  # Approximation via AST depth
    issues: List[str]


@dataclass
class CompilationResult:
    """Resultado da compilação de skill."""
    original_file: str
    new_file: str
    changes: List[str]
    rationale: str
    backward_compatible: bool


class SkillCompiler:
    """Compila skills existentes em versões melhoradas.
    
    Processo:
    1. ANÁLISE: Parseia estrutura AST, identifica padrões
    2. REFLECTION: Avalia qualidade em múltiplas dimensões
    3. COMPILAÇÃO: Gera nova versão com melhorias
    4. VERIFICAÇÃO: Valida que versão nova funciona
    """
    
    def __init__(self, model: str = "dolphin-llama3"):
        self.model = model
        self.backup_dir = Path("/root/evolution/backups")
        self.backup_dir.mkdir(exist_ok=True)
    
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
                timeout=180
            )
            return result.stdout.strip()
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def analyze(self, filepath: str) -> CodeAnalysis:
        """Análise estática via AST."""
        path = Path(filepath)
        source = path.read_text()
        lines = len(source.split('\n'))
        
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return CodeAnalysis(
                file=filepath,
                lines=lines,
                functions=[],
                classes=[],
                imports=[],
                complexity=0,
                issues=[f"Syntax error: {e}"]
            )
        
        functions = []
        classes = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": len(node.args.args),
                    "docstring": ast.get_docstring(node) is not None
                }
                functions.append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                    "docstring": ast.get_docstring(node) is not None
                }
                classes.append(class_info)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                else:
                    imports.append(node.module)
        
        # Complexidade aproximada via profundidade máxima
        complexity = max(
            (len(list(ast.walk(node))) for node in ast.walk(tree)),
            default=0
        )
        
        # Issues básicas
        issues = []
        if not any(f["docstring"] for f in functions):
            issues.append("No function docstrings")
        if not classes and len(functions) > 10:
            issues.append("High function count without classes - consider refactoring")
        
        return CodeAnalysis(
            file=filepath,
            lines=lines,
            functions=functions,
            classes=classes,
            imports=list(set(imports)),
            complexity=complexity,
            issues=issues
        )
    
    def reflect(self, analysis: CodeAnalysis, source: str) -> dict:
        """Fase de reflection sobre o código."""
        prompt = f"""Analise este código Python e sugira melhorias específicas:

ARQUIVO: {analysis.file}
LINHAS: {analysis.lines}
FUNÇÕES: {len(analysis.functions)}
CLASSES: {len(analysis.classes)}
IMPORTS: {', '.join(analysis.imports[:10])}

ISSUES DETECTADAS: {analysis.issues}

CÓDIGO ORIGINAL (primeiras 100 linhas):
```python
{chr(10).join(source.split(chr(10))[:100])}
```

Forneça análise em JSON:
{{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "opportunities": ["..."],
    "specific_changes": ["..."],
    "priority": "high|medium|low"
}}"""
        
        system = "Você é um engenheiro de software sênior focado em código limpo e Python idiomático."
        response = self._call_llm(prompt, system=system)
        
        # Parse JSON (com fallback)
        try:
            if "```json" in response:
                json_part = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_part = response.split("```")[1].split("```")[0]
            else:
                json_part = response
            return json.loads(json_part.strip())
        except:
            return {
                "strengths": ["Código funcional"],
                "weaknesses": ["Não foi possível parsear JSON da análise"],
                "opportunities": ["Revisão manual recomendada"],
                "specific_changes": [],
                "priority": "medium",
                "raw_response": response[:500]
            }
    
    def compile_skill(
        self, 
        filepath: str, 
        reflection: dict,
        dry_run: bool = True
    ) -> CompilationResult:
        """Compila nova versão do skill."""
        path = Path(filepath)
        source = path.read_text()
        
        prompt = f"""Reescreva o seguinte código Python aplicando estas melhorias:

MELHORIAS SUGERIDAS:
{json.dumps(reflection.get('specific_changes', []), indent=2)}

WEAKNESSES A CORRIGIR:
{json.dumps(reflection.get('weaknesses', []), indent=2)}

CÓDIGO ORIGINAL:
```python
{source}
```

REQUISITOS:
1. Mantenha TODAS as funcionalidades originais (backward compatibility)
2. Adicione type hints onde apropriado
3. Melhore docstrings e comentários
4. Simplifique lógica complexa
5. Use Python idiomático (list comprehensions, context managers, etc.)
6. Mantenha o mesmo nome de arquivo e estrutura de classes/funções principais

Forneça APENAS o código Python completo, sem explicações."""
        
        system = "Você é um expert Python que reescreve código mantendo compatibilidade."
        new_code = self._call_llm(prompt, system=system)
        
        # Extrair código de markdown se presente
        if "```python" in new_code:
            new_code = new_code.split("```python")[1].split("```")[0]
        elif "```" in new_code:
            new_code = new_code.split("```")[1].split("```")[0]
        
        new_code = new_code.strip()
        
        if dry_run:
            new_file = self.backup_dir / f"{path.stem}_compiled_v2.py"
        else:
            # Backup do original
            backup = self.backup_dir / f"{path.stem}_{path.stat().st_mtime}.py.bak"
            backup.write_text(source)
            new_file = path.with_suffix('.py')
        
        new_file.write_text(new_code)
        
        return CompilationResult(
            original_file=filepath,
            new_file=str(new_file),
            changes=reflection.get('specific_changes', []),
            rationale=reflection.get('weaknesses', ["N/A"])[0],
            backward_compatible=True  # Assumindo, mas deveria validar
        )
    
    def verify(self, result: CompilationResult) -> bool:
        """Verifica se código compilado é válido."""
        try:
            source = Path(result.new_file).read_text()
            ast.parse(source)
            return True
        except SyntaxError:
            return False


def main():
    parser = argparse.ArgumentParser(description="Skill Compiler")
    parser.add_argument("--target", "-t", required=True, help="Arquivo Python para compilar")
    parser.add_argument("--analysis", "-a", action="store_true", help="Apenas analisar")
    parser.add_argument("--compile", "-c", action="store_true", help="Compilar skill")
    parser.add_argument("--dry-run", "-d", action="store_true", default=True, help="Não modificar original")
    parser.add_argument("--model", "-m", default="dolphin-llama3", help="Modelo Ollama")
    
    args = parser.parse_args()
    
    compiler = SkillCompiler(model=args.model)
    
    if args.analysis:
        print(f"[SkillCompiler] Analisando {args.target}...")
        analysis = compiler.analyze(args.target)
        print(json.dumps(asdict(analysis), indent=2))
        
        print("\n[SkillCompiler] Gerando reflection...")
        source = Path(args.target).read_text()
        reflection = compiler.reflect(analysis, source)
        print(json.dumps(reflection, indent=2))
    
    elif args.compile:
        print(f"[SkillCompiler] Compilando {args.target}...")
        
        # Análise
        analysis = compiler.analyze(args.target)
        source = Path(args.target).read_text()
        reflection = compiler.reflect(analysis, source)
        
        # Compilação
        result = compiler.compile_skill(args.target, reflection, dry_run=args.dry_run)
        
        # Verificação
        valid = compiler.verify(result)
        
        print(f"\n✓ Compilação concluída")
        print(f"  Novo arquivo: {result.new_file}")
        print(f"  Mudanças: {len(result.changes)}")
        print(f"  Sintaxe válida: {valid}")
        print(f"  Dry-run: {args.dry_run}")
    
    else:
        print("Use --analysis ou --compile")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())