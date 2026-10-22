#!/usr/bin/env pythonw
"""
451bypass Windows Background Service & Logon Auto-Start
Launches the local proxy daemon and ensures Windows system PAC is enabled.
Runs completely silently in the background without opening a console window.
"""
import os
import sys
import time
import traceback
from pathlib import Path

# Ensure the parent directory is in sys.path
base_dir = Path(__file__).resolve().parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

# Fallback for primary config dir if running from elsewhere
local_appdata = os.environ.get("LOCALAPPDATA", "")
if local_appdata:
    install_dir = Path(local_appdata) / "451bypass"
    if str(install_dir) not in sys.path:
        sys.path.insert(0, str(install_dir))

def main():
    try:
        from bypass451.config import PRIMARY_CONFIG_DIR
        from bypass451.daemon import PID_FILE, DAEMON_LOG, is_proxy_running
        from bypass451.proxy import enable_system_pac, enable_system_env_proxy, run_server
    except ImportError as e:
        err_log = Path(local_appdata) / "451bypass" / "daemon.log" if local_appdata else Path("daemon.log")
        err_log.parent.mkdir(parents=True, exist_ok=True)
        with open(err_log, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Autostart import error: {e}\n")
        sys.exit(1)

    PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Ensure system PAC and environment proxy are enabled immediately upon logon
    enable_system_pac()
    enable_system_env_proxy()

    # 2. If proxy is already running, exit cleanly
    if is_proxy_running():
        sys.exit(0)

    # 3. Start local daemon server
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        with open(DAEMON_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Logon autostart running daemon PID {os.getpid()}...\n")
        run_server()
    except Exception as e:
        with open(DAEMON_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon crashed: {e}\n{traceback.format_exc()}\n")
    finally:
        with open(DAEMON_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon stopped.\n")
        try:
            if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

if __name__ == "__main__":
    main()
