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

@dataclass
class DiagnosticItem:
    name: str
    status: str
    latency_ms: float
    details: str
    action: str

def run_diagnostics(cfg: AppConfig, save_path: Optional[Path] = None) -> List[DiagnosticItem]:
    results: List[DiagnosticItem] = []

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
                action="Run '51b' and configure Cloudflare credentials."
            ))
    else:
        results.append(DiagnosticItem(
            name="Local Config",
            status="FAIL",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details="Configuration file not found.",
            action="Run installer or '51b' to initialize config."
        ))

    t0 = time.perf_counter()
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    path_env = os.environ.get("PATH", "")
    in_path = "51-bypass" in path_env or "51b" in path_env
    results.append(DiagnosticItem(
        name="Python & PATH",
        status="PASS" if in_path else "WARN",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Python {py_ver} (In PATH: {'Yes' if in_path else 'No'})",
        action="None" if in_path else "Add %LOCALAPPDATA%\\51-bypass to system PATH."
    ))

    t0 = time.perf_counter()
    net_ok = False
    try:
        req = urllib.request.Request("https://1.1.1.1", headers={"User-Agent": "51-BYPASS/1.0"})
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

    t0 = time.perf_counter()
    dns_ok = False
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

    t0 = time.perf_counter()
    tls_ok = False
    tls_msg = ""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("api.cloudflare.com", 443), timeout=4.0) as sock:
            with ctx.wrap_socket(sock, server_hostname="api.cloudflare.com") as ssock:
                tls_msg = ssock.version()
                tls_ok = True
    except Exception as e:
        tls_msg = str(e)
    results.append(DiagnosticItem(
        name="TLS Handshake",
        status="PASS" if tls_ok else "FAIL",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Negotiated {tls_msg}" if tls_ok else f"TLS failure: {tls_msg}",
        action="None" if tls_ok else "Check Windows CA certificate store."
    ))

    t0 = time.perf_counter()
    if cfg.api_token:
        valid, status_msg = verify_token(cfg.api_token)
        results.append(DiagnosticItem(
            name="Cloudflare API",
            status="PASS" if valid else "FAIL",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details=f"Token valid: {status_msg}" if valid else f"Token invalid: {status_msg}",
            action="None" if valid else "Re-issue Cloudflare API Token with Edit Workers permission."
        ))
    else:
        results.append(DiagnosticItem(
            name="Cloudflare API",
            status="SKIP",
            latency_ms=0.0,
            details="Token not configured",
            action="Set API token in config."
        ))

    t0 = time.perf_counter()
    if cfg.subdomain and cfg.worker_name:
        healthy, h_msg = check_worker_live_health(cfg.worker_name, cfg.subdomain)
        results.append(DiagnosticItem(
            name="Worker /health",
            status="PASS" if healthy else "WARN",
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            details=f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev: {h_msg}",
            action="None" if healthy else "Run '51b sync' or redeploy worker."
        ))
    else:
        results.append(DiagnosticItem(
            name="Worker /health",
            status="SKIP",
            latency_ms=0.0,
            details="Subdomain or worker name not set",
            action="Configure worker settings."
        ))

    t0 = time.perf_counter()
    active_count = len(get_active_domains(cfg))
    sync_ok = (cfg.last_sync_status == "OK" and cfg.last_sync_domain_count == active_count)
    results.append(DiagnosticItem(
        name="Domain Sync",
        status="PASS" if sync_ok else "WARN",
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        details=f"Status: {cfg.last_sync_status} ({active_count} active domains)",
        action="None" if sync_ok else "Synchronize domains to Cloudflare."
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
