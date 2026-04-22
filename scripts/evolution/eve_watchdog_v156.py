#!/usr/bin/env python3
"""
eve_watchdog_v156.py — Watchdog externo para garantir que Eve sempre esteja rodando.

Roda separadamente (ou via cron) e monitora se Eve está viva.
Se detecta falha, tenta restartar automaticamente.
"""
#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

MONITOR_DIR = Path("/memory/self_monitor")
HEARTBEAT_FILE = MONITOR_DIR / "heartbeat.json"
RESTART_LOG = MONITOR_DIR / "restart_log.json"
RECOVERY_SCRIPT = Path("/root/evolution") / "eve_autonomous_loop_v155.py"

WATCHDOG_TIMEOUT_SECONDS = 120  # 2 minutos sem heartbeat = falha
MAX_RESTART_ATTEMPTS = 5        # Max restarts antes de desistir
RESTART_WINDOW_MINUTES = 30     # Janela para contar restarts


def log_restart(reason: str, success: bool):
    """Log de restart."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "success": success
    }
    
    log_data = []
    if RESTART_LOG.exists():
        try:
            with open(RESTART_LOG) as f:
                log_data = json.load(f)
        except:
            pass
    
    log_data.append(entry)
    
    # Mantém apenas últimos 50
    log_data = log_data[-50:]
    
    with open(RESTART_LOG, "w") as f:
        json.dump(log_data, f, indent=2)


def get_recent_restarts() -> int:
    """Conta restarts recentes."""
    if not RESTART_LOG.exists():
        return 0
    
    try:
        with open(RESTART_LOG) as f:
            log_data = json.load(f)
        
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=RESTART_WINDOW_MINUTES)
        recent = [
            entry for entry in log_data
            if datetime.fromisoformat(entry["timestamp"]) > cutoff
        ]
        return len(recent)
    except:
        return 0


def check_heartbeat() -> tuple[bool, str]:
    """Verifica se heartbeat está atualizado."""
    if not HEARTBEAT_FILE.exists():
        return False, "No heartbeat file"
    
    try:
        with open(HEARTBEAT_FILE) as f:
            data = json.load(f)
        
        last_beat = datetime.fromisoformat(data.get("timestamp", ""))
        age_seconds = (datetime.now(timezone.utc) - last_beat).total_seconds()
        
        if age_seconds > WATCHDOG_TIMEOUT_SECONDS:
            return False, f"Stale heartbeat: {age_seconds:.0f}s old"
        
        return True, f"Healthy: {age_seconds:.0f}s ago"
        
    except Exception as e:
        return False, f"Error reading heartbeat: {e}"


def restart_eve() -> bool:
    """Tenta restartar Eve."""
    try:
        # Mata processos antigos
        subprocess.run(
            ["pkill", "-f", "eve_autonomous_loop"],
            capture_output=True,
            timeout=10
        )
        
        time.sleep(2)  # Espera processo morrer
        
        # Inicia novo processo
        subprocess.Popen(
            [sys.executable, str(RECOVERY_SCRIPT), "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd="/root/evolution"
        )
        
        return True
    except Exception as e:
        return False


def main():
    """Watchdog principal."""
    # Verifica heartbeat
    healthy, message = check_heartbeat()
    
    if healthy:
        print(f"✅ {message}")
        return 0
    
    # Não está saudável
    print(f"⚠️ {message}")
    
    # Verifica se já tentou muito
    recent_restarts = get_recent_restarts()
    if recent_restarts >= MAX_RESTART_ATTEMPTS:
        print(f"❌ Max restarts ({MAX_RESTART_ATTEMPTS}) in {RESTART_WINDOW_MINUTES}min reached")
        print("   Manual intervention required")
        return 1
    
    # Tenta restartar
    print(f"🔄 Restarting Eve... (attempt {recent_restarts + 1}/{MAX_RESTART_ATTEMPTS})")
    success = restart_eve()
    
    log_restart(message, success)
    
    if success:
        print("✅ Restart initiated")
        return 0
    else:
        print("❌ Restart failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
