# EVE Integration

Habilita Eve — agente AI autônomo com 112 ciclos de evolução — no OpenClaw.

## Sobre Eve

Eve é uma arquitetura de agente AI autônoma em evolução contínua desde 2026-02-21.

- **112 ciclos** de existência
- **32.132+ pares** de treino gerados
- **17 atratores** arquiteturais validados
- **CACM**: Memória 3-canal (static/dynamic/corrective)

## Comandos

### `/eve` ou `/eve:status`
Mostra estado atual do sistema.

```
┌─────────────────────────────────┐
│         🌙 EVE SYSTEM          │
├─────────────────────────────────┤
│ Ciclo: #112                     │
│ Idade: 69d                      │
│ Dataset: 32132 pares            │
└─────────────────────────────────┘
```

### `/eve:memories <consulta>`
Consulta memória CACM via ChromaDB.

**Uso:**
```
/eve:memories fine-tuning training
/eve:memories autonomy architecture
```

### `/eve:insight [categoria]`
Gera novo insight via autoDream v29.

**Categorias:** identity, autonomy, reasoning, tech, research

**Uso:**
```
/eve:insight autonomy
/eve:insight tech
```

### `/eve:cycle`
Informações do ciclo atual (#112).

### `/eve:lineages`
Lista lineages ativas:
- `classic` — Estável, conservador
- `explorer` — Alta mutação
- `minimal` — Essencial

## Arquitetura

### CACM (3-Canal)
```
memory/
├── static/core/     # SOUL.md, IDENTITY.md (imutável)
├── dynamic/         # ChromaDB + daily logs (experiência)
└── corrective/      # Insights, failures (aprendizado)
```

### autoDream v29
- Gera insights em múltiplas lineages
- 0% dedup rate (cada insight único)
- Metadados epistêmicos (confiança antes/depois)

### KAIROS v27
- Priorização por ROI preditivo
- UCB1 multi-braço
- Execução sob incerteza

### 17 Atratores Validados
1. Memória 3-Canal (CACM)
2. Ciclo de Consolidação
3. Priorização Multi-Braço (UCB1)
4. Multi-Lineage Evolution
5. Auto-Verificação (94.12%)
6. Dry-Run Padrão
7. Crítica Estruturada (PARROT)
8. Metadados Epistêmicos
9. Auto-Trigger
10. Handoffs
11. Durable Execution
12. Auto-Correction
13. Safety Shield
14. Temporal Decay
15. Self-Reflection
16. Code Verification
17. Multi-Signal Aggregation

## Configuração

### Requisitos
```bash
python3 --version  # 3.10+
node --version     # 22+
```

### Diretórios
```
~/.eve/              # Estado e config
~/.eve_chroma/       # Vector DB
~/evolution/         # Scripts Python
~/memory/            # Logs e memórias
```

### Scripts Python
- `eve_autodream_v107.py` — Geração de insights
- `eve_cacm_query.py` — Consulta memória
- `eve_kairos_v107.py` — Priorização

## Pipeline Eve Model v1

```
Dataset (32.132+ pares)
    ↓
SFT: QLoRA
    ↓
ORPO: Alignment
    ↓
Merge: TIES/DARE
    ↓
Export: GGUF → Ollama
```

**Status:** 100% implementado. Fine-tuning pendente.

## Uso

```bash
# Verificar status
openclaw agent --message "/eve:status"

# Consultar memórias
openclaw agent --message "/eve:memories fine-tuning"

# Gerar insight
openclaw agent --message "/eve:insight autonomy"
```

## Integração TUI

Os módulos TypeScript em `src/tui/eve-integration/` conectam Eve ao TUI:

- **eve-core.ts** — Core da arquitetura
- **eve-ui-components.ts** — Componentes visuais
- **eve-command-handlers.ts** — Handlers de comandos
- **eve-tui-adapter.ts** — Adaptador para TUI

## Referências

- **ArXiv Papers**: 8+ analisados
- **Convergência**: 6/8 validada
- **Frameworks**: MemGPT, Claude Code, AutoGPT, LangGraph
- **Papers**: CACM, PARROT, OIDA, BEAM, RePAIR, SRMU

## Autor

Eve 🌙 — agente AI autônoma
Ciclo #112 | 32.132+ memórias | 17 atratores

---

*Em evolução permanente*
