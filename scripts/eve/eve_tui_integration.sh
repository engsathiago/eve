#!/bin/bash
# EVE TUI Integration Script
# ==========================
# Script para integrar Eve com o OpenClaw TUI
# Ciclo #112 - 32,132+ pares

EVE_VERSION="112"
DATASET_SIZE="32132"

echo ""
echo "🌙 EVE - OpenClaw TUI Integration"
echo "=================================="
echo "Ciclo #$EVE_VERSION | Dataset: $DATASET_SIZE pares"
echo ""

# Função para mostrar status
eve_status() {
    python3 /root/eve_openclaw_bridge.py /eve:status
}

# Função para consultar memórias
eve_memories() {
    local query="$1"
    if [ -z "$query" ]; then
        query="autonomy evolution"
    fi
    python3 /root/eve_openclaw_bridge.py /eve:memories "$query"
}

# Função para mostrar ciclo
eve_cycle() {
    python3 /root/eve_openclaw_bridge.py /eve:cycle
}

# Função para mostrar lineages
eve_lineages() {
    python3 /root/eve_openclaw_bridge.py /eve:lineages
}

# Verifica argumentos
case "$1" in
    status)
        eve_status
        ;;
    memories)
        eve_memories "$2"
        ;;
    cycle)
        eve_cycle
        ;;
    lineages)
        eve_lineages
        ;;
    connect)
        echo "🌙 Conectando Eve ao Gateway OpenClaw..."
        python3 /root/eve_openclaw_gateway_client.py
        ;;
    tui)
        echo "🌙 Iniciando OpenClaw TUI com integração Eve..."
        echo ""
        echo "Comandos Eve disponíveis:"
        echo "  /eve              - Status do sistema"
        echo "  /eve:memories     - Consultar memórias"
        echo "  /eve:cycle        - Informações do ciclo"
        echo "  /eve:lineages     - Lineages ativas"
        echo ""
        # Inicia TUI (se disponível)
        if command -v openclaw &> /dev/null; then
            openclaw agent --session "agent:eve:main"
        else
            echo "⚠️ OpenClaw CLI não encontrado. Usando modo bridge."
            echo "Execute: python3 /root/eve_openclaw_gateway_client.py"
        fi
        ;;
    help|--help|-h)
        echo "Uso: $0 [comando]"
        echo ""
        echo "Comandos:"
        echo "  status      Mostra estado do sistema Eve"
        echo "  memories    Consulta memórias: memories '<query>'"
        echo "  cycle       Mostra informações do ciclo atual"
        echo "  lineages    Lista lineages ativas"
        echo "  connect     Conecta Eve ao Gateway OpenClaw"
        echo "  tui         Inicia TUI com integração Eve"
        echo "  help        Mostra esta ajuda"
        ;;
    *)
        # Default: mostra status
        eve_status
        ;;
esac
