import sys
import argparse
from pathlib import Path
from . import __version__, __product_name__, __command_name__
from .config import load_config, save_config, CUSTOM_DOMAINS_PATH, CORE_DOMAINS_PATH
from .utils import success, info, warn, error, print_table, normalize_domain, is_valid_domain
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
from .sync import sync_to_cloudflare, export_worker_script
from .diagnostics import run_diagnostics
from .importer import run_interactive_import, parse_domains_from_text
from .service import install_task, uninstall_task, get_task_status, run_service_cycle
from .menu import main_menu, menu_check_service, menu_test_domains, menu_setup

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__command_name__,
        description=f"{__product_name__}: Zero-Cost Regional Restriction Bypass & AI Gateway",
    )
    parser.add_argument("-v", "--version", action="version", version=f"{__product_name__} v{__version__}")
    
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    test_parser = subparsers.add_parser("test", help="Test connectivity and 451/403 bypass for domain")
    test_parser.add_argument("domain", nargs="?", default="integrate.api.nvidia.com", help="Domain to test")
    test_parser.add_argument("api_key", nargs="?", default=None, help="Optional API key for authorization test")

    subparsers.add_parser("check-service", help="Check gateway and background service status")
    subparsers.add_parser("status", help="Alias for check-service")

    subparsers.add_parser("update", help="Update core domains from remote repository and sync")

    domains_parser = subparsers.add_parser("domains", help="Manage active domains")
    domains_sub = domains_parser.add_subparsers(dest="domains_action", help="Domain action")
    domains_sub.add_parser("list", help="List all active domains (core and custom)")
    
    d_add = domains_sub.add_parser("add", help="Add domain to personal custom rules")
    d_add.add_argument("hostname", help="Hostname to add")
    
    d_rem = domains_sub.add_parser("remove", help="Remove domain from personal rules")
    d_rem.add_argument("hostname", help="Hostname to remove")

    subparsers.add_parser("import", help="Interactive text editor custom domain import")

    diag_parser = subparsers.add_parser("diagnostics", help="Run comprehensive diagnostics")
    diag_parser.add_argument("--save", help="Optional path to save JSON report")

    subparsers.add_parser("sync", help="Force sync active rules with Cloudflare")
    subparsers.add_parser("push", help="Alias for sync")

    srv_parser = subparsers.add_parser("service", help="Manage Windows background synchronization service")
    srv_parser.add_argument("action", choices=["install", "uninstall", "status", "run-once"], help="Service action")

    subparsers.add_parser("uninstall", help="Uninstall 451bypass, delete worker, and clean system")
    subparsers.add_parser("version", help="Print version information")

    setup_p = subparsers.add_parser("setup", help="Run 1-click Cloudflare onboarding setup")
    setup_p.add_argument("--force", action="store_true", help="Force re-authentication")
    subparsers.add_parser("login", help="Alias for setup")

    return parser

def main() -> None:
    cfg = load_config()
    parser = build_parser()

    if check_custom_file_changed(cfg):
        dups, rem, syn, msg = reconcile_custom_domains(cfg)
        if dups:
            print(warn(f"Removed {len(dups)} duplicate custom domains matching core: {', '.join(dups)}"))
        if syn:
            print(success(f"Custom domains updated: {msg}"))

    if len(sys.argv) == 1:
        try:
            main_menu(cfg)
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)
        return

    args = parser.parse_args()

    try:
        if args.subcommand == "test":
            domain = normalize_domain(args.domain)
            print(info(f"Testing endpoint '{domain}' via Gateway..."))
            res = perform_check(domain, cfg, use_gateway=True, api_key=args.api_key)
            print(f"Target:      {res.target}")
            print(f"URL:         {res.url}")
            print(f"HTTP Status: {res.status_code or 'ERROR'} {res.status_text}")
            print(f"Latency:     {res.latency_ms} ms")
            print(f"Class:       {res.classification}")
            print(f"Details:     {res.details}")
            sys.exit(0 if res.status_code in (200, 401) else 1)

        elif args.subcommand in ("check-service", "status"):
            menu_check_service(cfg, pause=False)

        elif args.subcommand == "update":
            print(info(f"Checking remote domain repository: {cfg.remote_domains_url}"))
            ok, msg, count = update_core_domains_from_remote(cfg)
            if ok:
                print(success(msg))
                print(info("Checking and reconciling custom domains..."))
                dups, rem, syn, s_msg = reconcile_custom_domains(cfg, force_sync=True)
                if dups:
                    print(warn(f"Removed duplicates: {', '.join(dups)}"))
                print(success(s_msg) if syn else warn(s_msg))
            else:
                print(warn(msg))

        elif args.subcommand == "domains":
            if not args.domains_action or args.domains_action == "list":
                core = load_core_domains()
                custom = load_custom_domains()
                c_file = get_custom_domains_file()
                print(f"Core Domains ({len(core)}):")
                for d in core:
                    is_def = " [DEFAULT]" if d == cfg.default_domain else ""
                    print(f"  • {d}{is_def}")
                print(f"\nUser Custom Domains ({len(custom)} in {c_file.name}):")
                if not custom:
                    print("  (None)")
                for d in custom:
                    print(f"  • {d}")
            elif args.domains_action == "add":
                dom = normalize_domain(args.hostname)
                if not is_valid_domain(dom):
                    print(error("Invalid domain format."))
                    sys.exit(1)
                ok, msg = add_user_domain(dom, cfg)
                if ok:
                    print(success(f"Added '{dom}' to your custom domains ({get_custom_domains_file().name})."))
                    print(success(f"Synchronized with Cloudflare Worker '{cfg.worker_name}'."))
                else:
                    print(warn(msg))
            elif args.domains_action == "remove":
                dom = normalize_domain(args.hostname)
                if remove_user_domain(dom, cfg):
                    print(success(f"Removed '{dom}' from your custom domains."))
                    print(success(f"Synchronized with Cloudflare Worker '{cfg.worker_name}'."))
                else:
                    print(warn(f"Domain '{dom}' not found in custom domains."))

        elif args.subcommand == "import":
            run_interactive_import(cfg)

        elif args.subcommand == "diagnostics":
            save_path = Path(args.save) if args.save else None
            run_diagnostics(cfg, save_path=save_path)

        elif args.subcommand in ("sync", "push"):
            print(info("Reconciling custom domains and synchronizing with Cloudflare..."))
            dups, rem, ok, msg = reconcile_custom_domains(cfg, force_sync=True)
            if dups:
                print(warn(f"Removed {len(dups)} duplicate domains already in core: {', '.join(dups)}"))
            print(success(msg) if ok else error(msg))

        elif args.subcommand == "service":
            if args.action == "install":
                ok, msg = install_task()
                print(success(msg) if ok else error(msg))
            elif args.action == "uninstall":
                ok, msg = uninstall_task()
                print(success(msg) if ok else error(msg))
            elif args.action == "status":
                state, detail = get_task_status()
                print(f"Service Task State: {state}")
                print(f"Details:            {detail}")
            elif args.action == "run-once":
                ok, msg = run_service_cycle()
                print(success(msg) if ok else error(msg))

        elif args.subcommand == "uninstall":
            import subprocess
            from .config import PRIMARY_CONFIG_DIR
            un_candidates = [
                Path(__file__).resolve().parent.parent / "uninstall.ps1",
                PRIMARY_CONFIG_DIR / "uninstall.ps1"
            ]
            target_ps = None
            for cand in un_candidates:
                if cand.exists():
                    target_ps = cand
                    break
            if target_ps and sys.platform == "win32":
                subprocess.run(f'powershell -ExecutionPolicy Bypass -File "{target_ps}"', shell=True)
            else:
                print("Uninstallation script not found or non-Windows system.")

        elif args.subcommand == "version":
            print(f"{__product_name__} v{__version__}")

        elif args.subcommand in ("setup", "login"):
            ok = menu_setup(cfg)
            if not ok:
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)

if __name__ == "__main__":
    main()
