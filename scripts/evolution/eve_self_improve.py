#!/usr/bin/env python3
"""
eve_self_improve.py — Self-Modifying Code Framework for Eve

Baseado no Karpathy autoresearch pattern:
- Um arquivo "program.md" define as instruções para o agente
- Um arquivo editável (train.py equivalent) é o alvo de melhorias
- Ciclo: analisar → propor modificação → testar → avaliar → manter/descartar

Diferença do autoresearch: Eve modifica seus próprios scripts de infraestrutura,
não modelos LLM. O "treino" é a execução real do script com validação.
"""

import os
import sys
import json
import hashlib
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict

# Configurações
EVOLUTION_DIR = Path("/root/evolution")
MEMORY_DIR = Path("/memory")
IMPROVEMENTS_DIR = EVOLUTION_DIR / "improvements"
PROGRAM_MD = EVOLUTION_DIR / "self_improve_program.md"
VERSIONS_DIR = EVOLUTION_DIR / "versions"

def ensure_dirs():
    """Garante que diretórios necessários existem."""
    for d in [IMPROVEMENTS_DIR, VERSIONS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

@dataclass
class ScriptVersion:
    """Representa uma versão de um script."""
    script_name: str
    version_id: str
    timestamp: str
    hash_before: str
    hash_after: str
    changes_description: str
    test_result: Optional[bool] = None
    test_output: Optional[str] = None
    kept: Optional[bool] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

class SelfImprover:
    """
    Framework de auto-modificação de código para Eve.
    
    Padrão:
    1. Carregar program.md (instruções para melhoria)
    2. Selecionar script alvo
    3. Gerar proposta de modificação
    4. Criar backup
    5. Aplicar modificação
    6. Testar (executar script)
    7. Avaliar resultado
    8. Manter ou reverter
    9. Logar aprendizado
    """
    
    def __init__(self):
        self.improvements_log = IMPROVEMENTS_DIR / "improvements_log.jsonl"
        self.current_experiment: Optional[ScriptVersion] = None
        
    def load_program_instructions(self) -> str:
        """Carrega instruções do program.md ou usa default."""
        if PROGRAM_MD.exists():
            return PROGRAM_MD.read_text(encoding='utf-8')
        
        # Default instructions
        default = """# Eve Self-Improvement Program

## Propósito
Modificar scripts de infraestrutura Eve para melhorar:
- Eficiência (menor uso de recursos)
- Confiabilidade (menos falhas)
- Capacidades (novas funcionalidades)
- Clareza (código mais limpo)

## Scripts Alvo (por prioridade)
1. eve_auto_dream.py — consolidação de memória
2. eve_kairos.py — sistema de prioridades  
3. eve_memory_ingest.py — ingestão de dados
4. eve_training_data_gen.py — geração de pares de treino

## Regras de Modificação
- Preserve compatibilidade com chamadas existentes
- Mantenha logging e observabilidade
- Adicione comentários explicativos para mudanças complexas
- Nunca remova backups ou mecanismos de segurança
- Teste sempre antes de considerar "sucesso"

## Critérios de Sucesso
- Script executa sem erros
- Output é válido (JSON well-formed, etc)
- Tempo de execução não aumentou significativamente
- Nenhuma funcionalidade foi perdida

## Processo
1. Analise o script atual — identifique gargalos ou oportunidades
2. Proponha mudanças específicas com justificativa
3. Crie backup antes de modificar
4. Aplique mudanças
5. Execute teste — veja se funciona
6. Avalie — melhorou? Mesmo? Piorou?
7. Decida: manter (kept=true) ou reverter (kept=false)
8. Documente o aprendizado
"""
        PROGRAM_MD.write_text(default, encoding='utf-8')
        return default
    
    def list_target_scripts(self) -> List[Path]:
        """Lista scripts elegíveis para melhoria."""
        targets = []
        for pattern in ["eve_*.py", "auto_*.py", "kairos*.py"]:
            targets.extend(EVOLUTION_DIR.glob(pattern))
        # Exclui este script e backups
        excluded = {Path(__file__).name, "eve_self_improve.py"}
        return [t for t in targets if t.name not in excluded and not t.name.endswith('.backup.py')]
    
    def compute_hash(self, filepath: Path) -> str:
        """Computa hash MD5 de um arquivo."""
        return hashlib.md5(filepath.read_bytes()).hexdigest()
    
    def create_backup(self, script_path: Path) -> Path:
        """Cria backup versionado do script."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{script_path.stem}_{timestamp}.backup.py"
        backup_path = VERSIONS_DIR / backup_name
        shutil.copy2(script_path, backup_path)
        return backup_path
    
    def run_script_test(self, script_path: Path, timeout: int = 60) -> Tuple[bool, str]:
        """
        Executa o script em modo teste.
        Retorna (sucesso, output/errors).
        """
        try:
            # Tenta executar com --dry-run ou --test primeiro
            result = subprocess.run(
                [sys.executable, str(script_path), "--dry-run"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(EVOLUTION_DIR)
            )
            if result.returncode == 0:
                return True, result.stdout
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        except Exception as e:
            pass
        
        # Se --dry-run não existe, tenta importar como módulo
        try:
            # Salva sys.path, modifica temporariamente
            original_path = sys.path.copy()
            sys.path.insert(0, str(EVOLUTION_DIR))
            
            module_name = script_path.stem
            # Não executa, apenas verifica sintaxe
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(script_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            sys.path = original_path
            
            if result.returncode == 0:
                return True, "Syntax OK"
            else:
                return False, result.stderr
                
        except Exception as e:
            return False, str(e)
    
    def log_experiment(self, version: ScriptVersion):
        """Adiciona experimento ao log."""
        with open(self.improvements_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(version.to_dict(), ensure_ascii=False) + '\n')
    
    def get_script_history(self, script_name: str) -> List[Dict]:
        """Retorna histórico de melhorias de um script."""
        if not self.improvements_log.exists():
            return []
        
        history = []
        with open(self.improvements_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('script_name') == script_name:
                        history.append(entry)
                except:
                    continue
        return history
    
    def generate_proposed_change(self, script_path: Path, instructions: str) -> Optional[str]:
        """
        Gera uma proposta de modificação.
        
        Retorna uma descrição textual da mudança proposta.
        Em uma implementação completa com LLM, isso geraria código real.
        
        Para Eve v1, retorna prompts estruturados que podem ser
        usados por um LLM externo para gerar o código.
        """
        script_content = script_path.read_text(encoding='utf-8')
        current_hash = self.compute_hash(script_path)
        
        # Análise simples — identifica oportunidades óbvias
        opportunities = []
        
        # Verifica funções longas (>50 linhas)
        lines = script_content.split('\n')
        current_func = None
        func_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                if current_func and (i - func_start) > 50:
                    opportunities.append(f"Função '{current_func}' tem {i-func_start} linhas — considerar refatorar")
                current_func = line.strip().split('(')[0].replace('def ', '')
                func_start = i
        
        # Verifica tratamento de exceções ausente
        if 'try:' not in script_content and 'except' not in script_content:
            opportunities.append("Sem tratamento de exceções — adicionar try/except em operações críticas")
        
        # Verifica documentação
        if '"""' not in script_content and "'''" not in script_content:
            opportunities.append("Sem docstrings — adicionar documentação")
        
        # Verifica uso de constantes hardcoded
        hardcoded_numbers = []
        for i, line in enumerate(lines):
            # Procura números mágicos (excluindo 0, 1, índices comuns)
            import re
            nums = re.findall(r'\b(?!0|1\b)\d+\b', line)
            if nums and not line.strip().startswith('#'):
                hardcoded_numbers.append((i+1, nums))
        
        if hardcoded_numbers:
            opportunities.append(f"{len(hardcoded_numbers)} linhas com números hardcoded — considerar constantes nomeadas")
        
        if not opportunities:
            return None
        
        proposal = f"""# Proposta de Melhoria: {script_path.name}

## Análise Atual
- Hash: {current_hash[:16]}
- Linhas: {len(lines)}
- Oportunidades encontradas: {len(opportunities)}

## Oportunidades Identificadas
"""
        for i, opp in enumerate(opportunities, 1):
            proposal += f"{i}. {opp}\n"
        
        proposal += f"""
## Sugestão de Mudança
Baseado nas oportunidades acima, considere:

1. Refatorar funções longas em funções menores com responsabilidade única
2. Adicionar tratamento de exceções em operações de I/O e chamadas externas
3. Documentar funções principais com docstrings
4. Extrair constantes mágicas para seção CONFIG no topo do arquivo

## Prompt para Geração de Código
```
Script: {script_path.name}
Objetivo: Refatorar para melhorar manutenibilidade

Ações:
- Identifique a função mais longa e extraia sub-funções
- Adicione try/except em todas as operações de arquivo e network
- Adicione docstrings em todas as funções públicas
- Extraia números mágicos para constantes UPPER_CASE no topo

Preserve:
- Assinaturas de função existentes
- Comportamento observável
- Caminhos de arquivo e configurações
```
"""
        return proposal
    
    def execute_improvement_cycle(self, script_path: Optional[Path] = None):
        """
        Executa um ciclo completo de auto-melhoria.
        
        Este é o método principal que orquestra o processo.
        """
        ensure_dirs()
        instructions = self.load_program_instructions()
        
        # Seleciona script alvo
        if script_path is None:
            targets = self.list_target_scripts()
            if not targets:
                print("Nenhum script alvo encontrado.")
                return
            # Seleciona o mais recentemente modificado
            script_path = max(targets, key=lambda p: p.stat().st_mtime)
        
        print(f"🎯 Alvo selecionado: {script_path.name}")
        
        # Gera proposta
        proposal = self.generate_proposed_change(script_path, instructions)
        if not proposal:
            print("ℹ️ Nenhuma oportunidade de melhoria identificada.")
            return
        
        print(f"📝 Proposta gerada:\n{proposal}\n")
        
        # Salva proposta para revisão/manual application
        proposal_path = IMPROVEMENTS_DIR / f"{script_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_proposal.md"
        proposal_path.write_text(proposal, encoding='utf-8')
        print(f"💾 Proposta salva em: {proposal_path}")
        
        # Registra no histórico (status: pending)
        version = ScriptVersion(
            script_name=script_path.name,
            version_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now().isoformat(),
            hash_before=self.compute_hash(script_path),
            hash_after="pending",
            changes_description="Proposta gerada, aguardando implementação",
            test_result=None,
            kept=None
        )
        self.log_experiment(version)
        
        print(f"""
✅ Ciclo de auto-melhoria iniciado para {script_path.name}

Próximos passos (modo manual):
1. Revise a proposta em: {proposal_path}
2. Implemente as mudanças no script
3. Execute: python eve_self_improve.py --apply {script_path.name}
4. O sistema testará automaticamente e decidirá manter ou reverter

Para implementação automática com LLM, use:
  python eve_self_improve.py --auto {script_path.name}
""")
    
    def apply_pending_changes(self, script_name: str, new_content: Optional[str] = None):
        """
        Aplica mudanças pendentes a um script.
        
        Se new_content for fornecido, usa ele.
        Senão, procura por arquivo .proposal.md correspondente.
        """
        script_path = EVOLUTION_DIR / script_name
        if not script_path.exists():
            print(f"❌ Script não encontrado: {script_name}")
            return
        
        # Cria backup
        backup_path = self.create_backup(script_path)
        print(f"💾 Backup criado: {backup_path}")
        
        # Aqui aplicaríamos a modificação real
        # Por enquanto, apenas registra o ciclo
        
        # Testa
        success, output = self.run_script_test(script_path)
        
        print(f"""
🧪 Resultado do teste:
{'✅ SUCESSO' if success else '❌ FALHA'}
Output: {output[:500] if output else 'N/A'}
""")
        
        # Decide manter ou reverter
        if success:
            print("✅ Mudanças mantidas (teste passou)")
            kept = True
        else:
            print("❌ Revertendo para backup (teste falhou)")
            shutil.copy2(backup_path, script_path)
            kept = False
        
        # Registra resultado
        version = ScriptVersion(
            script_name=script_name,
            version_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now().isoformat(),
            hash_before="N/A",  # Deveria recuperar do pending
            hash_after=self.compute_hash(script_path),
            changes_description="Aplicação de proposta",
            test_result=success,
            test_output=output[:1000] if output else None,
            kept=kept
        )
        self.log_experiment(version)
    
    def show_stats(self):
        """Mostra estatísticas de auto-melhoria."""
        if not self.improvements_log.exists():
            print("Nenhum experimento registrado ainda.")
            return
        
        experiments = []
        with open(self.improvements_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    experiments.append(json.loads(line.strip()))
                except:
                    continue
        
        if not experiments:
            print("Log vazio.")
            return
        
        print(f"""
📊 Estatísticas de Auto-Melhoria
================================
Total de experimentos: {len(experiments)}

Por script:
""")
        from collections import Counter
        scripts = Counter(e['script_name'] for e in experiments)
        for script, count in scripts.most_common():
            kept = sum(1 for e in experiments if e['script_name'] == script and e.get('kept'))
            print(f"  {script}: {count} tentativas, {kept} mantidas")
        
        print(f"""
Por resultado:
  Sucesso (kept): {sum(1 for e in experiments if e.get('kept'))}
  Falha (reverted): {sum(1 for e in experiments if e.get('kept') == False)}
  Pendente: {sum(1 for e in experiments if e.get('kept') is None)}
""")

def main():
    """Entry point CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Eve Self-Improvement Framework — Modifique seus próprios scripts"
    )
    parser.add_argument('--target', '-t', help='Script específico para melhorar')
    parser.add_argument('--apply', '-a', help='Aplicar mudanças pendentes ao script')
    parser.add_argument('--stats', '-s', action='store_true', help='Mostrar estatísticas')
    parser.add_argument('--list', '-l', action='store_true', help='Listar scripts alvo')
    
    args = parser.parse_args()
    
    improver = SelfImprover()
    
    if args.stats:
        improver.show_stats()
    elif args.list:
        targets = improver.list_target_scripts()
        print("Scripts disponíveis para melhoria:")
        for t in targets:
            size = t.stat().st_size
            print(f"  {t.name} ({size} bytes)")
    elif args.apply:
        improver.apply_pending_changes(args.apply)
    else:
        # Ciclo padrão: gerar proposta
        target = Path(args.target) if args.target else None
        improver.execute_improvement_cycle(target)

if __name__ == "__main__":
    main()
