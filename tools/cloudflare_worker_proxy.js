import { connect } from 'cloudflare:sockets';

const EMBEDDED_CORE_DOMAINS = new Set(["4pda.to", "a-vrv.akamaized.net", "abercrombie.com", "adidas.com", "adobe.com", "adobe.io", "adobe.net", "affinity.studio", "ai-chat.bsg.brave.com", "ai.com", "ai.google", "ai.google.dev", "aircanada.com", "aistudio.google.com", "akc.org", "alkalimakersuite-pa.clients6.google.com", "all3dp.com", "alphacoders.com", "alza.hu", "amazfitwatchfaces.com", "amplitude.com", "analog.com", "andrevi.ch", "ansys.com", "anthropic.com", "anthropic.qualtrics.com", "api.anthropic.com", "api.cohere.ai", "api.deepseek.com", "api.elevenlabs.io", "api.groq.com", "api.jetbrains.ai", "api.mistral.ai", "api.ngc.nvidia.com", "api.openai.com", "api.perplexity.ai", "api.themoviedb.org", "api.x.ai", "arc.net", "arduino.cc", "assets.heroku.com", "atlassian.com", "att.com", "augmentcode.com", "autodesk.com", "backend-v2.crixet.com", "bard.google.com", "bell-sw.com", "bestbuy.com", "bitdefender.com", "bitnami.com", "blinkshot.io", "bosch.com", "boschaftermarket.com", "boschautoparts.com", "broadcom.com", "broncosportforum.com", "btod.com", "buanzo.org", "buf.build", "build.nvidia.com", "builds.parsec.app", "buymeacoffee.com", "canva.com", "canva.dev", "capacitorjs.com", "carrefouruae.com", "cats.com", "cdn.web-platform.io", "cdromance.org", "cdw.com", "chainreactioncycles.com", "chaos.com", "chat.com", "chatgpt.com", "cisco.com", "cisecurity.org", "citrix.com", "clamav.net", "clashofclans.com", "claude.ai", "claude.com", "clevelandclinic.org", "clickup.com", "clip.opus.pro", "code.gist.build", "codeium.com", "coingate.com", "colab.research.google.com", "community.sophos.com", "connect.ngrok-agent.com", "contabo.com", "copilot.microsoft.com", "corsair.com", "cpu-monkey.com", "credly.com", "crunchyroll.com", "cursor-cdn.com", "cursor.sh", "cvedetails.com", "daemon-tools.cc", "dashboard.algolia.com", "dashboard.gitguardian.com", "data-cdn.mbamupdates.com", "data.cline.bot", "deepl.com", "deepmind.com", "deepmind.google", "deezer.com", "dell.com", "designer.microsoft.com", "developer.nvidia.com", "devexpress.com", "diabrowser.com", "disctech.com", "disneyplus.com", "docs.liquibase.com", "document360.com", "document360.io", "download3.omnissa.com", "downloads.intercomcdn.com", "ducati.com", "dyson.com", "easydmarc.com", "editorx.com", "elevenlabs.io", "eneba.com", "etsy.com", "exchanger.bits.media", "expandrive.com", "extremetech.com", "f1.com", "fast.com", "filebin.net", "fivetran.com", "flir.com", "flir.eu", "flourish.studio", "fluke.com", "flukenetworks.com", "flyertalk.com", "footballapi.pulselive.com", "force-user-content.com", "force.com", "formula1.com", "forum.netgate.com", "framer.app", "framer.com", "framercanvas.com", "framerusercontent.com", "freeimages.com", "fxnetworks.com", "g2a.com", "gamestop.com", "gaming.amazon.com", "geforcenow.com", "gemini.google.com", "generativeai.google", "generativelanguage.googleapis.com", "genspark.ai", "geolocation.onetrust.com", "getoutline.com", "gfn.am", "ghostrc.game.idtech.services", "global.fncstatic.com", "gofund.me", "gofundme.com", "gonift.com", "google.ai", "gpu-monkey.com", "gql.twitch.tv", "grafana.com", "graylog.org", "grizzlysms.com", "grok.com", "grok.x.com", "groq.com", "groupon.com", "guilded.gg", "habr.com", "hashicorp.com", "hbomax.com", "hc-ping.com", "hchk.io", "healthline.com", "hollisterco.com", "home-connect.com", "home.by.me", "hostinger.com", "hotels.com", "housebrand.com", "htmhell.dev", "httptoolkit.com", "hume.ai", "hybrid-analysis.com", "ibm.com", "idx.google.dev", "iedb.org", "iherb.com", "ikea.com", "image.tmdb.org", "imgur.com", "indeed.com", "integrate.api.nvidia.com", "intel.com", "intel.de", "intelix.sophos.com", "intercom.io", "intuit.com", "intuitibits.com", "itninja.com", "jamf.com", "jetbrains.com", "jetbrains.space", "jetbrains.team", "joesandbox.com", "kaggle.com", "kaleido.ai", "keysight.com", "kinogo.la", "klarna.com", "kmail-lists.com", "lambdalabs.com", "langdock.com", "last.fm", "ldoceonline.com", "legalshield.com", "lidarr.audio", "lifehacker.com", "lightning.ai", "lookerstudio.google.com", "lyst.com", "mailerlite.com", "mailinator.com", "makersuite.google.com", "manus.im", "manybooks.net", "marvelsnap.com", "mattermost.com", "max.com", "medicalnewstoday.com", "meetup.com", "metopera.org", "middlewareinventory.com", "mintmobile.com", "miracleptr.wordpress.com", "mixcloud.com", "mongodb.com", "monoprice.com", "mouser.com", "mouser.fi", "mssg.me", "multisim.com", "myheritage.com", "myjetbrains.com", "myparallels.com", "myqrcode.com", "nba.com", "neo4j.com", "netacad.com", "netapp.com", "netflix.ca", "netflix.com", "netflix.net", "netflixinvestor.com", "netflixtechblog.com", "netlify.com", "new.abb.com", "newark.com", "news.google.com", "newsroom.porsche.com", "nfl.com", "nflxext.com", "nflximg.com", "nflxso.net", "nflxvideo.net", "ngrok.com", "ni.com", "nike.com", "nitropdf.com", "nordaccount.com", "nordvpn.com", "notebook.google", "notebooklm.google", "notebooklm.google.com", "notion-emojis.s3-us-west-2.amazonaws.com", "notion-static.com", "notion.com", "notion.new", "notion.site", "notion.so", "nxp.com", "oaistatic.com", "oaiusercontent.com", "ocstore.com", "octopus.do", "omnissa.com", "onshape.com", "openai.com", "openrouter.ai", "oracle.com", "oraclecloud.com", "paddle.com", "paddlestatus.com", "pandasecurity.com", "parallels.cn", "parallels.com", "parallels.net", "paritydeals.com", "patreon.com", "patreonusercontent.com", "paywithmoon.com", "pcgamesn.com", "pcmag.com", "penguin.com", "penguinrandomhouse.com", "pexels.com", "philiascans.org", "pingdom.com", "pkgs.tailscale.com", "platform.activestate.com", "plugshare.com", "posthog.com", "premierleague.com", "primark.com", "primevideo.com", "proactivebackend-pa.googleapis.com", "production-openaicom-storage.azureedge.net", "profitwell.com", "prowlarr.com", "public.parsec.app", "qobuz.com", "qodana.cloud", "qoder.com", "qt.io", "qualcomm.com", "quicknode.com", "qwant.com", "reactflow.dev", "recraft.ai", "redd.it", "reddit.com", "redditmedia.com", "redditstatic.com", "redis.io", "redislabs.com", "remna.st", "remove.bg", "research.net", "reve.art", "rlcdn.com", "salesforce-experience.com", "salesforce-hub.com", "salesforce-scrt.com", "salesforce-setup.com", "salesforce-sites.com", "salesforce.com", "salesforceliveagent.com", "schneider-electric.com", "sdxcentral.com", "se.com", "semrush.com", "sentry.dev", "sentry.io", "sephora.com", "servarr.com", "sfdcopens.com", "sharefile.com", "shinyhardware.co.uk", "shop.gameloft.com", "sigsauer.com", "singlekey-id.com", "site.com", "siteground.com", "sketchup.com", "sky.com", "smartbear.co", "smartbear.com", "smartdeploy.com", "snapgametech.com", "snapgene.com", "snort.org", "snyk.io", "solarwinds.com", "sonara.ai", "sora.com", "spacelift.io", "spiceworks.com", "spitfireaudio.com", "spotify.com", "squareup.com", "strava.com", "streamable.com", "suggestqueries.google.com", "supercell.com", "support.anydesk.com", "support.xerox.com", "surveymonkey.com", "swagger.io", "swapd.co", "synoforum.com", "syslog-ng.com", "tableau.com", "talosintelligence.com", "teamviewer.com", "techbargains.com", "telemetr.io", "tempmail.plus", "terraform.io", "theaudiodb.com", "themoviedb.org", "ti.com", "tidal.com", "timberland.de", "tmdb-image-prod.b-cdn.net", "tmdb.com", "tmdb.org", "toolbox.app", "trae.ai", "trailblazer.me", "trailhead.com", "transferwise.com", "tria.ge", "truthsocial.com", "tsmc.com", "tutanota.com", "typing.com", "uaudio.com", "uizard.io", "unscreen.com", "upwork.com", "usher.ttvnw.net", "vagrantcloud.com", "veeam.com", "verificationacademy.com", "vmware.com", "volkswagen-classic-parts.com", "vyos.io", "w.atwiki.jp", "walmart.com", "watchguard.com", "watermarkremover.io", "wbgames.com", "wdfiles.com", "weather.com", "webnames.ca", "weebly.com", "wetransfer.com", "widgetapp.stream", "wikidot.com", "windsurf.com", "wise.com", "wpengine.com", "wunderground.com", "www3.corsair.com", "x-minus.pro", "x.ai", "xiaomi.eu", "xrite.com", "xsts.auth.xboxlive.com", "yeggi.com", "youtrack.cloud", "zapier.com", "zedge.net", "zerossl.com"]);
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
