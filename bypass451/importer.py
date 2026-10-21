import os
import sys
import subprocess
from pathlib import Path
from typing import List
from .config import AppConfig
from .utils import normalize_domain, is_valid_domain, print_table, Colors, colorize, success, info, warn, error
from .lists import get_custom_domains_file, reconcile_custom_domains

TEMPLATE_HEADER = """# Add one custom domain per line (e.g. api.my-service.com)
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
    custom_file = get_custom_domains_file()
    if not custom_file.exists():
        custom_file.write_text(TEMPLATE_HEADER, encoding="utf-8")

    print(info(f"Opening custom domains file in editor: {custom_file}"))
    print(colorize("Edit custom domains, save and close Notepad, then press ENTER...", Colors.YELLOW))

    editor = os.environ.get("EDITOR", "notepad.exe")
    try:
        if sys.platform == "win32" and editor == "notepad.exe":
            proc = subprocess.Popen([editor, str(custom_file)])
            proc.wait()
        else:
            os.system(f"{editor} \"{custom_file}\"")
    except Exception as e:
        print(warn(f"Could not automatically open editor: {e}"))
        
    input("\nPress ENTER after saving and closing the file to proceed...")

    if not custom_file.exists():
        print(error("Custom domains file was not found."))
        return

    print(info("Validating custom domains and checking for overlaps with core rules..."))
    duplicates, remaining, synced, msg = reconcile_custom_domains(cfg, force_sync=True)

    if duplicates:
        print(warn(f"Removed {len(duplicates)} duplicate domains already present in core: {', '.join(duplicates)}"))
    
    print(success(f"Cleaned custom domains: {len(remaining)} active in {custom_file.name}."))
    if synced:
        print(success(f"Synchronized with Cloudflare: {msg}"))
    else:
        print(warn(f"Sync status: {msg}"))
