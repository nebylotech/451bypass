import os
import sys
import subprocess
import datetime
import winreg
from pathlib import Path
from typing import Tuple

from .config import load_config, PRIMARY_CONFIG_DIR
from .daemon import get_pythonw_path, start_daemon, stop_daemon, get_daemon_status
from .proxy import is_system_pac_enabled, enable_system_pac, disable_system_pac
from .cloudflare import check_worker_live_health
from .lists import reconcile_custom_domains
from .utils import success, info, warn, error

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "451bypass"
SCHTASKS_NAME = "451bypass-Service"
LEGACY_TASKS = ["451bypass-Sync", "51-BYPASS-Sync"]
LOG_FILE = PRIMARY_CONFIG_DIR / "service.log"

def log_service_message(msg: str) -> None:
    PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

def is_autorun_registered() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return bool(val)
    except Exception:
        return False

def register_autorun() -> bool:
    if sys.platform != "win32":
        return False
    pythonw = get_pythonw_path()
    pkg_dir = Path(__file__).resolve().parent.parent
    install_dir = PRIMARY_CONFIG_DIR

    val = f'"{pythonw}" -m bypass451.daemon run'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, val)
        return True
    except Exception:
        return False

def unregister_autorun() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
        return True
    except Exception:
        return False

def install_task() -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Windows autorun service is only supported on Windows."

    # Remove old legacy tasks
    for legacy in LEGACY_TASKS:
        subprocess.run(f'schtasks /delete /tn "{legacy}" /f', shell=True, capture_output=True)

    # 1. Register autorun on user logon (HKCU Run - reliable for all users without UAC)
    reg_ok = register_autorun()

    # 2. Also register scheduled task if possible
    pythonw = get_pythonw_path()
    cmd = (
        f'schtasks /create /tn "{SCHTASKS_NAME}" '
        f'/tr "\\"{pythonw}\\" -m bypass451.daemon run" '
        f'/sc onlogon /f'
    )
    subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace")

    # 3. Immediately start the daemon and enable system PAC
    started, msg = start_daemon(enable_pac=True)

    if reg_ok:
        return True, "451bypass auto-start registered for user logon and background daemon started."
    return False, "Failed to write autorun registry key."

def uninstall_task() -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Not running on Windows."

    # Stop daemon and disable PAC
    stop_daemon()

    # Remove autorun
    unregister_autorun()

    # Delete scheduled tasks
    subprocess.run(f'schtasks /delete /tn "{SCHTASKS_NAME}" /f', shell=True, capture_output=True)
    for legacy in LEGACY_TASKS:
        subprocess.run(f'schtasks /delete /tn "{legacy}" /f', shell=True, capture_output=True)

    return True, "451bypass background service uninstalled, autorun removed, and PAC disabled."

def get_task_status() -> Tuple[str, str]:
    if sys.platform != "win32":
        return "UNSUPPORTED", "Non-Windows OS"

    state, info_data = get_daemon_status()
    autorun = is_autorun_registered()

    if state == "ACTIVE":
        return "RUNNING", f"Active (PID: {info_data.get('pid')}, PAC Enabled, Autorun: {'Yes' if autorun else 'No'})"
    elif state == "RUNNING_NO_PAC":
        return "RUNNING_NO_PAC", f"Daemon running (PID: {info_data.get('pid')}), PAC Disabled"
    elif autorun:
        return "INSTALLED_STOPPED", "Autorun enabled, daemon stopped"
    else:
        return "NOT_INSTALLED", "Not configured for autorun"

def run_service_cycle() -> Tuple[bool, str]:
    cfg = load_config()
    log_service_message("Checking service health and reconciling domains...")
    
    if not cfg.account_id or not cfg.api_token:
        log_service_message("Credentials not configured. Skipping.")
        return False, "Cloudflare credentials not configured"

    if cfg.worker_name and cfg.subdomain:
        healthy, h_msg = check_worker_live_health(cfg.worker_name, cfg.subdomain)
        log_service_message(f"Worker health check: {h_msg}")

    duplicates, remaining, synced, msg = reconcile_custom_domains(cfg)
    if duplicates:
        log_service_message(f"Removed duplicates from custom.txt: {', '.join(duplicates)}")
    if synced:
        log_service_message(f"Synchronized {len(remaining)} custom domains to worker.")
    else:
        log_service_message(f"Custom domains check: {msg}")

    return True, msg
