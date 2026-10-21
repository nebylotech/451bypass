import json
import datetime
from pathlib import Path
from typing import Tuple, List, Optional
from .config import AppConfig, save_config, DEFAULT_REMOTE_DOMAINS_URL
from .lists import load_custom_domains, load_core_domains
from .cloudflare import deploy_worker_script, CloudflareAPIError, check_worker_live_health

def generate_worker_script(
    custom_domains: List[str],
    default_domain: str = "",
    remote_core_url: str = DEFAULT_REMOTE_DOMAINS_URL
) -> str:
    custom_json = json.dumps(custom_domains)
    default_json = json.dumps(default_domain)
    remote_url_json = json.dumps(remote_core_url)

    return f"""import {{ connect }} from 'cloudflare:sockets';

const CUSTOM_DOMAINS = new Set({custom_json});
const REMOTE_CORE_URL = {remote_url_json};
const DEFAULT_DOMAIN = {default_json};

let cachedCoreDomains = null;
let lastCoreFetch = 0;
const CORE_CACHE_TTL_MS = 3600000;

async function getCoreDomains(env) {{
  const now = Date.now();
  if (cachedCoreDomains && (now - lastCoreFetch < CORE_CACHE_TTL_MS)) {{
    return cachedCoreDomains;
  }}
  const url = (env && env.REMOTE_CORE_URL) || REMOTE_CORE_URL;
  if (url) {{
    try {{
      const resp = await fetch(url, {{
        cf: {{ cacheTtl: 3600, cacheEverything: true }}
      }});
      if (resp.ok) {{
        const text = await resp.text();
        const list = text.split("\\n")
          .map(l => l.trim().toLowerCase())
          .filter(l => l && !l.startsWith("#"));
        cachedCoreDomains = new Set(list);
        lastCoreFetch = now;
        return cachedCoreDomains;
      }}
    }} catch (e) {{
    }}
  }}
  if (cachedCoreDomains) return cachedCoreDomains;
  return new Set();
}}

function isDomainAllowed(host, coreDomains, customDomains) {{
  if (!host) return false;
  host = host.toLowerCase().trim();
  if (coreDomains.has(host) || customDomains.has(host)) return true;
  const parts = host.split(".");
  for (let i = 1; i < parts.length - 1; i++) {{
    const parent = parts.slice(i).join(".");
    if (coreDomains.has(parent) || customDomains.has(parent)) return true;
  }}
  return false;
}}

export default {{
  async fetch(request, env, ctx) {{
    const url = new URL(request.url);

    // 1. WebSocket TCP Tunnel for HTTPS (CONNECT)
    if (url.pathname === "/tunnel") {{
      const upgradeHeader = request.headers.get("Upgrade");
      if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {{
        return new Response("Expected Upgrade: websocket", {{ status: 426 }});
      }}

      const target = url.searchParams.get("target");
      if (!target) {{
        return new Response("Missing target parameter", {{ status: 400 }});
      }}

      const lastColon = target.lastIndexOf(":");
      const host = lastColon !== -1 ? target.substring(0, lastColon) : target;
      const portStr = lastColon !== -1 ? target.substring(lastColon + 1) : "443";
      const port = parseInt(portStr, 10) || 443;

      const coreDomains = await getCoreDomains(env);
      if (!isDomainAllowed(host, coreDomains, CUSTOM_DOMAINS)) {{
        return new Response(`Domain '${{host}}' not allowed by 451bypass policy`, {{ status: 403 }});
      }}

      const webSocketPair = new WebSocketPair();
      const [client, server] = Object.values(webSocketPair);

      server.accept();

      let tcpSocket;
      try {{
        tcpSocket = connect({{ hostname: host, port: port }});
      }} catch (err) {{
        server.close(1011, "Connect error: " + err.message);
        return new Response(null, {{ status: 101, webSocket: client }});
      }}

      const writer = tcpSocket.writable.getWriter();
      const reader = tcpSocket.readable.getReader();

      server.addEventListener("message", async (event) => {{
        try {{
          let data;
          if (typeof event.data === "string") {{
            data = new TextEncoder().encode(event.data);
          }} else if (event.data instanceof ArrayBuffer) {{
            data = new Uint8Array(event.data);
          }} else if (ArrayBuffer.isView(event.data)) {{
            data = new Uint8Array(event.data.buffer, event.data.byteOffset, event.data.byteLength);
          }}
          if (data && data.byteLength > 0) {{
            await writer.write(data);
          }}
        }} catch (e) {{
          try {{ server.close(1011, e.message); }} catch (_) {{}}
          try {{ tcpSocket.close(); }} catch (_) {{}}
        }}
      }});

      server.addEventListener("close", () => {{
        try {{ writer.close(); }} catch (_) {{}}
        try {{ tcpSocket.close(); }} catch (_) {{}}
      }});

      server.addEventListener("error", () => {{
        try {{ tcpSocket.close(); }} catch (_) {{}}
      }});

      (async () => {{
        try {{
          while (true) {{
            const {{ value, done }} = await reader.read();
            if (done) break;
            if (value && value.byteLength > 0) {{
              const exactSlice = value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
              server.send(exactSlice);
            }}
          }}
        }} catch (e) {{
        }} finally {{
          try {{ server.close(1000, "Normal closure"); }} catch (_) {{}}
          try {{ tcpSocket.close(); }} catch (_) {{}}
        }}
      }})();

      return new Response(null, {{ status: 101, webSocket: client }});
    }}

    if (request.method === "OPTIONS") {{
      return new Response(null, {{
        headers: {{
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Max-Age": "86400",
        }},
      }});
    }}

    const coreDomains = await getCoreDomains(env);

    if (url.pathname === "/core-domains") {{
      return new Response(Array.from(coreDomains).join("\\n") + "\\n", {{
        headers: {{ "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" }}
      }});
    }}

    if (url.pathname === "/custom-domains") {{
      return new Response(Array.from(CUSTOM_DOMAINS).join("\\n") + "\\n", {{
        headers: {{ "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" }}
      }});
    }}

    if (url.pathname === "/" || url.pathname === "/health") {{
      const totalDomains = new Set([...coreDomains, ...CUSTOM_DOMAINS]);
      return new Response(
        JSON.stringify({{
          status: "ok",
          gateway: "451bypass AI Gateway & Tunnel",
          tunnel: "active",
          default_domain: DEFAULT_DOMAIN || null,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size,
          total_domains_count: totalDomains.size,
          custom_domains: Array.from(CUSTOM_DOMAINS),
          core_domains: Array.from(coreDomains),
          routes: {{
            tunnel: `wss://${{url.host}}/tunnel?target=<host>:<port>`,
            multi_domain: `https://${{url.host}}/<domain>/v1/...`,
            default_domain: DEFAULT_DOMAIN ? `https://${{url.host}}/v1/... -> ${{DEFAULT_DOMAIN}}/v1/...` : "disabled (domain prefix required)"
          }}
        }}, null, 2),
        {{
          headers: {{
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*"
          }}
        }}
      );
    }}

    const cleanPath = url.pathname.replace(/^\\/+/, "");
    const slashIndex = cleanPath.indexOf("/");
    const firstSegment = slashIndex >= 0 ? cleanPath.substring(0, slashIndex).toLowerCase() : cleanPath.toLowerCase();

    let targetDomain;
    let targetPath;

    if (coreDomains.has(firstSegment) || CUSTOM_DOMAINS.has(firstSegment)) {{
      targetDomain = firstSegment;
      targetPath = slashIndex >= 0 ? cleanPath.substring(slashIndex) : "/";
    }} else if (DEFAULT_DOMAIN) {{
      targetDomain = DEFAULT_DOMAIN;
      targetPath = "/" + cleanPath;
    }} else {{
      return new Response(
        JSON.stringify({{
          error: "Domain not specified or not allowed by 451bypass AI Gateway",
          requested_segment: firstSegment,
          usage: `https://${{url.host}}/<domain>/v1/... (e.g. https://${{url.host}}/api.openai.com/v1/chat/completions)`,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size
        }}, null, 2),
        {{
          status: 400,
          headers: {{ "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }}
        }}
      );
    }}

    const targetUrl = `https://${{targetDomain}}${{targetPath}}${{url.search}}`;

    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", targetDomain);

    const fakeUSIP = "8.8.8.8";
    newHeaders.set("x-forwarded-for", fakeUSIP);
    newHeaders.set("x-real-ip", fakeUSIP);

    const isGetOrHead = ["GET", "HEAD"].includes(request.method.toUpperCase());
    const fetchOptions = {{
      method: request.method,
      headers: newHeaders,
      body: isGetOrHead ? null : request.body,
      redirect: "follow",
    }};

    const maxRetries = 2;
    let response;

    for (let i = 0; i <= maxRetries; i++) {{
      try {{
        response = await fetch(targetUrl, fetchOptions);
        if (![502, 503, 504].includes(response.status)) break;
      }} catch (err) {{
        if (i === maxRetries) {{
          return new Response(
            JSON.stringify({{ error: "Upstream gateway connection error", message: err.message }}),
            {{ status: 502, headers: {{ "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }} }}
          );
        }}
      }}
      await new Promise(r => setTimeout(r, 200 * (i + 1)));
    }}

    const respHeaders = new Headers(response.headers);
    respHeaders.set("Access-Control-Allow-Origin", "*");

    respHeaders.delete("content-encoding");
    respHeaders.delete("content-length");
    respHeaders.delete("transfer-encoding");
    respHeaders.delete("connection");

    const respContentType = response.headers.get("content-type") || "";
    if (respContentType.includes("text/event-stream")) {{
      respHeaders.set("Cache-Control", "no-cache, no-transform");
      respHeaders.set("X-Accel-Buffering", "no");
    }}

    return new Response(response.body, {{
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders
    }});
  }}
}};
"""

def sync_to_cloudflare(cfg: AppConfig, force: bool = False) -> Tuple[bool, str]:
    if not cfg.account_id or not cfg.api_token:
        cfg.last_sync_status = "NOT_CONFIGURED"
        cfg.last_sync_error = "Cloudflare credentials not configured"
        save_config(cfg)
        return False, "Cloudflare credentials not configured"

    custom_domains = load_custom_domains()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not force and cfg.last_sync_status == "OK" and cfg.last_sync_domain_count == len(custom_domains):
        return True, "Already in sync"

    script = generate_worker_script(custom_domains, cfg.default_domain, cfg.remote_domains_url)

    try:
        success = deploy_worker_script(
            account_id=cfg.account_id,
            worker_name=cfg.worker_name,
            token=cfg.api_token,
            script_content=script
        )
        if success:
            cfg.last_sync_time = now
            cfg.last_sync_status = "OK"
            cfg.last_sync_error = None
            cfg.last_sync_domain_count = len(custom_domains)
            save_config(cfg)
            return True, f"Synchronized {len(custom_domains)} custom domains to Cloudflare Worker '{cfg.worker_name}'"
        else:
            cfg.last_sync_status = "ERROR"
            cfg.last_sync_error = "Deployment failed without explicit error"
            save_config(cfg)
            return False, "Deployment rejected by Cloudflare"
    except CloudflareAPIError as e:
        cfg.last_sync_status = "ERROR"
        cfg.last_sync_error = str(e)
        save_config(cfg)
        return False, f"Cloudflare API Error: {e}"
    except Exception as e:
        cfg.last_sync_status = "ERROR"
        cfg.last_sync_error = str(e)
        save_config(cfg)
        return False, f"Sync error: {e}"

def export_worker_script(cfg: AppConfig, path: Path) -> None:
    custom_domains = load_custom_domains()
    script = generate_worker_script(custom_domains, cfg.default_domain, cfg.remote_domains_url)
    path.write_text(script, encoding="utf-8")
