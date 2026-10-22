import os
import sys
import json
import time
import socket
import asyncio
import winreg
import ctypes
from typing import Optional, Set, Tuple
from pathlib import Path

from .config import load_config, AppConfig, PRIMARY_CONFIG_DIR
from .lists import get_active_domains

DEFAULT_PROXY_PORT = 10451
PID_FILE = PRIMARY_CONFIG_DIR / "daemon.pid"

def get_pac_script(domains: Set[str], port: int = DEFAULT_PROXY_PORT) -> str:
    domain_map = {d.lower(): 1 for d in domains if d}
    domains_json = json.dumps(domain_map)

    return f"""// 451bypass Dynamic PAC Configuration
var PROXIED_DOMAINS = {domains_json};

function FindProxyForURL(url, host) {{
    if (!host) return "DIRECT";
    var lower = host.toLowerCase();

    // Check exact match
    if (PROXIED_DOMAINS[lower]) {{
        return "PROXY 127.0.0.1:{port}";
    }}

    // Check parent domains
    var dot = lower.indexOf('.');
    while (dot !== -1) {{
        lower = lower.substring(dot + 1);
        if (PROXIED_DOMAINS[lower]) {{
            return "PROXY 127.0.0.1:{port}";
        }}
        dot = lower.indexOf('.');
    }}

    return "DIRECT";
}}
"""

def enable_system_pac(port: int = DEFAULT_PROXY_PORT) -> bool:
    if sys.platform != "win32":
        return False
    pac_url = f"http://127.0.0.1:{port}/proxy.pac"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, pac_url)
        winreg.CloseKey(key)

        # Notify WinINet
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0) # INTERNET_OPTION_SETTINGS_CHANGED
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0) # INTERNET_OPTION_REFRESH
        return True
    except Exception:
        return False

def disable_system_pac() -> bool:
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, "AutoConfigURL")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)

        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
        return True
    except Exception:
        return False

def is_system_pac_enabled(port: int = DEFAULT_PROXY_PORT) -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        ) as key:
            val, _ = winreg.QueryValueEx(key, "AutoConfigURL")
            expected = f"http://127.0.0.1:{port}/proxy.pac"
            return str(val).strip().lower() == expected.lower()
    except Exception:
        return False

def broadcast_setting_change() -> None:
    if sys.platform != "win32":
        return
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result)
        )
    except Exception:
        pass

def enable_system_env_proxy(port: int = DEFAULT_PROXY_PORT) -> bool:
    if sys.platform != "win32":
        return False
    proxy_val = f"http://127.0.0.1:{port}"
    no_proxy_val = "localhost,127.0.0.1,::1"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_SET_VALUE
        )
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            winreg.SetValueEx(key, var, 0, winreg.REG_SZ, proxy_val)
        for var in ["NO_PROXY", "no_proxy"]:
            winreg.SetValueEx(key, var, 0, winreg.REG_SZ, no_proxy_val)
        winreg.CloseKey(key)
        broadcast_setting_change()
        return True
    except Exception:
        return False

def disable_system_env_proxy() -> bool:
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_SET_VALUE
        )
        for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"]:
            try:
                winreg.DeleteValue(key, var)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        broadcast_setting_change()
        return True
    except Exception:
        return False

def is_system_env_proxy_enabled(port: int = DEFAULT_PROXY_PORT) -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            val, _ = winreg.QueryValueEx(key, "HTTPS_PROXY")
            expected = f"http://127.0.0.1:{port}"
            return str(val).strip().lower() == expected.lower()
    except Exception:
        return False

def is_proxy_running(port: int = DEFAULT_PROXY_PORT, timeout: float = 1.0) -> bool:
    import urllib.request
    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "451bypass/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class LocalProxy:
    def __init__(self, port: int = DEFAULT_PROXY_PORT):
        self.port = port
        self.cfg: AppConfig = load_config()
        self.start_time = time.time()
        self.active_tunnels = 0
        self.total_tunnels = 0
        self.server: Optional[asyncio.AbstractServer] = None
        self._session = None

    def _get_worker_tunnel_url(self, target: str) -> str:
        secret_param = f"&secret={self.cfg.gateway_secret}" if self.cfg.gateway_secret else ""
        return f"https://{self.cfg.worker_name}.{self.cfg.subdomain}.workers.dev/tunnel?target={target}{secret_param}"

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        import aiohttp

        try:
            req_line = await asyncio.wait_for(reader.readline(), timeout=10.0)
        except Exception:
            writer.close()
            return

        if not req_line:
            writer.close()
            return

        parts = req_line.decode("utf-8", errors="ignore").split()
        if not parts:
            writer.close()
            return

        method = parts[0].upper()
        path = parts[1] if len(parts) > 1 else "/"

        headers = {}
        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            except Exception:
                break
            if not line or line == b"\r\n":
                break
            line_str = line.decode("utf-8", errors="ignore").strip()
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        # 1. Health check
        if method == "GET" and (path == "/health" or path == "/status"):
            uptime = int(time.time() - self.start_time)
            resp = json.dumps({
                "status": "ok",
                "service": "451bypass Local Daemon",
                "port": self.port,
                "uptime_seconds": uptime,
                "active_tunnels": self.active_tunnels,
                "total_tunnels": self.total_tunnels,
                "worker": f"{self.cfg.worker_name}.{self.cfg.subdomain}.workers.dev"
            }).encode("utf-8")
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(resp)).encode() + b"\r\nConnection: close\r\n\r\n" + resp)
            await writer.drain()
            writer.close()
            return

        # 2. Dynamic PAC file
        if method == "GET" and path == "/proxy.pac":
            active_domains = set(get_active_domains(self.cfg))
            pac_content = get_pac_script(active_domains, self.port).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/x-ns-proxy-autoconfig\r\n"
                b"Cache-Control: no-cache, no-store, must-revalidate\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Content-Length: " + str(len(pac_content)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + pac_content
            )
            await writer.drain()
            writer.close()
            return

        # 3. HTTPS CONNECT Tunnel
        if method == "CONNECT":
            target = path
            last_colon = target.rfind(":")
            host = target[:last_colon] if last_colon != -1 else target
            port_str = target[last_colon + 1:] if last_colon != -1 else "443"
            port = int(port_str) if port_str.isdigit() else 443

            active_domains = set(get_active_domains(self.cfg))
            is_blocked = False
            lower_host = host.lower()
            if lower_host in active_domains:
                is_blocked = True
            else:
                dot = lower_host.find('.')
                while dot != -1:
                    lower_host = lower_host[dot + 1:]
                    if lower_host in active_domains:
                        is_blocked = True
                        break
                    dot = lower_host.find('.')

            if not is_blocked or not self.cfg.subdomain:
                # Direct TCP tunnel (100% provider speed, or fallback if worker not configured yet)
                try:
                    remote_reader, remote_writer = await asyncio.open_connection(host, port)
                    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await writer.drain()

                    async def pipe(r, w):
                        try:
                            while True:
                                data = await r.read(65536)
                                if not data:
                                    break
                                w.write(data)
                                await w.drain()
                        except Exception:
                            pass
                        finally:
                            try:
                                w.close()
                                await w.wait_closed()
                            except Exception:
                                pass

                    t1 = asyncio.create_task(pipe(reader, remote_writer))
                    t2 = asyncio.create_task(pipe(remote_reader, writer))
                    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                except Exception:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                return

            tunnel_url = self._get_worker_tunnel_url(target)
            self.active_tunnels += 1
            self.total_tunnels += 1

            client_timeout = aiohttp.ClientTimeout(total=None, connect=15.0)
            ws_headers = {"User-Agent": "451bypass/1.0"}
            if self.cfg.gateway_secret:
                ws_headers["X-451bypass-Secret"] = self.cfg.gateway_secret

            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                try:
                    async with session.ws_connect(tunnel_url, headers=ws_headers) as ws:
                        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                        await writer.drain()

                        async def client_to_ws():
                            try:
                                while True:
                                    data = await reader.read(65536)
                                    if not data:
                                        break
                                    await ws.send_bytes(data)
                            except Exception:
                                pass
                            finally:
                                try:
                                    await ws.close()
                                except Exception:
                                    pass

                        async def ws_to_client():
                            try:
                                async for msg in ws:
                                    if msg.type == aiohttp.WSMsgType.BINARY:
                                        writer.write(msg.data)
                                        await writer.drain()
                                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                        break
                            except Exception:
                                pass
                            finally:
                                try:
                                    writer.close()
                                    await writer.wait_closed()
                                except Exception:
                                    pass

                        t1 = asyncio.create_task(client_to_ws())
                        t2 = asyncio.create_task(ws_to_client())
                        done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
                        for t in pending:
                            t.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                except Exception as e:
                    DAEMON_LOG = PRIMARY_CONFIG_DIR / "daemon.log"
                    try:
                        with open(DAEMON_LOG, "a", encoding="utf-8") as f:
                            f.write(f"Tunnel connect error to {tunnel_url}: {type(e)} {e}\n")
                    except Exception:
                        pass
                    try:
                        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                        await writer.drain()
                        writer.close()
                    except Exception:
                        pass
                finally:
                    self.active_tunnels = max(0, self.active_tunnels - 1)
            return

        # 4. Standard HTTP proxy and gateway requests (GET, POST, PUT, DELETE, etc.)
        from urllib.parse import urlsplit

        target_host = None
        target_port = 80
        target_path = path

        if path.startswith("http://") or path.startswith("https://"):
            parsed = urlsplit(path)
            target_host = parsed.hostname or ""
            target_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            target_path = parsed.path or "/"
            if parsed.query:
                target_path += f"?{parsed.query}"
        elif "host" in headers:
            host_header = headers["host"]
            if ":" in host_header:
                h_parts = host_header.split(":", 1)
                target_host = h_parts[0]
                try:
                    target_port = int(h_parts[1])
                except ValueError:
                    target_port = 80
            else:
                target_host = host_header
                target_port = 80

        if not target_host:
            writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\n\r\nMissing host header\r\n")
            await writer.drain()
            writer.close()
            return

        is_loopback = target_host.lower() in ("127.0.0.1", "localhost", "::1")
        if is_loopback and target_port == self.port:
            # Direct API request to 451bypass (AI Gateway reverse proxy)
            if self.cfg.worker_name and self.cfg.subdomain and (target_path.startswith("/v1") or "/" in target_path.strip("/")):
                upstream_url = f"https://{self.cfg.worker_name}.{self.cfg.subdomain}.workers.dev{target_path}"
                client_timeout = aiohttp.ClientTimeout(total=60.0)
                fwd_headers = {k: v for k, v in headers.items() if k not in ("host", "content-length", "connection")}
                fwd_headers["User-Agent"] = "451bypass/1.0"
                if self.cfg.gateway_secret:
                    fwd_headers["X-451bypass-Secret"] = self.cfg.gateway_secret

                body = None
                content_len = int(headers.get("content-length", "0")) if headers.get("content-length", "").isdigit() else 0
                if content_len > 0:
                    try:
                        body = await asyncio.wait_for(reader.readexactly(content_len), timeout=15.0)
                    except Exception:
                        pass

                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    try:
                        async with session.request(method, upstream_url, headers=fwd_headers, data=body) as resp:
                            resp_body = await resp.read()
                            out = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
                            for hk, hv in resp.headers.items():
                                if hk.lower() not in ("transfer-encoding", "content-length", "connection"):
                                    out += f"{hk}: {hv}\r\n"
                            out += f"Content-Length: {len(resp_body)}\r\nConnection: close\r\n\r\n"
                            writer.write(out.encode("utf-8") + resp_body)
                            await writer.drain()
                            writer.close()
                            return
                    except Exception as e:
                        err_bytes = json.dumps({"error": str(e)}).encode()
                        writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\nContent-Length: " + str(len(err_bytes)).encode() + b"\r\nConnection: close\r\n\r\n" + err_bytes)
                        await writer.drain()
                        writer.close()
                        return

            resp_info = json.dumps({
                "service": "451bypass",
                "status": "running",
                "port": self.port,
                "pac": f"http://127.0.0.1:{self.port}/proxy.pac"
            }).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(resp_info)).encode() + b"\r\nConnection: close\r\n\r\n" + resp_info)
            await writer.drain()
            writer.close()
            return

        # Prepare request head for forwarding
        req_head = f"{method} {target_path} HTTP/1.1\r\n"
        for k, v in headers.items():
            lk = k.lower()
            if lk in ("proxy-connection", "proxy-authorization"):
                continue
            if lk == "connection":
                v = "close"
            req_head += f"{k}: {v}\r\n"
        if "connection" not in headers:
            req_head += "connection: close\r\n"
        req_head += "\r\n"
        req_bytes = req_head.encode("utf-8")

        # Check domain blockage
        active_domains = set(get_active_domains(self.cfg))
        is_blocked = False
        if not is_loopback:
            lower_host = target_host.lower()
            if lower_host in active_domains:
                is_blocked = True
            else:
                dot = lower_host.find('.')
                while dot != -1:
                    lower_host = lower_host[dot + 1:]
                    if lower_host in active_domains:
                        is_blocked = True
                        break
                    dot = lower_host.find('.')

        if not is_blocked or not self.cfg.subdomain:
            # Direct TCP connection (loopback, e.g. Omniroute, unblocked external, or fallback)
            try:
                remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
                remote_writer.write(req_bytes)
                await remote_writer.drain()

                async def pipe_body(r, w):
                    try:
                        while True:
                            data = await r.read(65536)
                            if not data:
                                break
                            w.write(data)
                            await w.drain()
                    except Exception:
                        pass
                    finally:
                        try:
                            w.close()
                            await w.wait_closed()
                        except Exception:
                            pass

                t1 = asyncio.create_task(pipe_body(reader, remote_writer))
                t2 = asyncio.create_task(pipe_body(remote_reader, writer))
                done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            except Exception:
                try:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                except Exception:
                    pass
            return

        # Blocked external host -> WebSocket tunnel to Cloudflare Worker
        tunnel_url = self._get_worker_tunnel_url(f"{target_host}:{target_port}")
        self.active_tunnels += 1
        self.total_tunnels += 1
        client_timeout = aiohttp.ClientTimeout(total=None, connect=15.0)
        ws_headers = {"User-Agent": "451bypass/1.0"}
        if self.cfg.gateway_secret:
            ws_headers["X-451bypass-Secret"] = self.cfg.gateway_secret

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            try:
                async with session.ws_connect(tunnel_url, headers=ws_headers) as ws:
                    await ws.send_bytes(req_bytes)

                    async def client_to_ws():
                        try:
                            while True:
                                data = await reader.read(65536)
                                if not data:
                                    break
                                await ws.send_bytes(data)
                        except Exception:
                            pass
                        finally:
                            try:
                                await ws.close()
                            except Exception:
                                pass

                    async def ws_to_client():
                        try:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.BINARY:
                                    writer.write(msg.data)
                                    await writer.drain()
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                        except Exception:
                            pass
                        finally:
                            try:
                                writer.close()
                                await writer.wait_closed()
                            except Exception:
                                pass

                    t1 = asyncio.create_task(client_to_ws())
                    t2 = asyncio.create_task(ws_to_client())
                    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
            except Exception:
                try:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                except Exception:
                    pass
            finally:
                self.active_tunnels = max(0, self.active_tunnels - 1)

    async def start(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", self.port))
            self.server = await asyncio.start_server(self.handle_client, sock=sock)
        except OSError as e:
            if getattr(e, "winerror", None) == 10048 or "already in use" in str(e).lower():
                if is_proxy_running(self.port):
                    return
            raise
        async with self.server:
            await self.server.serve_forever()

def run_server(port: int = DEFAULT_PROXY_PORT):
    proxy = LocalProxy(port=port)
    try:
        asyncio.run(proxy.start())
    except (KeyboardInterrupt, SystemExit):
        pass
