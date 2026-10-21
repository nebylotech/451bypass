import json
import urllib.request
from typing import List, Set, Tuple, Optional
from pathlib import Path
from .config import AppConfig, CORE_DOMAINS_PATH, USER_DOMAINS_PATH, PRIMARY_CONFIG_DIR
from .utils import normalize_domain, is_valid_domain

def find_core_domains_text_file() -> Optional[Path]:
    candidates = [
        PRIMARY_CONFIG_DIR / "domains" / "core.txt",
        Path(__file__).resolve().parent.parent / "domains" / "core.txt",
        PRIMARY_CONFIG_DIR / "core.txt"
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def load_default_domains_from_file() -> List[str]:
    p = find_core_domains_text_file()
    if p and p.exists():
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            res = []
            for line in lines:
                d = normalize_domain(line)
                if d and is_valid_domain(d) and d not in res:
                    res.append(d)
            if res:
                return res
        except Exception:
            pass
    return ["integrate.api.nvidia.com"]

def load_core_domains() -> List[str]:
    if CORE_DOMAINS_PATH.exists():
        try:
            with open(CORE_DOMAINS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return [normalize_domain(d) for d in data if is_valid_domain(normalize_domain(d))]
        except Exception:
            pass
    defaults = load_default_domains_from_file()
    save_core_domains(defaults)
    return defaults

def save_core_domains(domains: List[str]) -> None:
    valid = sorted(list(dict.fromkeys(normalize_domain(d) for d in domains if is_valid_domain(normalize_domain(d)))))
    CORE_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CORE_DOMAINS_PATH, "w", encoding="utf-8") as f:
        json.dump(valid, f, indent=2, ensure_ascii=False)

def load_user_domains() -> List[str]:
    if not USER_DOMAINS_PATH.exists():
        return []
    try:
        lines = USER_DOMAINS_PATH.read_text(encoding="utf-8").splitlines()
        res = []
        for line in lines:
            d = normalize_domain(line)
            if d and is_valid_domain(d) and d not in res:
                res.append(d)
        return res
    except Exception:
        return []

def save_user_domains(domains: List[str]) -> None:
    valid = sorted(list(dict.fromkeys(normalize_domain(d) for d in domains if is_valid_domain(normalize_domain(d)))))
    USER_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USER_DOMAINS_PATH.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")

def add_user_domain(raw_domain: str) -> Tuple[bool, str]:
    domain = normalize_domain(raw_domain)
    if not is_valid_domain(domain):
        return False, f"Invalid domain format: '{raw_domain}'"
    existing = load_user_domains()
    if domain in existing:
        return False, f"Domain '{domain}' already exists in your user domains"
    existing.append(domain)
    save_user_domains(existing)
    return True, domain

def remove_user_domain(raw_domain: str) -> bool:
    domain = normalize_domain(raw_domain)
    existing = load_user_domains()
    if domain in existing:
        existing.remove(domain)
        save_user_domains(existing)
        return True
    return False

def get_active_domains(cfg: AppConfig) -> List[str]:
    domains: Set[str] = set()
    for d in load_core_domains():
        domains.add(d)
    for d in load_user_domains():
        domains.add(d)
    if cfg.default_domain:
        norm_def = normalize_domain(cfg.default_domain)
        if is_valid_domain(norm_def):
            domains.add(norm_def)
    return sorted(list(domains))

def update_core_domains_from_remote(cfg: AppConfig, timeout_sec: float = 8.0) -> Tuple[bool, str, int]:
    url = cfg.remote_domains_url
    if not url:
        return False, "Remote domain repository URL is not configured", 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "51-BYPASS/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            text = resp.read().decode("utf-8")
        parsed = []
        for line in text.splitlines():
            d = normalize_domain(line)
            if d and is_valid_domain(d) and d not in parsed:
                parsed.append(d)
        if not parsed:
            return False, "Remote repository returned 0 valid domains", 0
        old_count = len(load_core_domains())
        save_core_domains(parsed)
        return True, f"Updated core domains: {len(parsed)} loaded (was {old_count})", len(parsed)
    except Exception as e:
        return False, f"Could not reach remote repository ({e}). Local domains preserved.", 0
