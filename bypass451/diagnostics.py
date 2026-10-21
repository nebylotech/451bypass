import os
import sys
import time
import socket
import ssl
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from .config import AppConfig, PRIMARY_CONFIG_PATH
from .utils import print_table, Colors, colorize, mask_token
from .cloudflare import verify_token, check_worker_live_health
from .lists import get_active_domains
from .proxy import is_proxy_running, is_system_pac_enabled, DEFAULT_PROXY_PORT
from .daemon import get_daemon_status

@dataclass
class DiagnosticItem:
    name: str
    status: str
    latency_ms: float
    details: str
    action: str

def run_diagnostics(cfg: AppConfig, save_path: Optional[Path] = None) -> List[DiagnosticItem]:
    results: List[DiagnosticItem] = []

    # 1. Local Config
    t0 = time.perf_counter()
    if PRIMARY_CONFIG_PATH.exists():
        if cfg.account_id and cfg.api_token:
            results.append(DiagnosticItem(
                name="Local Config",
                status="PASS",
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                details=f"Valid (Account: {mask_token(cfg.account_id)}, Token: {mask_token(cfg.api_token)})",
                action="None"
            ))
        else:
            results.append(DiagnosticItem(
                name="Local Config",
                status="WARN",
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                details="Config file present but Cloudflare credentials incomplete.",
                action="Run '451b setup' to configure Cloudflare token."
            ))
    else:
        results.append(DiagnosticItem(
            name="Local Config",
            status="FAIL",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details="Configuration file not found.",
            action="Run installer or '451b setup'."
        ))

    # 2. Python & PATH
    t0 = time.perf_counter()
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    path_env = os.environ.get("PATH", "")
    in_path = "451bypass" in path_env or "451b" in path_env or "51-bypass" in path_env or "51b" in path_env
    results.append(DiagnosticItem(
        name="Python & PATH",
        status="PASS" if in_path else "WARN",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Python {py_ver} (In PATH: {'Yes' if in_path else 'No'})",
        action="None" if in_path else "Add %LOCALAPPDATA%\\451bypass to system PATH."
    ))

    # 3. Internet connectivity
    t0 = time.perf_counter()
    net_ok = False
    try:
        req = urllib.request.Request("https://1.1.1.1", headers={"User-Agent": "451bypass/1.0"})
        with urllib.request.urlopen(req, timeout=4.0):
            net_ok = True
    except Exception:
        pass
    results.append(DiagnosticItem(
        name="Internet",
        status="PASS" if net_ok else "FAIL",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details="Connected to global internet" if net_ok else "Failed to reach 1.1.1.1",
        action="None" if net_ok else "Check local network or proxy connection."
    ))

    # 4. DNS Resolution
    t0 = time.perf_counter()
    dns_ok = False
    ip = ""
    try:
        ip = socket.gethostbyname("integrate.api.nvidia.com")
        dns_ok = bool(ip)
    except Exception as e:
        ip = str(e)
    results.append(DiagnosticItem(
        name="DNS Resolution",
        status="PASS" if dns_ok else "FAIL",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Resolved nvidia API to {ip}" if dns_ok else f"DNS lookup failed: {ip}",
        action="None" if dns_ok else "Check local DNS resolver settings."
    ))

    # 5. TLS Handshake
    t0 = time.perf_counter()
    tls_ok = False
    tls_ver = ""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("api.cloudflare.com", 443), timeout=4.0) as sock:
            with ctx.wrap_socket(sock, server_hostname="api.cloudflare.com") as ssock:
                tls_ver = ssock.version()
                tls_ok = True
    except Exception as e:
        tls_ver = str(e)
    results.append(DiagnosticItem(
        name="TLS Handshake",
        status="PASS" if tls_ok else "FAIL",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Negotiated {tls_ver}" if tls_ok else f"TLS Handshake failed: {tls_ver}",
        action="None" if tls_ok else "Verify system SSL/TLS root certificates."
    ))

    # 6. Cloudflare API Token
    t0 = time.perf_counter()
    if cfg.api_token:
        valid, msg = verify_token(cfg.api_token)
        results.append(DiagnosticItem(
            name="Cloudflare API",
            status="PASS" if valid else "FAIL",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details=f"Token valid: {msg}" if valid else f"Invalid token: {msg}",
            action="None" if valid else "Run '451b setup' to reconnect token."
        ))
    else:
        results.append(DiagnosticItem(
            name="Cloudflare API",
            status="WARN",
            latency_ms=0.0,
            details="Token not configured",
            action="Run '451b setup' to connect Cloudflare."
        ))

    # 7. Worker Health
    t0 = time.perf_counter()
    if cfg.subdomain and cfg.worker_name:
        healthy, h_msg = check_worker_live_health(cfg.worker_name, cfg.subdomain, secret=cfg.gateway_secret)
        results.append(DiagnosticItem(
            name="Worker /health",
            status="PASS" if healthy else "WARN",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details=f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev: {h_msg}",
            action="None" if healthy else "Run '451b sync' or redeploy worker."
        ))
    else:
        results.append(DiagnosticItem(
            name="Worker /health",
            status="SKIP",
            latency_ms=0.0,
            details="Subdomain or worker name not set",
            action="Configure worker settings."
        ))

    # 8. Local Daemon Process
    t0 = time.perf_counter()
    d_state, d_info = get_daemon_status()
    proxy_up = d_info.get("proxy_running", False)
    results.append(DiagnosticItem(
        name="Local Daemon",
        status="PASS" if proxy_up else "WARN",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Listening on 127.0.0.1:{DEFAULT_PROXY_PORT} (PID: {d_info.get('pid')})" if proxy_up else "Not running",
        action="None" if proxy_up else "Run '451b on' or select [1] in menu."
    ))

    # 9. Windows PAC (System Bypass)
    t0 = time.perf_counter()
    pac_ok = is_system_pac_enabled()
    results.append(DiagnosticItem(
        name="Windows PAC",
        status="PASS" if pac_ok else "WARN",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Configured (http://127.0.0.1:{DEFAULT_PROXY_PORT}/proxy.pac)" if pac_ok else "Disabled in Windows Settings",
        action="None" if pac_ok else "Run '451b on' to activate system bypass."
    ))

    # 10. Live Tunnel Probe (if daemon running)
    if proxy_up:
        t0 = time.perf_counter()
        tunnel_ok = False
        t_msg = ""
        import subprocess
        try:
            cmd = ["curl.exe", "-s", "-i", "-x", f"http://127.0.0.1:{DEFAULT_PROXY_PORT}", "https://integrate.api.nvidia.com/v1/models"]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=6.0)
            if "200 OK" in res.stdout or "401" in res.stdout:
                tunnel_ok = True
                t_msg = "200 OK — NVIDIA NIM reachable via tunnel"
            elif "Connection Established" in res.stdout:
                tunnel_ok = True
                t_msg = "Connected via Cloudflare WebSocket Tunnel"
            else:
                first_line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else res.stderr.strip()
                t_msg = first_line or "No response"
        except Exception as e:
            t_msg = str(e)

        results.append(DiagnosticItem(
            name="Tunnel Probe",
            status="PASS" if tunnel_ok else "WARN",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details=f"nvidia NIM via Tunnel: {t_msg}",
            action="None" if tunnel_ok else "Check Cloudflare Worker logs and network."
        ))

    table_rows = []
    for item in results:
        status_colored = item.status
        if item.status == "PASS":
            status_colored = colorize("PASS", Colors.GREEN)
        elif item.status == "WARN":
            status_colored = colorize("WARN", Colors.YELLOW)
        elif item.status == "FAIL":
            status_colored = colorize("FAIL", Colors.RED)
        elif item.status == "SKIP":
            status_colored = colorize("SKIP", Colors.DIM)
            
        table_rows.append([
            item.name,
            status_colored,
            f"{item.latency_ms}ms",
            item.details,
            item.action
        ])

    print()
    print_table(["Probe", "Status", "Latency", "Details", "Recommended Action"], table_rows)
    print()

    pass_cnt = sum(1 for r in results if r.status == "PASS")
    warn_cnt = sum(1 for r in results if r.status == "WARN")
    fail_cnt = sum(1 for r in results if r.status == "FAIL")
    skip_cnt = sum(1 for r in results if r.status == "SKIP")

    print(f"Summary: {colorize(f'{pass_cnt} PASSED', Colors.GREEN)}, "
          f"{colorize(f'{warn_cnt} WARNINGS', Colors.YELLOW)}, "
          f"{colorize(f'{fail_cnt} FAILED', Colors.RED)}, "
          f"{colorize(f'{skip_cnt} SKIPPED', Colors.DIM)}")

    if save_path:
        report_data = {
            "summary": {"pass": pass_cnt, "warn": warn_cnt, "fail": fail_cnt, "skip": skip_cnt},
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "details": r.details,
                    "action": r.action
                }
                for r in results
            ]
        }
        try:
            save_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
            print(f"Saved diagnostic report to: {save_path}")
        except Exception as e:
            print(f"Failed to save report: {e}")

    return results
