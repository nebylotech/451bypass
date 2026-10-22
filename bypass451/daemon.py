import os
import sys
import time
import subprocess
import signal
from pathlib import Path
from typing import Tuple, Optional

from .config import PRIMARY_CONFIG_DIR, load_config
from .proxy import (
    run_server,
    enable_system_pac,
    disable_system_pac,
    enable_system_env_proxy,
    disable_system_env_proxy,
    is_system_pac_enabled,
    is_proxy_running,
    DEFAULT_PROXY_PORT
)
from .utils import success, info, warn, error

PID_FILE = PRIMARY_CONFIG_DIR / "daemon.pid"
DAEMON_LOG = PRIMARY_CONFIG_DIR / "daemon.log"

def get_pythonw_path() -> str:
    py_dir = Path(sys.executable).parent
    pythonw = py_dir / "pythonw.exe"
    if pythonw.exists():
        return str(pythonw)
    return sys.executable

def get_running_pid() -> Optional[int]:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                kernel32.CloseHandle(h_proc)
                return pid
        else:
            os.kill(pid, 0)
            return pid
    except Exception:
        pass
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    return None

def start_daemon(enable_pac: bool = True, port: int = DEFAULT_PROXY_PORT) -> Tuple[bool, str]:
    existing_pid = get_running_pid()
    if existing_pid and is_proxy_running(port):
        if enable_pac and not is_system_pac_enabled(port):
            enable_system_pac(port)
        return True, f"Daemon already running (PID: {existing_pid})"

    if PID_FILE.exists():
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    python_bin = get_pythonw_path()
    pkg_dir = Path(__file__).resolve().parent.parent
    install_dir = PRIMARY_CONFIG_DIR

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{pkg_dir};{install_dir};{env.get('PYTHONPATH', '')}"

    PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    cmd = [python_bin, "-m", "bypass451.daemon", "run"]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(pkg_dir),
            env=env,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        PID_FILE.write_text(str(proc.pid), encoding="utf-8")

        # Wait up to 4 seconds for port to open
        t0 = time.time()
        while time.time() - t0 < 4.0:
            if is_proxy_running(port):
                break
            time.sleep(0.2)

        if not is_proxy_running(port):
            return False, "Daemon process spawned but proxy port 10451 did not respond in time"

        if enable_pac:
            enable_system_pac(port)
            enable_system_env_proxy(port)

        return True, f"451bypass daemon started successfully (PID: {proc.pid})"
    except Exception as e:
        return False, f"Failed to start daemon: {e}"

def stop_daemon() -> Tuple[bool, str]:
    disable_system_pac()
    disable_system_env_proxy()
    pid = get_running_pid()
    
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    return True, "451bypass daemon stopped and system PAC disabled"

def get_daemon_status(port: int = DEFAULT_PROXY_PORT) -> Tuple[str, dict]:
    pid = get_running_pid()
    running = is_proxy_running(port)
    pac_enabled = is_system_pac_enabled(port)

    info_dict = {
        "pid": pid,
        "proxy_running": running,
        "pac_enabled": pac_enabled,
        "port": port
    }

    if running:
        if pac_enabled:
            return "ACTIVE", info_dict
        return "RUNNING_NO_PAC", info_dict
    elif pid:
        return "UNRESPONSIVE", info_dict
    else:
        return "STOPPED", info_dict

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        enable_system_pac()
        if is_proxy_running():
            sys.exit(0)
        import traceback
        try:
            PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
            with open(DAEMON_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon starting PID {os.getpid()}...\n")
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
    elif len(sys.argv) > 1 and sys.argv[1] == "start":
        ok, msg = start_daemon()
        print(msg)
        sys.exit(0 if ok else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "stop":
        ok, msg = stop_daemon()
        print(msg)
        sys.exit(0 if ok else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        state, info_data = get_daemon_status()
        print(f"Status: {state}, Info: {info_data}")
        sys.exit(0)
    else:
        print("Usage: python -m bypass451.daemon [run|start|stop|status]")

if __name__ == "__main__":
    main()
