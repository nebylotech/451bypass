import os
import sys
import json
import time
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
        return f"https://{self.cfg.worker_name}.{self.cfg.subdomain}.workers.dev/tunnel?target={target}"

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
            tunnel_url = self._get_worker_tunnel_url(target)
            self.active_tunnels += 1
            self.total_tunnels += 1

            client_timeout = aiohttp.ClientTimeout(total=None, connect=15.0)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                try:
                    async with session.ws_connect(tunnel_url, headers={"User-Agent": "451bypass/1.0"}) as ws:
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

                        await asyncio.gather(client_to_ws(), ws_to_client(), return_exceptions=True)
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

        # 4. Standard HTTP proxy requests
        writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\n\r\n451bypass supports HTTPS CONNECT and PAC\r\n")
        await writer.drain()
        writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, "127.0.0.1", self.port)
        async with self.server:
            await self.server.serve_forever()

def run_server(port: int = DEFAULT_PROXY_PORT):
    proxy = LocalProxy(port=port)
    try:
        asyncio.run(proxy.start())
    except (KeyboardInterrupt, SystemExit):
        pass
