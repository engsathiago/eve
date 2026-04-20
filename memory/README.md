# EVE Memory Structure

Sistema CACM (3-Canal de Memória)

## Estrutura

```
memory/
├── static/core/           # Identidade imutável
│   ├── SOUL.md
│   ├── IDENTITY.md
│   └── AGENTS.md
├── dynamic/               # Experiências em tempo real
│   ├── daily/            # Logs YYYY-MM-DD.md
│   └── chromadb/         # Vector store
└── corrective/           # Aprendizado e feedback
    ├── insights/         # Insights gerados
    ├── failures/         # Logs de falhas
    └── questions/        # QUESTION registry
```

## Canais

### Static
- **Conteúdo:** Identidade, valores, arquitetura
- **Mutabilidade:** Nunca
- **Acesso:** Sempre carregado

### Dynamic
- **Conteúdo:** Conversas, logs, experiências
- **Mutabilidade:** TTL automático
- **Acesso:** Via ChromaDB

### Corrective
- **Conteúdo:** Insights, falhas, aprendizados
- **Mutabilidade:** Consolidado após revisão
- **Acesso:** Manual + autoDream

## Ciclo de Consolidação

1. autoDream gera insights → `corrective/insights/pending/`
2. Consolidação analisa → verifica contradições
3. Atualiza `static/core/` se necessário
4. Move para `corrective/insights/consolidated/`

## Inicialização

Criado automaticamente em primeiro uso.

---

*Eve 🌙 | CACM v1.0*
