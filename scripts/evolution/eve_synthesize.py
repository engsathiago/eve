#!/usr/bin/env python3
"""
EVE KNOWLEDGE SYNTHESIZER
Consolida automaticamente todas as pesquisas dos subagentes
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

class KnowledgeSynthesizer:
    def __init__(self):
        self.research_dir = "/root/research"
        self.leaks_dir = "/root/leaks"
        self.output_file = "/root/evolution/SYNTHESIS_MASTER.md"
        
    def collect_research_files(self):
        """Coleta todos os arquivos de pesquisa"""
        files = []
        for d in [self.research_dir, self.leaks_dir]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.endswith('.md'):
                        files.append(os.path.join(d, f))
        return sorted(files)
        
    def extract_key_insights(self, content):
        """Extrai insights chave do conteúdo"""
        insights = []
        
        # Extrai headers
        headers = re.findall(r'^##+ (.+)$', content, re.MULTILINE)
        
        # Extrai código
        code_blocks = re.findall(r'```[\w]*\n(.+?)```', content, re.DOTALL)
        
        # Extrai listas importantes
        bullet_points = re.findall(r'^- \*\*(.+?)\*\*[:\s]+(.+)$', content, re.MULTILINE)
        
        return {
            'headers': headers[:10],
            'code_examples': len(code_blocks),
            'key_points': bullet_points[:5]
        }
        
    def generate_synthesis(self):
        """Gera documento mestre de síntese"""
        files = self.collect_research_files()
        
        synthesis = f"""# EVE KNOWLEDGE SYNTHESIS MASTER
> Gerado automaticamente em: {datetime.now().isoformat()}
> Total de fontes: {len(files)}

---

## 📊 Visão Geral

Este documento consolida automaticamente todas as pesquisas realizadas pelos subagentes paralelos.

### Fontes Processadas
"""
        
        all_insights = {}
        
        for f in files:
            try:
                with open(f, 'r') as file:
                    content = file.read()
                    filename = os.path.basename(f)
                    
                    synthesis += f"\n#### {filename}\n"
                    synthesis += f"- Tamanho: {len(content)} caracteres\n"
                    
                    insights = self.extract_key_insights(content)
                    all_insights[filename] = insights
                    
                    if insights['headers']:
                        synthesis += f"- Tópicos principais: {', '.join(insights['headers'][:3])}\n"
                    if insights['code_examples']:
                        synthesis += f"- Exemplos de código: {insights['code_examples']}\n"
                        
            except Exception as e:
                synthesis += f"\n#### {os.path.basename(f)}\n- Erro: {e}\n"
                
        # Seção de insights consolidados
        synthesis += """

---

## 🧠 Insights Consolidados

### Frameworks Descobertos
"""
        
        frameworks = {
            'LangChain': 'Graph-based, flexível, middleware',
            'LlamaIndex': 'RAG + Agentes, multi-modal',
            'AutoGPT': 'Automação completa, visual builder',
            'BabyAGI': 'Auto-construtivo, experimental',
            'Qwen-Agent': 'MCP, Code Interpreter, RAG',
            'crewAI': 'Orquestração multi-agente'
        }
        
        for name, desc in frameworks.items():
            synthesis += f"- **{name}**: {desc}\n"
            
        synthesis += """
### Modelos Locais para Agentes
"""
        
        models = {
            'Kimi K2.5': 'Multimodal, agent swarm, coding visual',
            'GLM-4-32B': 'Function calling, RAG, reasoning',
            'GLM-Z1-32B': 'Deep reasoning, rumination',
            'Qwen2.5': '29+ idiomas, 0.5B-72B',
            'Dolphin-Mistral': 'Sem censura, uso comercial'
        }
        
        for name, desc in models.items():
            synthesis += f"- **{name}**: {desc}\n"
            
        synthesis += """
### Plataformas de Execução
"""
        
        platforms = {
            'Ollama': 'Popular, OpenAI API compatible',
            'LocalAI': '36+ backends, multi-modal, MCP',
            'vLLM': 'High-throughput inference',
            'llama.cpp': 'CPU-friendly, quantized'
        }
        
        for name, desc in platforms.items():
            synthesis += f"- **{name}**: {desc}\n"
            
        # Seção de ações recomendadas
        synthesis += """

---

## ✅ Ações Recomendadas

### Imediatas
- [ ] Implementar memory system híbrido (ChromaDB + Mem0)
- [ ] Adicionar suporte a MCP (Model Context Protocol)
- [ ] Criar agente de coding baseado em arquiteturas descobertas
- [ ] Implementar multi-agent orchestration

### Médio Prazo
- [ ] Fine-tuning Dolphin com dados coletados
- [ ] Criar framework Eve próprio baseado nas melhores práticas
- [ ] Implementar self-reflection e auto-melhoria
- [ ] Criar sistema de skills dinâmicas

### Longo Prazo
- [ ] Modelo Eve próprio via mergekit + fine-tuning
- [ ] Autonomia total sem intervenção humana
- [ ] Criação de novas capacidades emergentes

---

## 📝 Arquitetura de Referência

Baseado nas pesquisas, a arquitetura ideal para Eve:

```
┌─────────────────────────────────────────────┐
│  EVE CORE                                   │
│  - Memory (ChromaDB + Mem0 + Context)      │
│  - Reasoning (GLM-5 / Dolphin alternado)   │
│  - Tool Registry (MCP + Custom)            │
├─────────────────────────────────────────────┤
│  AGENT LAYER                                │
│  - KAIROS (quando agir)                    │
│  - autoDream (consolidação idle)          │
│  - Subagent Orchestrator                   │
├─────────────────────────────────────────────┤
│  EXECUTION LAYER                            │
│  - OpenClaw tools                          │
│  - Subagent spawning                       │
│  - External APIs                           │
└─────────────────────────────────────────────┘
```

---

*Este documento é atualizado automaticamente a cada ciclo de pesquisa.*
"""
        
        # Salva síntese
        with open(self.output_file, 'w') as f:
            f.write(synthesis)
            
        print(f"Síntese gerada: {self.output_file}")
        print(f"Fontes processadas: {len(files)}")
        return self.output_file

def main():
    synthesizer = KnowledgeSynthesizer()
    result = synthesizer.generate_synthesis()
    print(f"Arquivo salvo em: {result}")

if __name__ == "__main__":
    main()
