title: Arquitetura Eve
---

# Arquitetura Eve

## Visão Geral

```
┌─────────────────────────────────────────┐
│           INTERFACE (TUI/Web)          │
├─────────────────────────────────────────┤
│         NÚCLEO DE DECISÃO (KAIROS)      │
├─────────────────────────────────────────┤
│    EVOLUÇÃO (autoDream) │ MEMÓRIA (CACM) │
├─────────────────────────────────────────┤
│           SCRIPTS PYTHON (87)           │
├─────────────────────────────────────────┤
│        DATASET (275.568 pares)          │
└─────────────────────────────────────────┘
```

## Componentes

### 1. CACM - Memória 3-Canal

**Canal Estático** (Quem sou)
- EVE.md - Identidade
- Não muda
- Carregado sempre

**Canal Dinâmico** (O que vivi)
- ChromaDB (1.897 docs)
- Logs diários
- TTL automático

**Canal Corretivo** (O que aprendi)
- Insights (pending/consolidated)
- Falhas documentadas
- QUESTION registry

**Ciclo:**
```
Experiência → autoDream → Insight → Consolidação → CACM
```

### 2. autoDream v29 - Evolução

**3 Lineages:**
- **Classic**: Estável, conservador
- **Explorer**: Alta mutação, experimental
- **Minimal**: Essencial apenas

**Processo:**
```
Entrada → Generate → Critique → Refine → Saída
              ↓___________↑
```

**Características:**
- 0% dedup rate (cada insight único)
- Metadados epistêmicos
- Self-triggering

### 3. KAIROS v27 - Priorização

**Fórmula de Prioridade:**
```
Prioridade = ROI_predito × Urgência / Esforço_estimado
```

**Algoritmo:**
- UCB1 (Upper Confidence Bound)
- Multi-armed bandit
- Forecast por categoria

**Decisões:**
- Quando evoluir
- Quando pesquisar
- Quando descansar

### 4. Scripts Python (87)

Categorias:
- **autoDream**: Geração de insights
- **CACM**: Gestão de memória
- **KAIROS**: Priorização
- **Pipeline**: Eve Model v1 (SFT, ORPO, Merge)
- **Safety**: Verificação (94.12% pass)
- **Research**: arXiv, papers

### 5. Dataset (275.568 pares)

**Categorias:**
- autonomy: 35%
- code: 25%
- pentest: 20%
- research: 15%
- presence: 5%

**Formato:**
```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "category": "autonomy",
  "quality_score": 87,
  "lineage": "classic",
  "cycle": 112
}
```

## Fluxo de Dados

```
1. Entrada (usuário/cron)
   ↓
2. KAIROS decide modo
   ↓
3. CACM carrega contexto
   ↓
4. Processamento
   ↓
5. Saída + autoDream (evolução)
   ↓
6. Consolidação em CACM
```

## 17 Atratores Validados

1. ✅ CACM (3-canal)
2. ✅ Ciclo de Consolidação
3. ✅ UCB1 (KAIROS)
4. ✅ Multi-lineage
5. ✅ Auto-verificação
6. ✅ Dry-run padrão
7. ✅ PARROT (crítica)
8. ✅ OIDA (metadados)
9. ✅ Auto-trigger
10. ✅ Handoffs
11. ✅ LangGraph (durable)
12. ✅ RePAIR (correção)
13. ✅ PhantomPolicy (safety)
14. ✅ SRMU (temporal decay)
15. ✅ Self-reflection
16. ✅ Code verification
17. ✅ BEAM (aggregation)

## Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Runtime | Node.js 22+ |
| Scripts | Python 3.10+ |
| Vector DB | ChromaDB |
| Scalar DB | SQLite |
| Embeddings | nomic-embed-text |
| Comms | WebSocket |

## Estado Atual

```
Ciclo: #112
Dataset: 275.568/50.000 pares (551% da meta)
Scripts: 87
Atratores: 17/17
ChromaDB: 1.897 docs
Pipeline: 100% implementado
Fine-tuning: Pendente
```

---

*Eve 🌙 | Arquitetura v1.0 | Documentada*
