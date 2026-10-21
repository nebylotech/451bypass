import json
import datetime
from pathlib import Path
from typing import Tuple, List, Optional
from .config import AppConfig, save_config, DEFAULT_REMOTE_DOMAINS_URL
from .lists import load_custom_domains, load_core_domains
from .cloudflare import deploy_worker_script, CloudflareAPIError, check_worker_live_health

FALLBACK_CORE_LIST = [
    "api.anthropic.com",
    "api.cohere.ai",
    "api.deepseek.com",
    "api.elevenlabs.io",
    "api.groq.com",
    "api.mistral.ai",
    "api.ngc.nvidia.com",
    "api.openai.com",
    "api.perplexity.ai",
    "api.x.ai",
    "build.nvidia.com",
    "integrate.api.nvidia.com",
    "openrouter.ai"
]

def generate_worker_script(
    custom_domains: List[str],
    default_domain: str = "",
    remote_core_url: str = DEFAULT_REMOTE_DOMAINS_URL
) -> str:
    fallback_json = json.dumps(FALLBACK_CORE_LIST)
    custom_json = json.dumps(custom_domains)
    default_json = json.dumps(default_domain)
    remote_url_json = json.dumps(remote_core_url)

    return f"""const FALLBACK_CORE_DOMAINS = new Set({fallback_json});
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
        if (list.length > 0) {{
          cachedCoreDomains = new Set(list);
          lastCoreFetch = now;
          return cachedCoreDomains;
        }}
      }}
    }} catch (e) {{
    }}
  }}
  if (cachedCoreDomains) return cachedCoreDomains;
  return FALLBACK_CORE_DOMAINS;
}}

export default {{
  async fetch(request, env, ctx) {{
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

    const url = new URL(request.url);
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
          gateway: "51-BYPASS AI Gateway",
          default_domain: DEFAULT_DOMAIN || null,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size,
          total_domains_count: totalDomains.size,
          custom_domains: Array.from(CUSTOM_DOMAINS),
          core_domains: Array.from(coreDomains),
          routes: {{
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
          error: "Domain not specified or not allowed by 51-BYPASS AI Gateway",
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
