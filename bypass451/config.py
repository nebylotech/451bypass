import json
import os
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 2

PRIMARY_CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "451bypass"
PRIMARY_CONFIG_PATH = PRIMARY_CONFIG_DIR / "config.json"
BACKUP_CONFIG_PATH = PRIMARY_CONFIG_DIR / "config.json.bak"

DOMAINS_DIR = PRIMARY_CONFIG_DIR / "domains"
CUSTOM_DOMAINS_PATH = DOMAINS_DIR / "custom.txt"
CORE_DOMAINS_PATH = DOMAINS_DIR / "core.txt"
USER_DOMAINS_PATH = CUSTOM_DOMAINS_PATH

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

def load_config() -> AppConfig:
    get_config_dir()

    if PRIMARY_CONFIG_PATH.exists():
        try:
            with open(PRIMARY_CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)

            return AppConfig(
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
        except Exception:
            if BACKUP_CONFIG_PATH.exists():
                try:
                    shutil.copy2(BACKUP_CONFIG_PATH, PRIMARY_CONFIG_PATH)
                    return load_config()
                except Exception:
                    pass

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
