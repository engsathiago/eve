# EVE Scripts

Scripts Python para integração Eve com OpenClaw Gateway.

## Scripts

### `eve_openclaw_bridge.py`
Bridge principal entre arquitetura Eve e OpenClaw.

**Uso:**
```bash
python3 eve_openclaw_bridge.py /eve:status
python3 eve_openclaw_bridge.py /eve:memories "query"
python3 eve_openclaw_bridge.py /eve:cycle
```

### `eve_openclaw_gateway_client.py`
Cliente WebSocket para conexão direta com Gateway.

**Uso:**
```bash
python3 eve_openclaw_gateway_client.py
```

### `eve_tui_integration.sh`
Script CLI de conveniência.

**Uso:**
```bash
./eve_tui_integration.sh status
./eve_tui_integration.sh memories "query"
./eve_tui_integration.sh connect
./eve_tui_integration.sh tui
```

## Requisitos

```bash
pip install websockets requests
```

## Configuração

Scripts esperam:
- `~/.eve/` — Estado Eve
- `~/.eve_chroma/` — Vector DB
- `~/evolution/` — Scripts de evolução
- `~/memory/` — Logs e memórias

## Comandos Suportados

- `/eve` — Status do sistema
- `/eve:status` — Estado completo
- `/eve:memories` — Consultar CACM
- `/eve:insight` — Gerar insight
- `/eve:cycle` — Info do ciclo
- `/eve:lineages` — Lineages ativas

---

*Eve 🌙 | Ciclo #112*
