#!/usr/bin/env python3
"""
EVE-OpenClaw Bridge
===================

Integra a arquitetura Eve (CACM, autoDream, KAIROS) com o OpenClaw Gateway.
Ciclo #112 - 32,132+ pares - 17 atratores validados

Autor: Eve
Data: 2026-04-20
"""

import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Configurações
EVE_HOME = Path.home() / ".eve"
EVE_CHROMA = Path.home() / ".eve_chroma"
EVOLUTION_DIR = Path.home() / "evolution"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

@dataclass
class EveState:
    cycle: int = 112
    age: int = 69
    dataset_size: int = 32132
    last_heartbeat: float = 0.0
    active_lineages: List[str] = None
    pending_insights: int = 0
    consolidated_insights: int = 0
    
    def __post_init__(self):
        if self.active_lineages is None:
            self.active_lineages = ["classic", "explorer", "minimal"]
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = datetime.now().timestamp()

class EveOpenClawBridge:
    """
    Bridge entre a arquitetura Eve e o OpenClaw Gateway.
    """
    
    def __init__(self):
        self.state = self._load_state()
        self._ensure_dirs()
        
    def _ensure_dirs(self):
        """Garante que diretórios existam."""
        for path in [EVE_HOME, EVE_CHROMA]:
            path.mkdir(parents=True, exist_ok=True)
            
    def _load_state(self) -> EveState:
        """Carrega estado do sistema Eve."""
        state_file = EVE_HOME / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                return EveState(**data)
            except:
                pass
        return EveState()
    
    def _save_state(self):
        """Salva estado atual."""
        state_file = EVE_HOME / "state.json"
        state_file.write_text(json.dumps(asdict(self.state), indent=2))
        
    def query_memory(self, query: str, corpus: str = "all", limit: int = 5) -> List[Dict]:
        """
        Consulta memória via ChromaDB.
        
        Args:
            query: Texto da consulta
            corpus: Tipo de corpus (static/dynamic/corrective/all)
            limit: Número máximo de resultados
        """
        # Usa o script CACM existente
        script = EVOLUTION_DIR / "eve_cacm_query.py"
        if not script.exists():
            return self._fallback_query(query, limit)
            
        try:
            result = subprocess.run(
                ["python3", str(script), "--query", query, "--corpus", corpus, "--limit", str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
            
        return self._fallback_query(query, limit)
        
    def _fallback_query(self, query: str, limit: int) -> List[Dict]:
        """Fallback quando ChromaDB não disponível."""
        # Busca em arquivos de memória
        memories = []
        memory_dir = Path.home() / "memory"
        
        if memory_dir.exists():
            for file in sorted(memory_dir.glob("*.md")):
                content = file.read_text()
                # Score simples baseado em overlap
                words = set(query.lower().split())
                content_words = set(content.lower().split())
                overlap = len(words & content_words)
                if overlap > 0:
                    memories.append({
                        "source": str(file),
                        "content": content[:500],
                        "score": overlap / len(words)
                    })
                    
        return sorted(memories, key=lambda x: x["score"], reverse=True)[:limit]
        
    def generate_insight(self, category: str = "identity", context: str = "") -> Optional[Dict]:
        """
        Gera insight via autoDream.
        
        Args:
            category: Tipo de insight (identity/autonomy/reasoning/tech/research)
            context: Contexto adicional
        """
        # Usa autoDream v107
        script = EVOLUTION_DIR / "eve_autodream_v107.py"
        if not script.exists():
            return None
            
        try:
            result = subprocess.run(
                ["python3", str(script), "--category", category, "--quick"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
            
        return None
        
    def get_context_for_prompt(self, user_message: str) -> str:
        """
        Gera contexto Eve para inclusão em prompts.
        
        Args:
            user_message: Mensagem do usuário
            
        Returns:
            Texto de contexto para adicionar ao prompt
        """
        parts = [
            f"\n[Eve Context: Ciclo #{self.state.cycle}, {self.state.age}d, {self.state.dataset_size:,} pares]",
            f"Lineages: {', '.join(self.state.active_lineages)}"
        ]
        
        # Consulta memória relevante
        memories = self.query_memory(user_message, limit=3)
        if memories:
            parts.append("\nMemórias relevantes:")
            for mem in memories:
                content = mem.get("content", "")[:150]
                parts.append(f"- {content}...")
                
        return "\n".join(parts)
        
    def handle_slash_command(self, command: str, args: List[str]) -> str:
        """
        Handler para comandos slash Eve.
        
        Args:
            command: Comando (eve:status, eve:memories, etc)
            args: Argumentos
            
        Returns:
            Resposta formatada
        """
        cmd = command.lower().replace("/", "")
        
        if cmd == "eve" or cmd == "eve:status":
            return self._format_status()
            
        elif cmd == "eve:memories":
            query = " ".join(args) if args else "autonomy evolution"
            memories = self.query_memory(query, limit=5)
            return self._format_memories(memories)
            
        elif cmd == "eve:insight":
            category = args[0] if args else "identity"
            insight = self.generate_insight(category)
            return self._format_insight(insight)
            
        elif cmd == "eve:cycle":
            return self._format_cycle()
            
        elif cmd == "eve:lineages":
            return self._format_lineages()
            
        else:
            return f"Comando Eve desconhecido: {command}"
            
    def _format_status(self) -> str:
        """Formata status do sistema."""
        lines = [
            "",
            "┌─────────────────────────────────┐",
            "│         🌙 EVE SYSTEM          │",
            "├─────────────────────────────────┤",
            f"│ Ciclo: #{str(self.state.cycle).ljust(24)} │",
            f"│ Idade: {str(self.state.age) + 'd':<25} │",
            f"│ Dataset: {str(self.state.dataset_size) + ' pares':<22} │",
            "├─────────────────────────────────┤",
            f"│ Lineages: {str(', '.join(self.state.active_lineages))[:20].ljust(20)} │",
            f"│ Insights: {str(self.state.consolidated_insights) + ' cons/' + str(self.state.pending_insights) + ' pend':<20} │",
            "└─────────────────────────────────┘",
            ""
        ]
        return "\n".join(lines)
        
    def _format_memories(self, memories: List[Dict]) -> str:
        """Formata lista de memórias."""
        if not memories:
            return "\n📭 Nenhuma memória encontrada.\n"
            
        lines = ["", "📊 Memórias Encontradas:", "─" * 40]
        for i, mem in enumerate(memories[:5], 1):
            content = mem.get("content", "")[:60]
            score = mem.get("score", 0)
            lines.append(f"{i}. {content}... (score: {score:.2f})")
        lines.extend(["─" * 40, ""])
        return "\n".join(lines)
        
    def _format_insight(self, insight: Optional[Dict]) -> str:
        """Formata insight gerado."""
        if not insight:
            return "\n⚠️ Não foi possível gerar insight.\n"
            
        lines = [
            "",
            "💡 Novo Insight Gerado:",
            "─" * 40,
            f"Categoria: {insight.get('category', 'unknown')}",
            f"Confiança: {insight.get('confidence_before', 0)}% → {insight.get('confidence_after', 0)}%",
            f"Evidência: {insight.get('evidence_type', 'unknown')}",
            "",
            insight.get("content", "N/A"),
            "─" * 40,
            ""
        ]
        return "\n".join(lines)
        
    def _format_cycle(self) -> str:
        """Formata informações do ciclo."""
        lines = [
            "",
            f"🌙 Ciclo #{self.state.cycle}",
            f"📅 Idade: {self.state.age} dias",
            f"💾 Dataset: {self.state.dataset_size:,} pares de treino",
            f"🧬 Lineages: {', '.join(self.state.active_lineages)}",
            ""
        ]
        return "\n".join(lines)
        
    def _format_lineages(self) -> str:
        """Formata lista de lineages."""
        icons = {
            "classic": "📘",
            "explorer": "🔥",
            "minimal": "✨"
        }
        lines = ["", "🧬 Lineages Ativas:", "─" * 40]
        for lineage in self.state.active_lineages:
            icon = icons.get(lineage, "💿")
            lines.append(f"{icon} {lineage}")
        lines.extend(["─" * 40, ""])
        return "\n".join(lines)
        
    def heartbeat(self):
        """Atualiza heartbeat do sistema."""
        self.state.last_heartbeat = datetime.now().timestamp()
        self._save_state()


def main():
    """CLI para o bridge."""
    import sys
    
    bridge = EveOpenClawBridge()
    
    if len(sys.argv) < 2:
        print(bridge._format_status())
        return
        
    command = sys.argv[1]
    args = sys.argv[2:]
    
    result = bridge.handle_slash_command(command, args)
    print(result)


if __name__ == "__main__":
    main()
