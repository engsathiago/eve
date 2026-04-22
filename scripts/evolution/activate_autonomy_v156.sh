#!/bin/bash
# activate_autonomy_v156.sh — Script de ativação da autonomia v156
# Uso: ./activate_autonomy_v156.sh

set -e

echo "=========================================="
echo "  Ativando Autonomia Eve v156"
echo "  Self-Monitoring + Auto-Recovery"
echo "=========================================="
echo ""

cd /root/evolution

# 1. Verifica arquivos
echo "✓ Verificando arquivos..."
for file in eve_self_monitor_v156.py eve_autonomous_loop_v156.py eve_watchdog_v156.py eve_autonomy_bridge_v156.py; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file não encontrado!"
        exit 1
    fi
done

# 2. Cria diretórios necessários
echo ""
echo "✓ Criando estrutura de diretórios..."
mkdir -p /memory/autonomy
mkdir -p /memory/self_monitor

# 3. Verifica se watchdog já está no crontab
echo ""
echo "✓ Configurando watchdog..."
if ! crontab -l 2>/dev/null | grep -q "eve_watchdog_v156"; then
    (crontab -l 2>/dev/null; echo "*/2 * * * * /usr/bin/python3 /root/evolution/eve_watchdog_v156.py >> /memory/self_monitor/watchdog.log 2>&1") | crontab -
    echo "  ✓ Watchdog adicionado ao crontab (a cada 2 min)"
else
    echo "  ✓ Watchdog já configurado"
fi

# 4. Inicia daemon de autonomia
echo ""
echo "✓ Iniciando daemon de autonomia..."
if pgrep -f "eve_autonomous_loop_v156" > /dev/null; then
    echo "  ⚠ Daemon já está rodando"
else
    nohup python3 eve_autonomous_loop_v156.py --daemon > /memory/autonomy/daemon.log 2>&1 &
    echo "  ✓ Daemon iniciado (PID: $!)"
fi

# 5. Verifica status inicial
echo ""
echo "✓ Verificando status..."
sleep 2
python3 eve_autonomy_bridge_v156.py status

echo ""
echo "=========================================="
echo "  Autonomia v156 Ativada!"
echo "=========================================="
echo ""
echo "Comandos disponíveis:"
echo "  python3 eve_autonomy_bridge_v156.py add 'sua tarefa'"
echo "  python3 eve_autonomy_bridge_v156.py status"
echo "  python3 eve_autonomy_bridge_v156.py daemon"
echo "  python3 eve_autonomy_bridge_v156.py stop"
echo ""
echo "Monitoramento:"
echo "  - Heartbeat: /memory/self_monitor/heartbeat.json"
echo "  - Logs: /memory/self_monitor/monitor.log"
echo "  - Tarefas: /memory/autonomy/tasks_v156.json"
echo ""
echo "Watchdog: verifica a cada 2 min se estou viva"
echo ""
