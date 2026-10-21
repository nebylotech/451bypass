import json
import uuid
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple, Any

API_BASE = "https://api.cloudflare.com/client/v4"

class CloudflareAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, errors: Optional[List[dict]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []

def _api_request(
    method: str,
    path: str,
    token: str,
    data: Optional[bytes] = None,
    content_type: str = "application/json",
    timeout: float = 15.0
) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "451bypass/1.0",
        "Accept": "application/json"
    }
    if data is not None:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw_error = e.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw_error)
            errors = parsed.get("errors", [])
            msg = "; ".join(err.get("message", "Unknown error") for err in errors) or f"HTTP {e.code}"
        except Exception:
            errors = []
            msg = f"HTTP {e.code}: {e.reason}"
        raise CloudflareAPIError(msg, status_code=e.code, errors=errors)
    except urllib.error.URLError as e:
        raise CloudflareAPIError(f"Network error: {e.reason}")

def verify_token(token: str) -> Tuple[bool, str]:
    try:
        resp = _api_request("GET", "/user/tokens/verify", token)
        if resp.get("success"):
            status = resp.get("result", {}).get("status", "active")
            return (status == "active"), status
        return False, "Token verification failed"
    except CloudflareAPIError as e:
        return False, str(e)

def list_accounts(token: str) -> List[Dict[str, str]]:
    accounts = []
    try:
        resp = _api_request("GET", "/accounts?page=1&per_page=20", token)
        for item in resp.get("result", []):
            if item.get("id"):
                accounts.append({
                    "id": item.get("id", ""),
                    "name": item.get("name", "")
                })
    except CloudflareAPIError:
        pass

    if not accounts:
        try:
            resp = _api_request("GET", "/memberships?page=1&per_page=20", token)
            for item in resp.get("result", []):
                acc = item.get("account", {})
                if acc.get("id"):
                    accounts.append({
                        "id": acc.get("id", ""),
                        "name": acc.get("name", "")
                    })
        except CloudflareAPIError:
            pass

    return accounts

def get_subdomain(account_id: str, token: str) -> Optional[str]:
    try:
        resp = _api_request("GET", f"/accounts/{account_id}/workers/subdomain", token)
        return resp.get("result", {}).get("subdomain")
    except CloudflareAPIError:
        return None

def check_worker_exists(account_id: str, worker_name: str, token: str) -> bool:
    try:
        resp = _api_request("GET", f"/accounts/{account_id}/workers/scripts/{worker_name}", token)
        return bool(resp.get("success"))
    except CloudflareAPIError as e:
        if e.status_code == 404:
            return False
        raise

def enable_subdomain_route(account_id: str, worker_name: str, token: str) -> bool:
    body = json.dumps({"enabled": True}).encode("utf-8")
    try:
        resp = _api_request(
            "POST",
            f"/accounts/{account_id}/workers/scripts/{worker_name}/subdomain",
            token,
            data=body,
            content_type="application/json"
        )
        return bool(resp.get("success"))
    except CloudflareAPIError as e:
        if "already" in str(e).lower():
            return True
        raise

def deploy_worker_script(
    account_id: str,
    worker_name: str,
    token: str,
    script_content: str
) -> bool:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": "2024-01-01"
    }
    metadata_json = json.dumps(metadata)

    parts = []
    
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(b'Content-Disposition: form-data; name="metadata"\r\n')
    parts.append(b'Content-Type: application/json\r\n\r\n')
    parts.append(metadata_json.encode("utf-8"))
    parts.append(b"\r\n")

    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n')
    parts.append(b'Content-Type: application/javascript+module\r\n\r\n')
    parts.append(script_content.encode("utf-8"))
    parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    payload = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"

    resp = _api_request(
        "PUT",
        f"/accounts/{account_id}/workers/scripts/{worker_name}",
        token,
        data=payload,
        content_type=content_type,
        timeout=25.0
    )
    
    if resp.get("success"):
        enable_subdomain_route(account_id, worker_name, token)
        return True
    return False

def delete_worker_script(account_id: str, worker_name: str, token: str) -> bool:
    try:
        resp = _api_request("DELETE", f"/accounts/{account_id}/workers/scripts/{worker_name}", token)
        return bool(resp.get("success"))
    except Exception:
        return False

def check_worker_live_health(worker_name: str, subdomain: str, secret: str = "", timeout: float = 8.0) -> Tuple[bool, str]:
    secret_param = f"?secret={secret}" if secret else ""
    url = f"https://{worker_name}.{subdomain}.workers.dev/health{secret_param}"
    headers = {"User-Agent": "451bypass/1.0"}
    if secret:
        headers["X-451bypass-Secret"] = secret
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                if data.get("status") == "ok":
                    return True, "Worker healthy (200 OK)"
            return False, f"Worker returned unexpected status {resp.status}"
    except Exception as e:
        return False, str(e)
