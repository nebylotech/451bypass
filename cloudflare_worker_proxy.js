const FALLBACK_CORE_DOMAINS = new Set([
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
]);
const CUSTOM_DOMAINS = new Set([]);
const REMOTE_CORE_URL = "https://raw.githubusercontent.com/451bypass/domains/main/domains/core.txt";
const DEFAULT_DOMAIN = "";

let cachedCoreDomains = null;
let lastCoreFetch = 0;
const CORE_CACHE_TTL_MS = 3600000;

async function getCoreDomains(env) {
  const now = Date.now();
  if (cachedCoreDomains && (now - lastCoreFetch < CORE_CACHE_TTL_MS)) {
    return cachedCoreDomains;
  }
  const url = (env && env.REMOTE_CORE_URL) || REMOTE_CORE_URL;
  if (url) {
    try {
      const resp = await fetch(url, {
        cf: { cacheTtl: 3600, cacheEverything: true }
      });
      if (resp.ok) {
        const text = await resp.text();
        const list = text.split("\n")
          .map(l => l.trim().toLowerCase())
          .filter(l => l && !l.startsWith("#"));
        if (list.length > 0) {
          cachedCoreDomains = new Set(list);
          lastCoreFetch = now;
          return cachedCoreDomains;
        }
      }
    } catch (e) {
    }
  }
  if (cachedCoreDomains) return cachedCoreDomains;
  return FALLBACK_CORE_DOMAINS;
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    const url = new URL(request.url);
    const coreDomains = await getCoreDomains(env);

    if (url.pathname === "/core-domains") {
      return new Response(Array.from(coreDomains).join("\n") + "\n", {
        headers: { "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/custom-domains") {
      return new Response(Array.from(CUSTOM_DOMAINS).join("\n") + "\n", {
        headers: { "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/" || url.pathname === "/health") {
      const totalDomains = new Set([...coreDomains, ...CUSTOM_DOMAINS]);
      return new Response(
        JSON.stringify({
          status: "ok",
          gateway: "451bypass AI Gateway",
          default_domain: DEFAULT_DOMAIN || null,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size,
          total_domains_count: totalDomains.size,
          custom_domains: Array.from(CUSTOM_DOMAINS),
          core_domains: Array.from(coreDomains),
          routes: {
            multi_domain: `https://${url.host}/<domain>/v1/...`,
            default_domain: DEFAULT_DOMAIN ? `https://${url.host}/v1/... -> ${DEFAULT_DOMAIN}/v1/...` : "disabled (domain prefix required)"
          }
        }, null, 2),
        {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }

    const cleanPath = url.pathname.replace(/^\/+/, "");
    const slashIndex = cleanPath.indexOf("/");
    const firstSegment = slashIndex >= 0 ? cleanPath.substring(0, slashIndex).toLowerCase() : cleanPath.toLowerCase();

    let targetDomain;
    let targetPath;

    if (coreDomains.has(firstSegment) || CUSTOM_DOMAINS.has(firstSegment)) {
      targetDomain = firstSegment;
      targetPath = slashIndex >= 0 ? cleanPath.substring(slashIndex) : "/";
    } else if (DEFAULT_DOMAIN) {
      targetDomain = DEFAULT_DOMAIN;
      targetPath = "/" + cleanPath;
    } else {
      return new Response(
        JSON.stringify({
          error: "Domain not specified or not allowed by 451bypass AI Gateway",
          requested_segment: firstSegment,
          usage: `https://${url.host}/<domain>/v1/... (e.g. https://${url.host}/api.openai.com/v1/chat/completions)`,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size
        }, null, 2),
        {
          status: 400,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        }
      );
    }

    const targetUrl = `https://${targetDomain}${targetPath}${url.search}`;

    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", targetDomain);

    const fakeUSIP = "8.8.8.8";
    newHeaders.set("x-forwarded-for", fakeUSIP);
    newHeaders.set("x-real-ip", fakeUSIP);

    const isGetOrHead = ["GET", "HEAD"].includes(request.method.toUpperCase());
    const fetchOptions = {
      method: request.method,
      headers: newHeaders,
      body: isGetOrHead ? null : request.body,
      redirect: "follow",
    };

    const maxRetries = 2;
    let response;

    for (let i = 0; i <= maxRetries; i++) {
      try {
        response = await fetch(targetUrl, fetchOptions);
        if (![502, 503, 504].includes(response.status)) break;
      } catch (err) {
        if (i === maxRetries) {
          return new Response(
            JSON.stringify({ error: "Upstream gateway connection error", message: err.message }),
            { status: 502, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" } }
          );
        }
      }
      await new Promise(r => setTimeout(r, 200 * (i + 1)));
    }

    const respHeaders = new Headers(response.headers);
    respHeaders.set("Access-Control-Allow-Origin", "*");

    respHeaders.delete("content-encoding");
    respHeaders.delete("content-length");
    respHeaders.delete("transfer-encoding");
    respHeaders.delete("connection");

    const respContentType = response.headers.get("content-type") || "";
    if (respContentType.includes("text/event-stream")) {
      respHeaders.set("Cache-Control", "no-cache, no-transform");
      respHeaders.set("X-Accel-Buffering", "no");
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders
    });
  }
};
