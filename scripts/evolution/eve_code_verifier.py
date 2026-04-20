#!/usr/bin/env python3
"""
eve_code_verifier.py — Auto-verificação de qualidade de código

Sistema de análise estática para scripts Eve. Avalia:
- Sintaxe e bugs potenciais (via ast)
- Complexidade ciclomática
- Imports não utilizados
- Type hints coverage
- Documentação (docstrings)
- Adesão a padrões Eve

Uso: python3 eve_code_verifier.py <script_path> [--strict]
"""

import ast
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class VerificationResult:
    """Resultado completo da verificação de um arquivo."""
    file_path: str
    score: float  # 0-100
    passed: bool
    
    # Métricas individuais
    syntax_valid: bool
    complexity_score: float  # 0-100, maior é melhor (menos complexo)
    imports_score: float  # 0-100
    types_score: float  # 0-100
    docs_score: float  # 0-100
    patterns_score: float  # 0-100
    
    # Detalhes
    issues: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'file_path': self.file_path,
            'score': round(self.score, 2),
            'passed': self.passed,
            'metrics': {
                'syntax': self.syntax_valid,
                'complexity': round(self.complexity_score, 2),
                'imports': round(self.imports_score, 2),
                'types': round(self.types_score, 2),
                'docs': round(self.docs_score, 2),
                'patterns': round(self.patterns_score, 2),
            },
            'issues': self.issues,
            'warnings': self.warnings,
        }


class CodeVerifier:
    """Motor de verificação de código Eve."""
    
    # Thresholds de complexidade ciclomática
    CC_THRESHOLDS = {
        'simple': 10,      # Verde
        'moderate': 20,    # Amarelo
        'complex': 50,     # Vermelho
    }
    
    # Padrões esperados em scripts Eve
    EVE_PATTERNS = {
        'header_shebang': r'^#!/usr/bin/env python3',
        'header_encoding': r'coding[:=]\s*([-\w.]+)',
        'docstring_module': r'^(\"\"\"|\'\'\')[\s\S]*?\1',
        'eve_prefix': r'^eve_',
        'version_marker': r'v\d+\.?\d*',
        'memory_integration': r'(chroma|memory|chromadb)',
        'logging_pattern': r'(logging|log\.getLogger)',
    }
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.issues: List[Dict] = []
        self.warnings: List[str] = []
    
    def verify(self, file_path: str) -> VerificationResult:
        """Executa verificação completa em um arquivo."""
        self.issues = []
        self.warnings = []
        
        path = Path(file_path)
        if not path.exists():
            return self._error_result(file_path, f"Arquivo não encontrado: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        
        # 1. Verificação de sintaxe
        syntax_valid, syntax_error = self._check_syntax(content)
        if not syntax_valid:
            return self._error_result(file_path, f"Erro de sintaxe: {syntax_error}")
        
        # Parse AST para análises posteriores
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return self._error_result(file_path, f"Erro de parse AST: {e}")
        
        # 2. Análise de complexidade
        complexity_score = self._analyze_complexity(tree)
        
        # 3. Análise de imports
        imports_score = self._analyze_imports(tree, content)
        
        # 4. Análise de type hints
        types_score = self._analyze_type_hints(tree, content)
        
        # 5. Análise de documentação
        docs_score = self._analyze_documentation(tree, content)
        
        # 6. Verificação de padrões Eve
        patterns_score = self._analyze_eve_patterns(content, path.name)
        
        # Cálculo de score final
        weights = {
            'complexity': 0.25,
            'imports': 0.15,
            'types': 0.20,
            'docs': 0.20,
            'patterns': 0.20,
        }
        
        final_score = (
            complexity_score * weights['complexity'] +
            imports_score * weights['imports'] +
            types_score * weights['types'] +
            docs_score * weights['docs'] +
            patterns_score * weights['patterns']
        )
        
        # Threshold de aprovação
        threshold = 70.0 if not self.strict else 80.0
        passed = final_score >= threshold and not any(
            i['severity'] == 'error' for i in self.issues
        )
        
        return VerificationResult(
            file_path=file_path,
            score=final_score,
            passed=passed,
            syntax_valid=True,
            complexity_score=complexity_score,
            imports_score=imports_score,
            types_score=types_score,
            docs_score=docs_score,
            patterns_score=patterns_score,
            issues=self.issues,
            warnings=self.warnings,
        )
    
    def _check_syntax(self, content: str) -> Tuple[bool, Optional[str]]:
        """Verifica se o código é sintaticamente válido."""
        try:
            compile(content, '<string>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, str(e)
    
    def _analyze_complexity(self, tree: ast.AST) -> float:
        """Calcula complexidade ciclomática média e score."""
        complexities = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = self._calculate_cyclomatic_complexity(node)
                complexities.append((node.name, cc))
        
        if not complexities:
            return 100.0  # Nenhuma função = score perfeito (módulo simples)
        
        avg_cc = sum(cc for _, cc in complexities) / len(complexities)
        max_cc = max(cc for _, cc in complexities)
        
        # Registrar funções complexas
        for name, cc in complexities:
            if cc > self.CC_THRESHOLDS['complex']:
                self.issues.append({
                    'type': 'complexity',
                    'severity': 'error',
                    'message': f"Função '{name}' tem CC={cc} (muito complexa)",
                })
            elif cc > self.CC_THRESHOLDS['moderate']:
                self.issues.append({
                    'type': 'complexity',
                    'severity': 'warning',
                    'message': f"Função '{name}' tem CC={cc} (moderadamente complexa)",
                })
        
        # Score baseado na média (menor CC = melhor)
        if avg_cc <= 5:
            return 100.0
        elif avg_cc <= 10:
            return 90.0
        elif avg_cc <= 15:
            return 75.0
        elif avg_cc <= 25:
            return 60.0
        else:
            return 40.0
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Calcula CC para uma função."""
        # CC = 1 (base) + número de decision points
        cc = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                cc += 1
            elif isinstance(child, ast.BoolOp):
                cc += len(child.values) - 1
            elif isinstance(child, (ast.And, ast.Or)):
                pass  # Já contado em BoolOp
        
        return cc
    
    def _analyze_imports(self, tree: ast.AST, content: str) -> float:
        """Analisa imports não utilizados."""
        imports = {}
        used_names = set()
        
        for node in ast.walk(tree):
            # Import regular
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name] = alias.name
            # Import from
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = f"{module}.{alias.name}"
            # Nomes usados
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
        
        # Verificar imports não utilizados (exceto __future__)
        unused = []
        for name, full_name in imports.items():
            if name not in used_names and not full_name.startswith('__future__'):
                unused.append(name)
        
        if unused:
            self.warnings.append(f"Imports não utilizados: {unused}")
        
        # Score
        total_imports = len(imports)
        if total_imports == 0:
            return 100.0
        
        unused_ratio = len(unused) / total_imports
        return max(0, 100 - (unused_ratio * 100))
    
    def _analyze_type_hints(self, tree: ast.AST, content: str) -> float:
        """Analisa cobertura de type hints."""
        total_functions = 0
        typed_functions = 0
        typed_args = 0
        total_args = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_functions += 1
                
                # Return type annotation
                if node.returns is not None:
                    typed_functions += 1
                
                # Argument type annotations
                for arg in node.args.args + node.args.posonlyargs:
                    total_args += 1
                    if arg.annotation is not None:
                        typed_args += 1
                
                # *args e **kwargs
                if node.args.vararg and node.args.vararg.annotation:
                    typed_args += 1
                if node.args.kwarg and node.args.kwarg.annotation:
                    typed_args += 1
        
        if total_functions == 0:
            return 100.0
        
        # Calcular cobertura
        return_annotation_coverage = typed_functions / total_functions
        arg_annotation_coverage = typed_args / total_args if total_args > 0 else 1.0
        
        coverage = (return_annotation_coverage * 0.4) + (arg_annotation_coverage * 0.6)
        
        if coverage >= 0.9:
            return 100.0
        elif coverage >= 0.7:
            return 85.0
        elif coverage >= 0.5:
            return 65.0
        elif coverage >= 0.3:
            return 45.0
        else:
            return 25.0
    
    def _analyze_documentation(self, tree: ast.AST, content: str) -> float:
        """Analisa presença de docstrings."""
        total_funcs = 0
        documented_funcs = 0
        
        # Module docstring
        has_module_docstring = False
        if tree.body and isinstance(tree.body[0], ast.Expr):
            if isinstance(tree.body[0].value, (ast.Str, ast.Constant)):
                has_module_docstring = True
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_funcs += 1
                if ast.get_docstring(node):
                    documented_funcs += 1
        
        if total_funcs == 0:
            return 100.0 if has_module_docstring else 50.0
        
        func_coverage = documented_funcs / total_funcs
        
        # Module docstring vale 20% do score
        module_score = 20 if has_module_docstring else 0
        func_score = func_coverage * 80
        
        return module_score + func_score
    
    def _analyze_eve_patterns(self, content: str, filename: str) -> float:
        """Verifica adesão a padrões Eve."""
        checks = []
        
        # 1. Nome segue padrão eve_*.py
        if re.match(self.EVE_PATTERNS['eve_prefix'], filename):
            checks.append(('nome_eve_prefix', True, 15))
        else:
            checks.append(('nome_eve_prefix', False, 15))
            self.warnings.append("Nome do arquivo não segue padrão eve_*.py")
        
        # 2. Shebang presente
        if re.search(self.EVE_PATTERNS['header_shebang'], content, re.MULTILINE):
            checks.append(('shebang', True, 15))
        else:
            checks.append(('shebang', False, 15))
        
        # 3. Docstring do módulo
        if re.search(self.EVE_PATTERNS['docstring_module'], content, re.MULTILINE):
            checks.append(('module_docstring', True, 20))
        else:
            checks.append(('module_docstring', False, 20))
        
        # 4. Version marker no docstring ou comentários
        if re.search(self.EVE_PATTERNS['version_marker'], content):
            checks.append(('version_marker', True, 10))
        else:
            checks.append(('version_marker', False, 10))
        
        # 5. Integração com memória (ChromaDB ou sistema de memória)
        if re.search(self.EVE_PATTERNS['memory_integration'], content, re.IGNORECASE):
            checks.append(('memory_integration', True, 20))
        else:
            checks.append(('memory_integration', False, 20))
            self.warnings.append("Script não integra com sistema de memória Eve")
        
        # 6. Logging configurado
        if re.search(self.EVE_PATTERNS['logging_pattern'], content):
            checks.append(('logging', True, 20))
        else:
            checks.append(('logging', False, 20))
            self.warnings.append("Logging não configurado (recomendado)")
        
        score = sum(passed * points for _, passed, points in checks)
        return score
    
    def _error_result(self, file_path: str, error_msg: str) -> VerificationResult:
        """Cria resultado de erro."""
        return VerificationResult(
            file_path=file_path,
            score=0.0,
            passed=False,
            syntax_valid=False,
            complexity_score=0.0,
            imports_score=0.0,
            types_score=0.0,
            docs_score=0.0,
            patterns_score=0.0,
            issues=[{'type': 'syntax', 'severity': 'error', 'message': error_msg}],
            warnings=[],
        )


def verify_batch(directory: str, pattern: str = "eve_*.py", strict: bool = False) -> Dict:
    """Verifica todos os arquivos correspondentes em um diretório."""
    import glob
    
    verifier = CodeVerifier(strict=strict)
    results = []
    
    files = glob.glob(f"{directory}/{pattern}")
    
    for file_path in files:
        result = verifier.verify(file_path)
        results.append(result.to_dict())
    
    # Estatísticas
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    avg_score = sum(r['score'] for r in results) / total if total > 0 else 0
    
    return {
        'total_files': total,
        'passed': passed,
        'failed': total - passed,
        'average_score': round(avg_score, 2),
        'pass_rate': round((passed / total * 100) if total > 0 else 0, 2),
        'results': results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Eve Code Verifier - Análise estática de qualidade de código'
    )
    parser.add_argument('target', help='Arquivo ou diretório para verificar')
    parser.add_argument('--strict', action='store_true', 
                        help='Modo estrito (threshold 80 ao invés de 70)')
    parser.add_argument('--batch', action='store_true',
                        help='Verificar todos os arquivos eve_*.py no diretório')
    parser.add_argument('--json', action='store_true',
                        help='Saída em formato JSON')
    
    args = parser.parse_args()
    
    target = Path(args.target)
    
    if args.batch or target.is_dir():
        results = verify_batch(str(target), strict=args.strict)
        
        if args.json:
            import json
            print(json.dumps(results, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"EVE CODE VERIFIER — Batch Results")
            print(f"{'='*60}")
            print(f"Arquivos analisados: {results['total_files']}")
            print(f"Aprovados: {results['passed']}")
            print(f"Reprovados: {results['failed']}")
            print(f"Taxa de aprovação: {results['pass_rate']}%")
            print(f"Score médio: {results['average_score']}/100")
            print(f"{'='*60}\n")
            
            for r in results['results']:
                status = "✅ PASS" if r['passed'] else "❌ FAIL"
                print(f"{status} | {r['score']:5.1f}/100 | {r['file_path']}")
    else:
        verifier = CodeVerifier(strict=args.strict)
        result = verifier.verify(str(target))
        
        if args.json:
            import json
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"EVE CODE VERIFIER — Single File")
            print(f"{'='*60}")
            print(f"Arquivo: {result.file_path}")
            print(f"Score: {result.score:.1f}/100")
            print(f"Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
            print(f"{'='*60}\n")
            
            print("Métricas:")
            print(f"  Sintaxe:     {'✅ OK' if result.syntax_valid else '❌ Erro'}")
            print(f"  Complexidade: {result.complexity_score:.1f}/100")
            print(f"  Imports:      {result.imports_score:.1f}/100")
            print(f"  Type Hints:   {result.types_score:.1f}/100")
            print(f"  Docs:         {result.docs_score:.1f}/100")
            print(f"  Padrões Eve:  {result.patterns_score:.1f}/100")
            
            if result.issues:
                print(f"\n❌ Issues ({len(result.issues)}):")
                for issue in result.issues:
                    severity = "🔴" if issue['severity'] == 'error' else "🟡"
                    print(f"  {severity} [{issue['type']}] {issue['message']}")
            
            if result.warnings:
                print(f"\n⚠️  Warnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  • {warning}")
            
            print()


if __name__ == '__main__':
    main()
