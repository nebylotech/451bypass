import json
import hashlib
import shutil
import urllib.request
from typing import List, Set, Tuple, Optional
from pathlib import Path
from .config import (
    AppConfig,
    save_config,
    CORE_DOMAINS_PATH,
    CUSTOM_DOMAINS_PATH,
    PRIMARY_CONFIG_DIR
)
from .utils import normalize_domain, is_valid_domain

def find_repo_domains_dir() -> Optional[Path]:
    candidates = [
        Path.cwd() / "domains",
        Path(__file__).resolve().parent.parent / "domains"
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None

def compute_file_hash(p: Path) -> str:
    if not p.exists():
        return ""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return ""

def get_custom_domains_file() -> Path:
    CUSTOM_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CUSTOM_DOMAINS_PATH.exists():
        repo_dir = find_repo_domains_dir()
        if repo_dir and (repo_dir / "custom.txt").exists():
            try:
                shutil.copy2(repo_dir / "custom.txt", CUSTOM_DOMAINS_PATH)
            except Exception:
                pass
        else:
            CUSTOM_DOMAINS_PATH.write_text("", encoding="utf-8")
    
    repo_dir = find_repo_domains_dir()
    if repo_dir:
        repo_custom = repo_dir / "custom.txt"
        if repo_custom.exists() and repo_custom.resolve() != CUSTOM_DOMAINS_PATH.resolve():
            try:
                if repo_custom.stat().st_mtime > CUSTOM_DOMAINS_PATH.stat().st_mtime:
                    shutil.copy2(repo_custom, CUSTOM_DOMAINS_PATH)
            except Exception:
                pass

    return CUSTOM_DOMAINS_PATH

def get_core_domains_file() -> Path:
    CORE_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CORE_DOMAINS_PATH.exists():
        repo_dir = find_repo_domains_dir()
        if repo_dir and (repo_dir / "core.txt").exists():
            try:
                shutil.copy2(repo_dir / "core.txt", CORE_DOMAINS_PATH)
            except Exception:
                pass
        else:
            CORE_DOMAINS_PATH.write_text("", encoding="utf-8")
    return CORE_DOMAINS_PATH

def load_core_domains() -> List[str]:
    p = get_core_domains_file()
    if p.exists():
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            res = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                d = normalize_domain(line)
                if d and is_valid_domain(d) and d not in res:
                    res.append(d)
            if res:
                return sorted(res)
        except Exception:
            pass
    return []

def save_core_domains(domains: List[str]) -> None:
    valid = sorted(list(dict.fromkeys(normalize_domain(d) for d in domains if is_valid_domain(normalize_domain(d)))))
    p = get_core_domains_file()
    p.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
    repo_dir = find_repo_domains_dir()
    if repo_dir:
        repo_core = repo_dir / "core.txt"
        if repo_core.exists() and repo_core.resolve() != p.resolve():
            try:
                repo_core.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
            except Exception:
                pass

def load_custom_domains() -> List[str]:
    p = get_custom_domains_file()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        res = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            d = normalize_domain(line)
            if d and is_valid_domain(d) and d not in res:
                res.append(d)
        return res
    except Exception:
        return []

def load_user_domains() -> List[str]:
    return load_custom_domains()

def save_custom_domains(domains: List[str]) -> None:
    valid = sorted(list(dict.fromkeys(normalize_domain(d) for d in domains if is_valid_domain(normalize_domain(d)))))
    p = get_custom_domains_file()
    p.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
    repo_dir = find_repo_domains_dir()
    if repo_dir:
        repo_custom = repo_dir / "custom.txt"
        if repo_custom.exists() and repo_custom.resolve() != p.resolve():
            try:
                repo_custom.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
            except Exception:
                pass

def save_user_domains(domains: List[str]) -> None:
    save_custom_domains(domains)

def fetch_worker_core_domains(cfg: AppConfig, timeout_sec: float = 4.0) -> List[str]:
    if cfg.worker_name and cfg.subdomain:
        core_url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev/core-domains"
        try:
            req = urllib.request.Request(core_url, headers={"User-Agent": "451bypass/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    parsed = []
                    for line in raw.splitlines():
                        d = normalize_domain(line.strip())
                        if d and is_valid_domain(d) and d not in parsed:
                            parsed.append(d)
                    if parsed:
                        return sorted(parsed)
        except Exception:
            pass

        health_url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev/health"
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "451bypass/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    domains = data.get("core_domains") or data.get("managed_domains")
                    if isinstance(domains, list) and domains:
                        parsed = [normalize_domain(d) for d in domains if is_valid_domain(normalize_domain(d))]
                        if parsed:
                            return sorted(parsed)
        except Exception:
            pass

    return load_core_domains()

def check_custom_file_changed(cfg: AppConfig) -> bool:
    p = get_custom_domains_file()
    curr_hash = compute_file_hash(p)
    return curr_hash != (cfg.last_custom_hash or "")

def reconcile_custom_domains(cfg: AppConfig, force_sync: bool = False) -> Tuple[List[str], List[str], bool, str]:
    from .sync import sync_to_cloudflare

    custom_file = get_custom_domains_file()
    try:
        raw_text = custom_file.read_text(encoding="utf-8")
    except Exception:
        raw_text = ""

    worker_core = fetch_worker_core_domains(cfg)
    core_set = {d.lower() for d in worker_core if is_valid_domain(d)}

    lines = raw_text.splitlines()
    duplicates = []
    cleaned_lines = []
    remaining_custom = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            cleaned_lines.append(line)
            continue
        domain = normalize_domain(stripped)
        if not is_valid_domain(domain):
            continue
        if domain in core_set:
            if domain not in duplicates:
                duplicates.append(domain)
        else:
            if domain not in remaining_custom:
                remaining_custom.append(domain)
                cleaned_lines.append(domain)

    if duplicates:
        new_content = "\n".join(cleaned_lines)
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        custom_file.write_text(new_content, encoding="utf-8")
        repo_dir = find_repo_domains_dir()
        if repo_dir:
            repo_custom = repo_dir / "custom.txt"
            if repo_custom.exists() and repo_custom.resolve() != custom_file.resolve():
                try:
                    repo_custom.write_text(new_content, encoding="utf-8")
                except Exception:
                    pass

    current_hash = compute_file_hash(custom_file)
    needs_sync = force_sync or (current_hash != (cfg.last_custom_hash or ""))

    synced = False
    sync_msg = "Up to date"

    if needs_sync and cfg.account_id and cfg.api_token:
        synced, sync_msg = sync_to_cloudflare(cfg, force=True)
        if synced:
            cfg.last_custom_hash = current_hash
            save_config(cfg)
    elif not needs_sync:
        sync_msg = "Custom domains already synchronized"

    return duplicates, remaining_custom, synced, sync_msg

def add_user_domain(raw_domain: str, cfg: Optional[AppConfig] = None) -> Tuple[bool, str]:
    domain = normalize_domain(raw_domain)
    if not is_valid_domain(domain):
        return False, f"Invalid domain format: '{raw_domain}'"
    
    if cfg:
        worker_core = fetch_worker_core_domains(cfg)
    else:
        worker_core = load_core_domains()

    if domain in worker_core:
        return False, f"Domain '{domain}' is already included in core gateway rules"

    existing = load_custom_domains()
    if domain in existing:
        return False, f"Domain '{domain}' already exists in your custom domains"
    
    existing.append(domain)
    save_custom_domains(existing)

    if cfg:
        reconcile_custom_domains(cfg, force_sync=True)

    return True, domain

def remove_user_domain(raw_domain: str, cfg: Optional[AppConfig] = None) -> bool:
    domain = normalize_domain(raw_domain)
    existing = load_custom_domains()
    if domain in existing:
        existing.remove(domain)
        save_custom_domains(existing)
        if cfg:
            reconcile_custom_domains(cfg, force_sync=True)
        return True
    return False

def get_active_domains(cfg: AppConfig) -> List[str]:
    domains: Set[str] = set()
    for d in load_core_domains():
        domains.add(d)
    for d in load_custom_domains():
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
        req = urllib.request.Request(url, headers={"User-Agent": "451bypass/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            text = resp.read().decode("utf-8")
        parsed = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
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
