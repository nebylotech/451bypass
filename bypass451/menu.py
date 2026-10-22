import os
import sys
import time
import webbrowser
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
from .cloudflare import verify_token, check_worker_live_health, list_accounts, get_subdomain
from .service import get_task_status, install_task, uninstall_task
from .daemon import start_daemon, stop_daemon, get_daemon_status
from .proxy import is_system_pac_enabled, enable_system_pac, disable_system_pac
from .sync import sync_to_cloudflare
from .importer import run_interactive_import
from .diagnostics import run_diagnostics

def clear_screen() -> None:
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

def pause_prompt(prompt: str = "Нажмите ENTER, чтобы вернуться в меню...") -> None:
    try:
        input(f"\n{prompt}")
    except KeyboardInterrupt:
        pass

def toggle_bypass(cfg: AppConfig) -> None:
    clear_screen()
    d_state, info_data = get_daemon_status()
    pac_on = is_system_pac_enabled()

    if pac_on or d_state == "ACTIVE":
        print(info("Выключение системного обхода..."))
        stop_daemon()
        print(warn("Системный обход Windows ВЫКЛЮЧЕН."))
        print(info("Трафик всех сайтов теперь идёт напрямую."))
    else:
        print(info("Включение системного обхода..."))
        ok, msg = start_daemon(enable_pac=True)
        if ok:
            print(success("Системный обход Windows ВКЛЮЧЕН!"))
            print(info("477+ заблокированных сайтов направляются в обход."))
            print(info("Банки, Госуслуги и игры работают напрямую."))
        else:
            print(error(f"Не удалось запустить обход: {msg}"))

    pause_prompt()

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
        worker_online, h_msg = check_worker_live_health(cfg.worker_name, cfg.subdomain, secret=cfg.gateway_secret)
        worker_latency = round((time.perf_counter() - t0) * 1000, 1)
        worker_detail = f"{h_msg} ({worker_latency}ms)" if worker_online else f"Unavailable: {h_msg}"

    token_valid = False
    token_status = "Not configured"
    if cfg.api_token:
        token_valid, t_msg = verify_token(cfg.api_token)
        token_status = f"Valid ({t_msg})" if token_valid else f"Invalid ({t_msg})"

    srv_state, srv_detail = get_task_status()
    d_state, d_info = get_daemon_status()
    pac_on = is_system_pac_enabled()
    
    active_domains = get_active_domains(cfg)
    sync_state = f"{cfg.last_sync_status} ({len(active_domains)} active domains)"
    if cfg.last_sync_time:
        sync_state += f" - Last: {cfg.last_sync_time[:19]}"

    gateway_url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev" if (cfg.worker_name and cfg.subdomain) else "Not set"

    w_color = Colors.GREEN if worker_online else Colors.RED
    t_color = Colors.GREEN if token_valid else Colors.RED
    d_color = Colors.GREEN if d_state == "ACTIVE" else Colors.YELLOW
    pac_color = Colors.GREEN if pac_on else Colors.YELLOW

    pac_str = "ВКЛЮЧЕН (127.0.0.1:10451/proxy.pac)" if pac_on else "ВЫКЛЮЧЕН"
    daemon_str = f"Работает (PID: {d_info.get('pid')})" if d_state == "ACTIVE" else "Остановлен"

    print(f"  Системный обход Windows: {colorize(pac_str, pac_color)}")
    print(f"  Локальный демон:         {colorize(daemon_str, d_color)}")
    print(f"  Шлюз Cloudflare:         {colorize(worker_detail, w_color)}")
    print(f"  Адрес шлюза:             {colorize(gateway_url, Colors.CYAN)}")
    print(f"  Cloudflare API:          {colorize(token_status, t_color)}")
    print(f"  Служба автозапуска:      {colorize(f'{srv_state} ({srv_detail})', Colors.WHITE)}")
    print(f"  База доменов:            {colorize(sync_state, Colors.WHITE)}")
    print()

    if worker_online and token_valid and pac_on:
        print(success("Все системы работают идеально! Обход активен."))
    elif not pac_on:
        print(warn("Внимание: системный обход выключен. Нажмите [1] в главном меню для включения."))
    else:
        print(warn("Служба требует внимания. Запустите Диагностику [5] для проверки."))

    if pause:
        pause_prompt()

def run_test_stream(domains: list, cfg: AppConfig, title: str = "Тестирование сайтов") -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"       451bypass -- {title} ({len(domains)} сайтов)           ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"  {colorize('[Подсказка]', Colors.CYAN)} Нажмите {colorize('Ctrl+C', Colors.YELLOW)}, чтобы прервать проверку в любой момент\n")

    table_rows = []
    passed = 0
    total = len(domains)

    try:
        for idx, d in enumerate(domains, 1):
            sys.stdout.write(f"  [{idx}/{total}] Проверка {d:<34} ... ")
            sys.stdout.flush()

            res = perform_check(d, cfg, timeout_sec=5.5)
            table_rows.append([d, res.status_label, f"{res.latency_ms}ms", res.details])

            if "OK" in res.status_label:
                passed += 1

            sys.stdout.write(f"\r  [{idx}/{total}] {d:<34} -> {res.status_label} ({res.latency_ms}ms)\n")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print(f"\n  {colorize('[!]', Colors.YELLOW)} Тестирование прервано пользователем (проверено {len(table_rows)} из {total}).")

    print(f"\n{Colors.BOLD}---------------------------------------------------------------{Colors.RESET}")
    print(f"  Результат: проверено {len(table_rows)} сайтов, успешно: {colorize(f'{passed}/{len(table_rows)}', Colors.GREEN if passed == len(table_rows) and passed > 0 else Colors.YELLOW)}")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    pause_prompt()

def menu_test_domains(cfg: AppConfig, pause: bool = True) -> None:
    while True:
        clear_screen()
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
        print(f"              451bypass -- Тестирование сайтов                 ")
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
        print("  [1] Быстрый тест ключевых сервисов (ChatGPT, Gemini, Claude, Grok, NVIDIA, Notion)")
        print("  [2] Проверить конкретный сайт (ввести домен вручную)")
        print("  [3] Проверить все активные сайты из базы (с возможностью прервать)")
        print("  [0] Назад в главное меню")
        print(f"\n{Colors.BOLD}==============================================================={Colors.RESET}\n")

        try:
            choice = input("Выберите вариант [0-3]: ").strip()
        except KeyboardInterrupt:
            return

        if choice == "1":
            quick_list = [
                "integrate.api.nvidia.com",
                "gemini.google.com",
                "chatgpt.com",
                "claude.ai",
                "grok.com",
                "notion.so",
                "build.nvidia.com",
                "api.perplexity.ai"
            ]
            run_test_stream(quick_list, cfg, title="Быстрый тест ключевых сервисов")
        elif choice == "2":
            clear_screen()
            print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
            print(f"              Проверка конкретного домена                      ")
            print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
            try:
                dom = input("Введите домен (например, chatgpt.com или 0 для отмены): ").strip()
            except KeyboardInterrupt:
                continue
            if not dom or dom == "0":
                continue
            dom = normalize_domain(dom)
            run_test_stream([dom], cfg, title=f"Проверка {dom}")
        elif choice == "3":
            active = get_active_domains(cfg)
            run_test_stream(active, cfg, title="Полный тест всех сайтов базы")
        elif choice == "0":
            break

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

    pause_prompt()

def menu_diagnostics(cfg: AppConfig) -> None:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"              451bypass -- System Diagnostics                  ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    run_diagnostics(cfg)
    pause_prompt()

def menu_setup(cfg: AppConfig) -> bool:
    clear_screen()
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
    print(f"       451bypass v{__version__} -- Подключение Cloudflare Gateway      ")
    print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
    token_url = "https://dash.cloudflare.com/profile/api-tokens"
    print(info(f"Открываем страницу токенов Cloudflare: {token_url}"))
    try:
        if sys.platform == "win32":
            os.startfile(token_url)
        else:
            webbrowser.open(token_url)
    except Exception:
        pass

    print("\nИнструкция:")
    print("  1. В открывшемся браузере нажмите кнопку 'Create Token'")
    print("  2. В первой строке выберите шаблон 'Edit Cloudflare Workers' -> 'Use template'")
    print("  3. Прокрутите страницу вниз и нажмите 'Continue to summary' -> 'Create Token'")
    print("  4. Скопируйте полученный токен и вставьте сюда:\n")

    while True:
        token_input = input("Cloudflare API Token: ").strip()
        if not token_input:
            continue
        valid, msg = verify_token(token_input)
        if not valid:
            print(error(f"Токен не подошел: {msg}. Попробуйте еще раз."))
            continue
        print(success("Токен проверен успешно!"))
        accs = list_accounts(token_input)
        if not accs:
            print(error("Не удалось найти аккаунт Cloudflare для этого токена."))
            return False
        cfg.account_id = accs[0]["id"]
        cfg.api_token = token_input
        print(success(f"Аккаунт определен автоматически: {accs[0].get('name', '')} ({cfg.account_id})"))
        sub = get_subdomain(cfg.account_id, cfg.api_token)
        if sub:
            cfg.subdomain = sub
            print(success(f"Workers Subdomain: {sub}.workers.dev"))
        else:
            custom_sub = input("Введите имя поддомена Workers: ").strip()
            if custom_sub:
                cfg.subdomain = custom_sub
        save_config(cfg)
        ok, smsg = sync_to_cloudflare(cfg, force=True)
        if ok:
            print(success(f"Шлюз успешно запущен: https://{cfg.worker_name}.{cfg.subdomain}.workers.dev"))
        return True

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

        pac_on = is_system_pac_enabled()
        d_state, _ = get_daemon_status()
        is_active = pac_on and d_state == "ACTIVE"

        status_text = "ВКЛЮЧЕН (Работает)" if is_active else "ВЫКЛЮЧЕН"
        status_color = Colors.GREEN if is_active else Colors.YELLOW

        print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
        print(f"      451bypass v{__version__} -- Умный обход блокировок (HTTP 451 / 403)     ")
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}")
        print(f"  Обход Windows:          {colorize(f'[{status_text}]', status_color)}")
        print(f"  Активных сайтов в базе: {colorize(str(total_cnt), Colors.GREEN)} ({core_cnt} базовых, {user_cnt} своих)")
        print(f"  Шлюз Cloudflare:        {colorize(f'https://{cfg.worker_name}.{cfg.subdomain}.workers.dev' if cfg.subdomain else 'Не настроен', Colors.CYAN)}")
        if last_notice:
            print(f"  {colorize('[Уведомление]', Colors.YELLOW)} {last_notice}")
            last_notice = None
        print(f"{Colors.BOLD}---------------------------------------------------------------{Colors.RESET}")
        toggle_label = "Выключить системный обход" if is_active else "Включить системный обход"
        print(f"  [1] {toggle_label} (ON / OFF)")
        print("  [2] Проверить статус службы     - Verify Gateway, Worker, and Task health")
        print("  [3] Тест доступности сайтов     - Probe active endpoints for 451/403 bypass")
        print("  [4] Редактировать свои сайты    - Edit personal custom.txt in Notepad")
        print("  [5] Диагностика системы         - Full 8-point system diagnostics")
        print("  [6] Настроить токен Cloudflare  - Connect Cloudflare API Token")
        print("  [0] Выход")
        print(f"{Colors.BOLD}==============================================================={Colors.RESET}\n")
        
        try:
            choice = input("Выберите пункт [0-6]: ").strip()
        except KeyboardInterrupt:
            clear_screen()
            print("451bypass закрыт.")
            sys.exit(0)

        if choice == "1":
            toggle_bypass(cfg)
        elif choice == "2":
            menu_check_service(cfg)
        elif choice == "3":
            menu_test_domains(cfg)
        elif choice == "4":
            run_interactive_import(cfg)
        elif choice == "5":
            menu_diagnostics(cfg)
        elif choice == "6":
            menu_setup(cfg)
            pause_prompt()
        elif choice == "0":
            clear_screen()
            print("451bypass закрыт.")
            sys.exit(0)
