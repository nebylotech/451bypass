import os
import sys
import subprocess
import datetime
from pathlib import Path
from typing import Tuple
from .config import load_config, PRIMARY_CONFIG_DIR
from .lists import reconcile_custom_domains
from .cloudflare import check_worker_live_health
from .utils import success, info, warn, error

TASK_NAME = "451bypass-Sync"
LEGACY_TASK_NAME = "51-BYPASS-Sync"
LOG_FILE = PRIMARY_CONFIG_DIR / "service.log"

def log_service_message(msg: str) -> None:
    PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

def run_service_cycle() -> Tuple[bool, str]:
    cfg = load_config()
    log_service_message("Starting background health and sync cycle...")
    
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

def install_task() -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Windows background task is only supported on Windows."

    python_dir = Path(sys.executable).parent
    pythonw_candidate = python_dir / "pythonw.exe"
    runner_exe = str(pythonw_candidate if pythonw_candidate.exists() else sys.executable)

    installed_script = PRIMARY_CONFIG_DIR / "451b.py"
    if not installed_script.exists():
        installed_script = PRIMARY_CONFIG_DIR / "51b.py"
    if not installed_script.exists():
        installed_script = Path(__file__).resolve().parent.parent / "451b.py"

    subprocess.run(f'schtasks /delete /tn "{LEGACY_TASK_NAME}" /f', shell=True, capture_output=True, text=True)

    cmd = (
        f'schtasks /create /tn "{TASK_NAME}" '
        f'/tr "\"{runner_exe}\" \"{installed_script}\" service run-once" '
        f'/sc daily /st 04:00 /f'
    )

    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Windows scheduled task '{TASK_NAME}' registered successfully (daily at 04:00)."
        return False, f"Failed to register task: {res.stderr.strip() or res.stdout.strip()}"
    except Exception as e:
        return False, str(e)

def uninstall_task() -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Not running on Windows."

    subprocess.run(f'schtasks /delete /tn "{LEGACY_TASK_NAME}" /f', shell=True, capture_output=True, text=True)
    cmd = f'schtasks /delete /tn "{TASK_NAME}" /f'
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0 or "cannot find" in res.stderr.lower():
            return True, f"Windows task '{TASK_NAME}' removed."
        return False, f"Failed to remove task: {res.stderr.strip()}"
    except Exception as e:
        return False, str(e)

def get_task_status() -> Tuple[str, str]:
    if sys.platform != "win32":
        return "UNSUPPORTED", "Non-Windows OS"

    cmd = f'schtasks /query /tn "{TASK_NAME}" /fo LIST'
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            status_line = "Active"
            for line in res.stdout.splitlines():
                if "Status:" in line or "Состояние:" in line:
                    status_line = line.split(":", 1)[1].strip()
            return "INSTALLED", status_line
        
        legacy_res = subprocess.run(f'schtasks /query /tn "{LEGACY_TASK_NAME}" /fo LIST', shell=True, capture_output=True, text=True)
        if legacy_res.returncode == 0:
            return "INSTALLED", "Legacy task active"

        return "NOT_INSTALLED", "Task not registered in Windows Task Scheduler"
    except Exception as e:
        return "ERROR", str(e)
