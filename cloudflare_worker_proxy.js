const ALLOWED_DOMAINS = new Set([
  "api.ngc.nvidia.com",
  "api.openai.com",
  "api.x.ai",
  "build.nvidia.com",
  "chatgpt.com",
  "integrate.api.nvidia.com"
]);
const DEFAULT_DOMAIN = "integrate.api.nvidia.com";

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

    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(
        JSON.stringify({
          status: "ok",
          gateway: "51-BYPASS AI Gateway",
          default_domain: DEFAULT_DOMAIN,
          managed_domains: Array.from(ALLOWED_DOMAINS),
          routes: {
            drop_in_default: `https://${url.host}/v1/... -> ${DEFAULT_DOMAIN}/v1/...`,
            multi_domain: `https://${url.host}/<domain>/v1/...`
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
    const firstSegment = slashIndex >= 0 ? cleanPath.substring(0, slashIndex) : cleanPath;

    let targetDomain;
    let targetPath;

    if (ALLOWED_DOMAINS.has(firstSegment)) {
      targetDomain = firstSegment;
      targetPath = slashIndex >= 0 ? cleanPath.substring(slashIndex) : "/";
    } else {
      targetDomain = DEFAULT_DOMAIN;
      targetPath = "/" + cleanPath;
    }

    if (!ALLOWED_DOMAINS.has(targetDomain)) {
      return new Response(
        JSON.stringify({
          error: "Domain not allowed by 51-BYPASS AI Gateway",
          target: targetDomain,
          allowed: Array.from(ALLOWED_DOMAINS)
        }, null, 2),
        {
          status: 403,
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
