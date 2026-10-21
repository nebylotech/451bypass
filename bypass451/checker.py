import time
import urllib.request
import urllib.error
import ssl
import socket
from dataclasses import dataclass
from typing import Optional, Tuple
from .config import AppConfig
from .utils import Colors, colorize

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
    "chatgpt.com": "/robots.txt",
    "api.anthropic.com": "/v1/models",
    "api.x.ai": "/v1/models",
    "api.groq.com": "/openai/v1/models",
    "api.perplexity.ai": "/robots.txt",
    "openrouter.ai": "/api/v1/models",
    "api.deepseek.com": "/models",
    "api.mistral.ai": "/v1/models"
}

def classify_status(status: Optional[int], body_snippet: str = "", error_str: str = "") -> Tuple[str, str, str]:
    if status == 200:
        label = colorize("[OK] 200", Colors.GREEN)
        return label, "SUCCESS_200", "200 OK — Endpoint reachable and returned data."
    elif status == 401:
        label = colorize("[OK] 401", Colors.GREEN)
        return label, "BYPASS_OK_401", "Bypass active — Service reached and awaiting API Key."
    elif status == 451:
        label = colorize("[FAIL 451]", Colors.RED)
        return label, "RESTRICTED_451", "HTTP 451 Unavailable For Legal Reasons — Geo-restricted."
    elif status == 403:
        if "country" in body_snippet.lower() or "region" in body_snippet.lower() or "territory" in body_snippet.lower():
            label = colorize("[FAIL 403]", Colors.RED)
            return label, "RESTRICTED_403", "HTTP 403 Forbidden — Regional block in response."
        label = colorize("[WARN 403]", Colors.YELLOW)
        return label, "FORBIDDEN_403", "HTTP 403 Forbidden — Web bot check or access denied."
    elif status == 404:
        label = colorize("[WARN 404]", Colors.YELLOW)
        return label, "NOT_FOUND_404", "HTTP 404 Not Found — Endpoint path does not exist."
    elif status == 429:
        label = colorize("[WARN 429]", Colors.YELLOW)
        return label, "RATE_LIMITED_429", "HTTP 429 Too Many Requests — Rate limit reached."
    elif status and 500 <= status < 600:
        label = colorize(f"[FAIL {status}]", Colors.RED)
        return label, f"SERVER_ERROR_{status}", f"HTTP {status} — Upstream server error."
    elif "timed out" in error_str.lower() or "timeout" in error_str.lower():
        label = colorize("[TIMEOUT]", Colors.RED)
        return label, "TIMEOUT", "Connection timed out."
    elif "certificate" in error_str.lower() or "ssl" in error_str.lower():
        label = colorize("[TLS FAIL]", Colors.RED)
        return label, "TLS_ERROR", f"TLS Handshake failed: {error_str}"
    elif "getaddrinfo" in error_str.lower() or "name resolution" in error_str.lower():
        label = colorize("[DNS FAIL]", Colors.RED)
        return label, "DNS_ERROR", "DNS resolution failed."
    else:
        label = colorize("[FAIL]", Colors.RED)
        return label, "CONNECTION_ERROR", f"Network error: {error_str}"

def perform_check(
    domain: str,
    cfg: Optional[AppConfig] = None,
    use_gateway: bool = False,
    api_key: Optional[str] = None,
    timeout_sec: float = 6.0
) -> CheckResult:
    path = TEST_PATHS.get(domain, "/")
    
    if use_gateway and cfg and cfg.subdomain and cfg.worker_name:
        url = f"https://{cfg.worker_name}.{cfg.subdomain}.workers.dev/{domain}{path}"
    else:
        url = f"https://{domain}{path}"
        
    headers = {
        "User-Agent": "451bypass/1.0",
        "Accept": "*/*"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start_time = time.perf_counter()
    status_code: Optional[int] = None
    status_text = ""
    body_snippet = ""
    error_str = ""

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
        is_gateway=use_gateway,
        classification=classification,
        details=details
    )
