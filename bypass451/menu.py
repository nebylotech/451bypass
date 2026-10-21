import os
import sys
import time
from . import __version__
from .config import AppConfig, load_config, save_config, CUSTOM_DOMAINS_PATH, CORE_DOMAINS_PATH
from .utils import print_table, Colors, colorize, success, info, warn, error, is_valid_domain, normalize_domain, mask_token
from .lists import (
    load_core_domains,
    load_custom_domains,
    get_active_domains,
    update_core_domains_from_remote,
    add_user_domain,
    remove_user_domain,
    reconcile_custom_domains,
    check_custom_file_changed,
    get_custom_domains_file
)
from .checker import perform_check
from .cloudflare import verify_token, check_worker_live_health
from .service import get_task_status
from .sync import sync_to_cloudflare
from .importer import run_interactive_import
from .diagnostics import run_diagnostics

def clear_screen() -> None:
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

def menu_check_service(cfg: AppConfig, pause: bool = True) -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"               451bypass -- Service Status Check               ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
    
    t0 = time.perf_counter()
    worker_online = False
    worker_detail = "Not configured"
    worker_latency = 0.0

    if cfg.worker_name and cfg.subdomain:
        worker_online, h_msg = check_worker_live_health(cfg.worker_name, cfg.subdomain)
        worker_latency = round((time.perf_counter() - t0) * 1000, 1)
        worker_detail = f"{h_msg} ({worker_latency}ms)" if worker_online else f"Unavailable: {h_msg}"

    token_valid = False
    token_status = "Not configured"
    if cfg.api_token:
        token_valid, t_msg = verify_token(cfg.api_token)
        token_status = f"Valid ({t_msg})" if token_valid else f"Invalid ({t_msg})"

    srv_state, srv_detail = get_task_status()
    
    active_domains = get_active_domains(cfg)
    sync_state = f"{cfg.last_sync_status} ({len(active_domains)} active domains)"
    if cfg.last_sync_time:
        sync_state += f" - Last: {cfg.last_sync_time[:19]}"

    gateway_url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev" if (cfg.worker_name and cfg.subdomain) else "Not set"

    w_color = Colors.GREEN if worker_online else Colors.RED
    t_color = Colors.GREEN if token_valid else Colors.RED
    s_color = Colors.GREEN if srv_state == "INSTALLED" else Colors.YELLOW

    print(f"  Gateway Base URL:    {colorize(gateway_url, Colors.CYAN)}")
    print(f"  Worker Health:       {colorize(worker_detail, w_color)}")
    print(f"  Cloudflare API:      {colorize(token_status, t_color)}")
    print(f"  Windows Service:     {colorize(f'{srv_state} ({srv_detail})', s_color)}")
    print(f"  Domain Sync:         {colorize(sync_state, Colors.WHITE)}")
    print()

    if worker_online and token_valid:
        print(success("Service is fully operational and accepting traffic."))
    else:
        print(warn("Service requires attention. Run Diagnostics [5] for full inspection."))

    print()
    if pause:
        input("Press ENTER to return to menu...")

def menu_test_domains(cfg: AppConfig, pause: bool = True) -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"              451bypass -- Test Domain Bypass                  ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")

    active_domains = get_active_domains(cfg)
    if not active_domains:
        print(warn("No active domains to test."))
        if pause:
            input("\nPress ENTER to return to menu...")
        return

    print(info(f"Testing {len(active_domains)} domains via Gateway..."))
    table_rows = []
    for d in active_domains:
        res = perform_check(d, cfg, use_gateway=True, timeout_sec=5.0)
        table_rows.append([d, res.status_label, f"{res.latency_ms}ms", res.details])

    print()
    print_table(["Domain / Endpoint", "Status", "Latency", "Bypass Diagnostics"], table_rows)
    print()
    if pause:
        input("Press ENTER to return to menu...")

def menu_update_domains(cfg: AppConfig) -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"              451bypass -- Update Core Domains                 ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")

    print(f"Remote repository URL:\n  {colorize(cfg.remote_domains_url, Colors.CYAN)}\n")
    print(info("Checking remote repository for updated domain rules..."))
    
    ok, msg, count = update_core_domains_from_remote(cfg)
    if ok:
        print(success(msg))
        print(info("Reconciling custom domains and uploading to Cloudflare..."))
        dups, rem, s_ok, s_msg = reconcile_custom_domains(cfg, force_sync=True)
        if dups:
            print(warn(f"Removed duplicates: {', '.join(dups)}"))
        print(success(s_msg) if s_ok else warn(s_msg))
    else:
        print(warn(msg))
        core_cnt = len(load_core_domains())
        user_cnt = len(load_custom_domains())
        print(info(f"Current local setup: {core_cnt} core domains, {user_cnt} custom domains."))

    print()
    input("Press ENTER to return to menu...")

def menu_diagnostics(cfg: AppConfig) -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"              451bypass -- System Diagnostics                  ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    run_diagnostics(cfg)
    print()
    input("Press ENTER to return to menu...")

def main_menu(cfg: AppConfig) -> None:
    last_notice = None

    while True:
        if check_custom_file_changed(cfg):
            dups, rem, syn, msg = reconcile_custom_domains(cfg)
            if dups:
                last_notice = f"Auto-cleaned {len(dups)} duplicates from custom.txt: {', '.join(dups)}"
            elif syn:
                last_notice = f"Auto-synchronized {len(rem)} custom domains to worker."

        clear_screen()
        core_cnt = len(load_core_domains())
        user_cnt = len(load_custom_domains())
        total_cnt = len(get_active_domains(cfg))

        print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
        print(f"     451bypass v{__version__} -- AI Gateway & Regional Restriction Bypass")
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
        print(f"  Active Domains: {colorize(str(total_cnt), Colors.GREEN)} ({core_cnt} core, {user_cnt} custom)")
        print(f"  Gateway URL:    {colorize(f'https://{cfg.worker_name}.{cfg.subdomain}.workers.dev' if cfg.subdomain else 'Not configured', Colors.CYAN)}")
        if last_notice:
            print(f"  {colorize('[Notice]', Colors.YELLOW)} {last_notice}")
            last_notice = None
        print(f"{Colors.BOLD}---------------------------------------------------------------{Colors.RESET}")
        print("  [1] Check Service     - Verify Gateway, Worker, and Task health")
        print("  [2] Test Domains      - Probe active endpoints for 451/403 bypass")
        print("  [3] Update Domains    - Check and pull latest domains from GitHub")
        print("  [4] Custom Domains    - Edit personal custom.txt in Notepad (auto-sync)")
        print("  [5] Run Diagnostics   - Full 8-point system diagnostics")
        print("  [0] Exit")
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
        
        choice = input("Select an option [0-5]: ").strip()
        if choice == "1":
            menu_check_service(cfg)
        elif choice == "2":
            menu_test_domains(cfg)
        elif choice == "3":
            menu_update_domains(cfg)
        elif choice == "4":
            run_interactive_import(cfg)
        elif choice == "5":
            menu_diagnostics(cfg)
        elif choice == "0":
            clear_screen()
            print("Exiting 451bypass.")
            sys.exit(0)
