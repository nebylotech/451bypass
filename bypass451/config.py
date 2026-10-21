import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

SCHEMA_VERSION = 2

PRIMARY_CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "451bypass"
PRIMARY_CONFIG_PATH = PRIMARY_CONFIG_DIR / "config.json"
BACKUP_CONFIG_PATH = PRIMARY_CONFIG_DIR / "config.json.bak"

DOMAINS_DIR = PRIMARY_CONFIG_DIR / "domains"
CUSTOM_DOMAINS_PATH = DOMAINS_DIR / "custom.txt"
CORE_DOMAINS_PATH = DOMAINS_DIR / "core.txt"
USER_DOMAINS_PATH = CUSTOM_DOMAINS_PATH

LEGACY_USER_DOMAINS_PATH = PRIMARY_CONFIG_DIR / "user_domains.txt"
LEGACY_CORE_DOMAINS_PATH = PRIMARY_CONFIG_DIR / "core_domains.json"

LEGACY_51_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "51-bypass"
DOT_CONFIG_DIR = Path.home() / ".451bypass"
DOT_CONFIG_PATH = DOT_CONFIG_DIR / "config.json"
LEGACY_DOT_CONFIG_DIR = Path.home() / ".51-bypass"
LEGACY_DOT_CONFIG_PATH = LEGACY_DOT_CONFIG_DIR / "config.json"
LEGACY_CONFIG_DIR = Path.home() / ".cloudflare-dns"
LEGACY_CONFIG_PATH = LEGACY_CONFIG_DIR / "config.json"

DEFAULT_REMOTE_DOMAINS_URL = "https://raw.githubusercontent.com/nebylotech/451bypass/main/domains/core.txt"

@dataclass
class AppConfig:
    schema_version: int = SCHEMA_VERSION
    account_id: str = ""
    api_token: str = ""
    worker_name: str = "ai-gateway"
    subdomain: str = ""
    default_domain: str = ""
    remote_domains_url: str = DEFAULT_REMOTE_DOMAINS_URL
    last_sync_time: Optional[str] = None
    last_sync_status: str = "PENDING"
    last_sync_error: Optional[str] = None
    last_sync_domain_count: int = 0
    last_custom_hash: Optional[str] = None

def get_config_dir() -> Path:
    PRIMARY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DOMAINS_DIR.mkdir(parents=True, exist_ok=True)
    return PRIMARY_CONFIG_DIR

def migrate_external_config() -> Optional[AppConfig]:
    source_path = None
    if (LEGACY_51_DIR / "config.json").exists():
        source_path = LEGACY_51_DIR / "config.json"
    elif DOT_CONFIG_PATH.exists():
        source_path = DOT_CONFIG_PATH
    elif LEGACY_DOT_CONFIG_PATH.exists():
        source_path = LEGACY_DOT_CONFIG_PATH
    elif LEGACY_CONFIG_PATH.exists():
        source_path = LEGACY_CONFIG_PATH

    if not source_path or not source_path.exists():
        return None

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cfg = AppConfig()
        cfg.account_id = data.get("account_id", data.get("AccountId", ""))
        cfg.api_token = data.get("api_token", data.get("ApiToken", ""))
        cfg.worker_name = data.get("worker_name", data.get("WorkerName", "ai-gateway"))
        cfg.subdomain = data.get("subdomain", data.get("Subdomain", ""))
        cfg.default_domain = data.get("default_domain", data.get("DefaultDomain", ""))

        if (LEGACY_51_DIR / "domains" / "custom.txt").exists() and not CUSTOM_DOMAINS_PATH.exists():
            CUSTOM_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_51_DIR / "domains" / "custom.txt", CUSTOM_DOMAINS_PATH)
        elif (LEGACY_51_DIR / "user_domains.txt").exists() and not CUSTOM_DOMAINS_PATH.exists():
            CUSTOM_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_51_DIR / "user_domains.txt", CUSTOM_DOMAINS_PATH)

        if (LEGACY_51_DIR / "domains" / "core.txt").exists() and not CORE_DOMAINS_PATH.exists():
            CORE_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_51_DIR / "domains" / "core.txt", CORE_DOMAINS_PATH)

        legacy_domains = data.get("domains", data.get("Domains", []))
        if legacy_domains and not CUSTOM_DOMAINS_PATH.exists():
            user_lines = [d.lower().strip() for d in legacy_domains if d.strip()]
            CUSTOM_DOMAINS_PATH.parent.mkdir(parents=True, exist_ok=True)
            CUSTOM_DOMAINS_PATH.write_text("\n".join(dict.fromkeys(user_lines)) + "\n", encoding="utf-8")

        dot_user = DOT_CONFIG_DIR / "user_domains.txt"
        if dot_user.exists() and not CUSTOM_DOMAINS_PATH.exists():
            shutil.copy2(dot_user, CUSTOM_DOMAINS_PATH)

        return cfg
    except Exception:
        return None

def load_config() -> AppConfig:
    get_config_dir()

    if LEGACY_51_DIR.exists() and not PRIMARY_CONFIG_PATH.exists():
        migrated = migrate_external_config()
        if migrated:
            save_config(migrated)
            return migrated

    if LEGACY_USER_DOMAINS_PATH.exists() and not CUSTOM_DOMAINS_PATH.exists():
        try:
            shutil.copy2(LEGACY_USER_DOMAINS_PATH, CUSTOM_DOMAINS_PATH)
        except Exception:
            pass

    if PRIMARY_CONFIG_PATH.exists():
        try:
            with open(PRIMARY_CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)

            cfg = AppConfig(
                schema_version=raw.get("schema_version", 1),
                account_id=raw.get("account_id", ""),
                api_token=raw.get("api_token", ""),
                worker_name=raw.get("worker_name", "ai-gateway"),
                subdomain=raw.get("subdomain", ""),
                default_domain=raw.get("default_domain", ""),
                remote_domains_url=raw.get("remote_domains_url", DEFAULT_REMOTE_DOMAINS_URL),
                last_sync_time=raw.get("last_sync_time"),
                last_sync_status=raw.get("last_sync_status", "PENDING"),
                last_sync_error=raw.get("last_sync_error"),
                last_sync_domain_count=raw.get("last_sync_domain_count", 0),
                last_custom_hash=raw.get("last_custom_hash"),
            )

            if not cfg.account_id or not cfg.api_token:
                migrated = migrate_external_config()
                if migrated and migrated.account_id and migrated.api_token:
                    cfg.account_id = migrated.account_id
                    cfg.api_token = migrated.api_token
                    cfg.subdomain = migrated.subdomain or cfg.subdomain
                    save_config(cfg)

            return cfg
        except Exception:
            if BACKUP_CONFIG_PATH.exists():
                try:
                    shutil.copy2(BACKUP_CONFIG_PATH, PRIMARY_CONFIG_PATH)
                    return load_config()
                except Exception:
                    pass

    migrated = migrate_external_config()
    if migrated:
        save_config(migrated)
        return migrated

    default_cfg = AppConfig()
    save_config(default_cfg)
    return default_cfg

def save_config(cfg: AppConfig) -> None:
    get_config_dir()

    if PRIMARY_CONFIG_PATH.exists():
        try:
            shutil.copy2(PRIMARY_CONFIG_PATH, BACKUP_CONFIG_PATH)
        except Exception:
            pass

    data = asdict(cfg)

    temp_fd, temp_path = tempfile.mkstemp(dir=PRIMARY_CONFIG_DIR, prefix="cfg_", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, PRIMARY_CONFIG_PATH)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
