import { connect } from 'cloudflare:sockets';

const EMBEDDED_CORE_DOMAINS = new Set(["ai.api.nvidia.com", "ai.com", "ai.google", "ai.google.dev", "aistudio.google.com", "alkalimakersuite-pa.clients6.google.com", "anthropic.com", "api.anthropic.com", "api.deepseek.com", "api.elevenlabs.io", "api.groq.com", "api.mistral.ai", "api.ngc.nvidia.com", "api.nvcf.nvidia.com", "api.nvidia.com", "api.openai.com", "api.perplexity.ai", "api.x.ai", "bard.google.com", "build.nvidia.com", "catalog.ngc.nvidia.com", "chat.com", "chatgpt.com", "claude.ai", "claude.com", "colab.research.google.com", "deepmind.com", "deepmind.google", "deepseek.com", "developer.nvidia.com", "elevenlabs.io", "gemini.google.com", "generativelanguage.googleapis.com", "google.ai", "grok.com", "grok.x.com", "groq.com", "grpc.nvcf.nvidia.com", "health.api.nvidia.com", "idx.google.dev", "integrate.api.nvidia.com", "makersuite.google.com", "mistral.ai", "notebook.google", "notebooklm.google", "notebooklm.google.com", "notion-emojis.s3-us-west-2.amazonaws.com", "notion-static.com", "notion.com", "notion.new", "notion.site", "notion.so", "nvcf.nvidia.com", "nvidia.com", "oaistatic.com", "oaiusercontent.com", "openai.com", "openrouter.ai", "perplexity.ai", "proactivebackend-pa.googleapis.com", "production-openaicom-storage.azureedge.net", "sora.com", "x.ai"]);
const CUSTOM_DOMAINS = new Set([]);
const REMOTE_CORE_URL = "https://raw.githubusercontent.com/nebylotech/451bypass/main/domains/core.txt";
const DEFAULT_DOMAIN = "";
const GATEWAY_SECRET = "";

const CF_PROXIED_ROOTS = [
  "chatgpt.com",
  "openai.com",
  "oaistatic.com",
  "oaiusercontent.com",
  "sora.com",
  "claude.ai",
  "anthropic.com",
  "grok.com",
  "x.ai"
];

const PROXY_HOSTS = [
  "proxyip.cmliussss.net",
  "proxyip.aliyun.fxxk.dedyn.io"
];

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
        cachedCoreDomains = new Set([...EMBEDDED_CORE_DOMAINS, ...list]);
        lastCoreFetch = now;
        return cachedCoreDomains;
      }
    } catch (e) {
    }
  }
  if (cachedCoreDomains) return cachedCoreDomains;
  return EMBEDDED_CORE_DOMAINS;
}

function isDomainAllowed(host, coreDomains, customDomains) {
  if (!host) return false;
  host = host.toLowerCase().trim();
  if (coreDomains.has(host) || customDomains.has(host)) return true;
  const parts = host.split(".");
  for (let i = 1; i < parts.length - 1; i++) {
    const parent = parts.slice(i).join(".");
    if (coreDomains.has(parent) || customDomains.has(parent)) return true;
  }
  return false;
}

function isKnownCloudflare(host) {
  if (!host) return false;
  host = host.toLowerCase().trim();
  return CF_PROXIED_ROOTS.some(r => host === r || host.endsWith("." + r));
}

async function connectUpstream(targetHost, targetPort) {
  if (isKnownCloudflare(targetHost)) {
    for (const pHost of PROXY_HOSTS) {
      try {
        const sock = connect({ hostname: pHost, port: targetPort });
        await sock.opened;
        return sock;
      } catch (e) {
      }
    }
  }

  try {
    const directSock = connect({ hostname: targetHost, port: targetPort });
    await directSock.opened;
    return directSock;
  } catch (err) {
    for (const pHost of PROXY_HOSTS) {
      try {
        const fallbackSock = connect({ hostname: pHost, port: targetPort });
        await fallbackSock.opened;
        return fallbackSock;
      } catch (e) {
      }
    }
    throw err;
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Security check: require secret token to prevent unauthorized public access
    const secret = (env && env.GATEWAY_SECRET) || GATEWAY_SECRET;
    if (secret) {
      const clientSecret = request.headers.get("X-451bypass-Secret") || url.searchParams.get("secret");
      if (clientSecret !== secret) {
        return new Response("Not Found", {
          status: 404,
          headers: { "Content-Type": "text/plain; charset=utf-8" }
        });
      }
    }

    // 1. WebSocket TCP Tunnel for HTTPS (CONNECT)
    if (url.pathname === "/tunnel") {
      const upgradeHeader = request.headers.get("Upgrade");
      if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
        return new Response("Expected Upgrade: websocket", { status: 426 });
      }

      const target = url.searchParams.get("target");
      if (!target) {
        return new Response("Missing target parameter", { status: 400 });
      }

      const lastColon = target.lastIndexOf(":");
      const host = lastColon !== -1 ? target.substring(0, lastColon) : target;
      const portStr = lastColon !== -1 ? target.substring(lastColon + 1) : "443";
      const port = parseInt(portStr, 10) || 443;

      const coreDomains = await getCoreDomains(env);
      if (!isDomainAllowed(host, coreDomains, CUSTOM_DOMAINS)) {
        return new Response(`Domain '${host}' not allowed by 451bypass policy`, { status: 403 });
      }

      let tcpSocket;
      try {
        tcpSocket = await connectUpstream(host, port);
      } catch (err) {
        return new Response(`Failed to connect to ${host}:${port}: ${err.message}`, { status: 502 });
      }

      const webSocketPair = new WebSocketPair();
      const [client, server] = Object.values(webSocketPair);

      server.accept();

      const writer = tcpSocket.writable.getWriter();
      const reader = tcpSocket.readable.getReader();

      server.addEventListener("message", async (event) => {
        try {
          let data;
          if (typeof event.data === "string") {
            data = new TextEncoder().encode(event.data);
          } else if (event.data instanceof ArrayBuffer) {
            data = new Uint8Array(event.data);
          } else if (ArrayBuffer.isView(event.data)) {
            data = new Uint8Array(event.data.buffer, event.data.byteOffset, event.data.byteLength);
          }
          if (data && data.byteLength > 0) {
            await writer.write(data);
          }
        } catch (e) {
          try { server.close(1011, e.message); } catch (_) {}
          try { tcpSocket.close(); } catch (_) {}
        }
      });

      server.addEventListener("close", () => {
        try { writer.close(); } catch (_) {}
        try { tcpSocket.close(); } catch (_) {}
      });

      server.addEventListener("error", () => {
        try { tcpSocket.close(); } catch (_) {}
      });

      (async () => {
        try {
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            if (value && value.byteLength > 0) {
              const exactSlice = value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
              server.send(exactSlice);
            }
          }
        } catch (e) {
        } finally {
          try { server.close(1000, "Normal closure"); } catch (_) {}
          try { tcpSocket.close(); } catch (_) {}
        }
      })();

      return new Response(null, { status: 101, webSocket: client });
    }

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
          gateway: "451bypass AI Gateway and Tunnel",
          tunnel: "active",
          sni_fallback: "active",
          default_domain: DEFAULT_DOMAIN || null,
          core_domains_count: coreDomains.size,
          custom_domains_count: CUSTOM_DOMAINS.size,
          total_domains_count: totalDomains.size,
          custom_domains: Array.from(CUSTOM_DOMAINS),
          core_domains: Array.from(coreDomains),
          routes: {
            tunnel: `wss://${url.host}/tunnel?target=<host>:<port>`,
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

    if (isDomainAllowed(firstSegment, coreDomains, CUSTOM_DOMAINS)) {
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
