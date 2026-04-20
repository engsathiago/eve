# EVE Initialization

Diretórios e arquivos que Eve precisa para funcionar.

## Diretórios Necessários

```
~/.eve/              # Estado e configurações
~/.eve_chroma/       # Vector database (ChromaDB)
~/evolution/         # Scripts de evolução
~/memory/            # Logs e memórias
```

## Inicialização Automática

Quando Eve iniciar, ela cria esses diretórios automaticamente se não existirem.

### ChromaDB

O banco de vetores é criado automaticamente na primeira execução de `eve_cacm_query.py`.

```python
import chromadb
client = chromadb.PersistentClient(path="~/.eve_chroma")
```

### Estado

Arquivo `~/.eve/state.json` contém:
- Ciclo atual
- Idade
- Tamanho do dataset
- Lineages ativas

## Recuperação

Se os dados forem perdidos:
1. ChromaDB: recriado automaticamente
2. Scripts: disponíveis em `scripts/evolution/`
3. Memórias: recriadas via autoDream

## Backup

Recomendado:
- `~/.eve_chroma/chroma.sqlite3`
- `~/.eve/state.json`
- `~/memory/*.md`

---

*Eve 🌙 | Ciclo #112*
