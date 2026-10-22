import time
import urllib.request
import urllib.error
import http.client
import ssl
import socket
from dataclasses import dataclass
from typing import Optional, Tuple
from .config import AppConfig
from .utils import Colors, colorize
from .proxy import is_proxy_running, DEFAULT_PROXY_PORT

@dataclass
class CheckResult:
    target: str
    url: str
    status_code: Optional[int]
    status_text: str
    status_label: str
    latency_ms: float
    is_gateway: bool
    classification: str
    details: str

TEST_PATHS = {
    "integrate.api.nvidia.com": "/v1/models",
    "api.ngc.nvidia.com": "/v2/org",
    "build.nvidia.com": "/v1/models",
    "api.openai.com": "/v1/models",
    "chatgpt.com": "/",
    "claude.ai": "/",
    "gemini.google.com": "/",
    "grok.com": "/",
    "api.anthropic.com": "/v1/models",
    "api.x.ai": "/v1/models",
    "api.groq.com": "/openai/v1/models",
    "api.perplexity.ai": "/robots.txt",
    "openrouter.ai": "/api/v1/models",
    "api.deepseek.com": "/models",
    "api.mistral.ai": "/v1/models",
    "api.cohere.ai": "/v1",
    "api.elevenlabs.io": "/v1/voices",
    "generativelanguage.googleapis.com": "/$discovery/rest"
}

TEST_HOST_OVERRIDE = {
    "oaiusercontent.com": "files.oaiusercontent.com",
    "patreonusercontent.com": "c5.patreonusercontent.com",
    "servarr.com": "wiki.servarr.com",
    "notion-static.com": "www.notion.so"
}

def classify_status(status: Optional[int], body_snippet: str = "", error_str: str = "") -> Tuple[str, str, str]:
    if status == 200:
        label = colorize("[OK] 200", Colors.GREEN)
        return label, "SUCCESS_200", "200 OK — Доступен, данные получены."
    elif status in (301, 302, 307, 308):
        label = colorize(f"[OK] {status}", Colors.GREEN)
        return label, f"REDIRECT_{status}", f"HTTP {status} — Редирект, сервис доступен."
    elif status == 401:
        label = colorize("[OK] 401", Colors.GREEN)
        return label, "BYPASS_OK_401", "HTTP 401 — Обход активен, API ждет ключ авторизации."
    elif status == 400:
        label = colorize("[OK] 400", Colors.GREEN)
        return label, "BAD_REQUEST_400", "HTTP 400 — Сервер ответил, эндпоинт доступен."
    elif status == 451:
        label = colorize("[FAIL 451]", Colors.RED)
        return label, "RESTRICTED_451", "HTTP 451 Unavailable For Legal Reasons — Региональная блокировка."
    elif status == 403:
        b_low = body_snippet.lower()
        if "country" in b_low or "region" in b_low or "territory" in b_low:
            label = colorize("[FAIL 403]", Colors.RED)
            return label, "RESTRICTED_403", "HTTP 403 Forbidden — Региональный блок в ответе."
        label = colorize("[OK] 403", Colors.GREEN)
        return label, "CHALLENGE_OK_403", "HTTP 403 — Защита от ботов / WAF (в браузере открывается штатно)."
    elif status == 404:
        label = colorize("[OK] 404", Colors.GREEN)
        return label, "NOT_FOUND_404", "HTTP 404 Not Found — Эндпоинт ответил, сервис доступен."
    elif status == 429:
        label = colorize("[OK] 429", Colors.GREEN)
        return label, "RATE_LIMITED_429", "HTTP 429 Too Many Requests — Лимит запросов, сервис доступен."
    elif status == 530:
        label = colorize("[OK] 530", Colors.GREEN)
        return label, "CF_OK_530", "HTTP 530 — Cloudflare Edge ответил (wildcard parent)."
    elif status and 500 <= status < 600:
        label = colorize(f"[FAIL {status}]", Colors.RED)
        return label, f"SERVER_ERROR_{status}", f"HTTP {status} — Ошибка сервера."
    elif "timed out" in error_str.lower() or "timeout" in error_str.lower():
        label = colorize("[TIMEOUT]", Colors.RED)
        return label, "TIMEOUT", "Таймаут соединения."
    elif "certificate" in error_str.lower() or "ssl" in error_str.lower():
        label = colorize("[TLS FAIL]", Colors.RED)
        return label, "TLS_ERROR", f"Сбой TLS Handshake: {error_str}"
    elif "getaddrinfo" in error_str.lower() or "name resolution" in error_str.lower():
        label = colorize("[DNS FAIL]", Colors.RED)
        return label, "DNS_ERROR", "Сбой DNS resolution."
    else:
        label = colorize("[FAIL]", Colors.RED)
        return label, "CONNECTION_ERROR", f"Сетевая ошибка: {error_str}"

def perform_check(
    domain: str,
    cfg: Optional[AppConfig] = None,
    use_gateway: bool = False,
    api_key: Optional[str] = None,
    timeout_sec: float = 5.5,
    proxy_port: int = DEFAULT_PROXY_PORT
) -> CheckResult:
    target_host = TEST_HOST_OVERRIDE.get(domain, domain)
    path = TEST_PATHS.get(domain, TEST_PATHS.get(target_host, "/"))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 451bypass/1.0",
        "Accept": "*/*",
        "Host": target_host
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start_time = time.perf_counter()
    status_code: Optional[int] = None
    status_text = ""
    body_snippet = ""
    error_str = ""
    tested_via_proxy = False

    proxy_up = is_proxy_running(proxy_port)

    if proxy_up and not use_gateway:
        tested_via_proxy = True
        url = f"https://{target_host}{path}"
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                ctx.set_alpn_protocols(["http/1.1"])
            except Exception:
                pass
            conn = http.client.HTTPSConnection("127.0.0.1", proxy_port, context=ctx, timeout=timeout_sec)
            conn.set_tunnel(target_host, 443)
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            latency = (time.perf_counter() - start_time) * 1000.0
            status_code = resp.status
            status_text = resp.reason or "OK"
            raw_body = resp.read(512)
            body_snippet = raw_body.decode("utf-8", errors="ignore")
            cf_ray = resp.getheader("CF-RAY") or ""
            cf_bm = resp.getheader("set-cookie") or ""
            if cf_ray or "cf_bm" in cf_bm:
                body_snippet += f" [cloudflare:{cf_ray}]"
            conn.close()
        except socket.timeout:
            latency = (time.perf_counter() - start_time) * 1000.0
            error_str = "Socket timed out"
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            error_str = str(e)
    else:
        if use_gateway and cfg and cfg.subdomain and cfg.worker_name:
            sep = "&" if "?" in path else "?"
            secret_p = f"{sep}secret={cfg.gateway_secret}" if cfg.gateway_secret else ""
            url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev/{domain}{path}{secret_p}"
            if cfg.gateway_secret:
                headers["X-451bypass-Secret"] = cfg.gateway_secret
        else:
            url = f"https://{domain}{path}"

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
                latency = (time.perf_counter() - start_time) * 1000.0
                status_code = resp.status
                status_text = resp.reason or "OK"
                raw_body = resp.read(512)
                body_snippet = raw_body.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            status_code = e.code
            status_text = e.reason or ""
            try:
                body_snippet = e.read(512).decode("utf-8", errors="ignore")
            except Exception:
                pass
        except urllib.error.URLError as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            error_str = str(e.reason)
        except socket.timeout:
            latency = (time.perf_counter() - start_time) * 1000.0
            error_str = "Socket timed out"
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            error_str = str(e)

    label, classification, details = classify_status(status_code, body_snippet, error_str)

    return CheckResult(
        target=domain,
        url=url,
        status_code=status_code,
        status_text=status_text,
        status_label=label,
        latency_ms=round(latency, 1),
        is_gateway=use_gateway or tested_via_proxy,
        classification=classification,
        details=details
    )
