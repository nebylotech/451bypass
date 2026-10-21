import os
import sys
import subprocess
from pathlib import Path
from typing import List
from .config import AppConfig, USER_DOMAINS_PATH
from .utils import normalize_domain, is_valid_domain, print_table, Colors, colorize, success, info, warn, error
from .lists import load_user_domains, save_user_domains
from .sync import sync_to_cloudflare

TEMPLATE_HEADER = """api.my-custom-service.com
"""

def parse_domains_from_text(text: str) -> List[str]:
    seen = set()
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        domain = normalize_domain(line)
        if domain and is_valid_domain(domain) and domain not in seen:
            seen.add(domain)
            results.append(domain)
    return results

def run_interactive_import(cfg: AppConfig) -> None:
    USER_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USER_DOMAINS_PATH.exists():
        USER_DOMAINS_PATH.write_text(TEMPLATE_HEADER, encoding="utf-8")

    print(info(f"Opening user domains file in editor: {USER_DOMAINS_PATH}"))
    print(colorize("Edit your domains, save and close Notepad, then press ENTER...", Colors.YELLOW))

    editor = os.environ.get("EDITOR", "notepad.exe")
    try:
        if sys.platform == "win32" and editor == "notepad.exe":
            proc = subprocess.Popen([editor, str(USER_DOMAINS_PATH)])
            proc.wait()
        else:
            os.system(f"{editor} \"{USER_DOMAINS_PATH}\"")
    except Exception as e:
        print(warn(f"Could not automatically open editor: {e}"))
        
    input("\nPress ENTER after saving and closing the file to proceed...")

    if not USER_DOMAINS_PATH.exists():
        print(error("User domains file was not found."))
        return

    content = USER_DOMAINS_PATH.read_text(encoding="utf-8")
    valid_domains = parse_domains_from_text(content)
    save_user_domains(valid_domains)

    print(success(f"Saved {len(valid_domains)} custom user domains in {USER_DOMAINS_PATH.name}."))
    print(info("Synchronizing changes with Cloudflare..."))
    sync_ok, sync_msg = sync_to_cloudflare(cfg)
    if sync_ok:
        print(success(sync_msg))
    else:
        print(warn(f"Sync warning: {sync_msg}"))
