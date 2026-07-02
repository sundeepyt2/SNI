// SNI Stream Proxy — universal version
//
// Works on:
//   - Cloudflare Workers (use the whole file as-is)
//   - Deno Deploy (uses Deno.serve at the bottom)
//   - Vercel Edge Functions (rename handler to default export)
//   - Netlify Edge Functions (uses Deno.serve, same as Deno Deploy)
//
// What it does:
//   Proxies GET and POST requests to a allowlisted set of AllAnime-related
//   hosts. Used by SNI as a fallback when the user's IP is captcha-walled
//   on api.allanime.day directly.
//
// URL format (GET):
//   https://your-deployment/?url=<encoded_target_url>&h_<Header>=<value>
//
// URL format (POST):
//   POST https://your-deployment/?url=<encoded_target_url>
//   Body: the JSON body to forward
//   Content-Type: application/json (will be forwarded)

const ALLOWED_HOSTS = [
  "allanime.day",
  "allmanga.to",
  "allanime.uns.bio",
  "youtu-chan.com",
  "tools.fast4speed.rsvp",
  "fast4speed.rsvp",
  "megacloud.tv",
  "vixcloud.co",
  "mp4upload.com",
  "bysekoze.com",
  "vidnest.io",
  "ok.ru",
  "repackager.wixmp.com",
  "allanimenews.com",
  "sharepoint.com",
  "wixmp.com",
  "kwik.cx",
  "kwik.si",
  "streamwish.to",
  "megaplay.buzz",
  "flixcloud.cc",
];

function isAllowedHost(urlStr) {
  try {
    const u = new URL(urlStr);
    const host = u.hostname.toLowerCase();
    return ALLOWED_HOSTS.some(
      (h) => host === h || host.endsWith("." + h)
    );
  } catch (e) {
    return false;
  }
}

const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "content-length",
  "content-range",
  "accept-ranges",
  "cache-control",
  "etag",
  "last-modified",
];

const FORWARD_REQUEST_HEADERS = ["range", "if-range", "if-modified-since"];

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "range, content-type, if-range, if-modified-since",
  "access-control-expose-headers":
    "content-length, content-range, content-type",
};

function jsonError(message, status) {
  return new Response(JSON.stringify({ error: message }), {
    status: status || 400,
    headers: {
      "content-type": "application/json",
      "access-control-allow-origin": "*",
    },
  });
}

async function handleRequest(request) {
  const url = new URL(request.url);

  // CORS preflight
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers":
          "range, content-type, if-range, if-modified-since",
        "access-control-max-age": "86400",
      },
    });
  }

  if (request.method !== "GET" && request.method !== "POST") {
    return jsonError("Method not allowed - use GET or POST", 405);
  }

  // Health check
  const target = url.searchParams.get("url");
  if (!target) {
    return new Response(
      JSON.stringify({
        ok: true,
        service: "sni-stream-proxy",
        version: 3,
        allowedHosts: ALLOWED_HOSTS.length,
        message:
          "SNI proxy. Pass ?url=<target_url> to proxy a GET or POST request.",
      }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "access-control-allow-origin": "*",
        },
      }
    );
  }

  // Host allowlist
  if (!isAllowedHost(target)) {
    let host = "invalid-url";
    try { host = new URL(target).hostname; } catch (e) {}
    return jsonError("Host not allowed: " + host, 403);
  }

  // Build upstream headers (h_Referer, h_Origin, etc. -> Referer, Origin)
  const customHeaders = {};
  url.searchParams.forEach(function (v, k) {
    if (k.indexOf("h_") === 0) {
      customHeaders[k.slice(2)] = v;
    }
  });

  const upstreamHeaders = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    Accept: "*/*",
  };
  Object.keys(customHeaders).forEach(function (k) {
    upstreamHeaders[k] = customHeaders[k];
  });

  // Forward Range / conditional-fetch headers
  for (let i = 0; i < FORWARD_REQUEST_HEADERS.length; i++) {
    const h = FORWARD_REQUEST_HEADERS[i];
    const v = request.headers.get(h);
    if (v) upstreamHeaders[h] = v;
  }

  // For POST: forward content-type and body
  let bodyToSend = undefined;
  if (request.method === "POST") {
    const ct = request.headers.get("content-type");
    if (ct) upstreamHeaders["Content-Type"] = ct;
    bodyToSend = await request.text();
  }

  // Fetch upstream
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: upstreamHeaders,
      body: bodyToSend,
      redirect: "follow",
    });

    // Build response headers
    const respHeaders = new Headers(CORS_HEADERS);
    for (let i = 0; i < FORWARD_RESPONSE_HEADERS.length; i++) {
      const h = FORWARD_RESPONSE_HEADERS[i];
      const v = upstream.headers.get(h);
      if (v) respHeaders.set(h, v);
    }

    // Fix content-type for MP4 streams
    const contentType = upstream.headers.get("content-type") || "";
    const urlLower = target.toLowerCase();
    if (
      (contentType.indexOf("octet-stream") >= 0 || !contentType) &&
      (urlLower.indexOf(".mp4") >= 0 || urlLower.indexOf("/media") >= 0)
    ) {
      respHeaders.set("content-type", "video/mp4");
    }

    // Stream the response body back
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
    } catch (err) {
    const msg = (err && err.message) || "Unknown proxy error";
    return jsonError(msg, 502);
  }
}

// ─── Platform entry points ─────────────────────────────────────────────
// Pick ONE of these based on where you deploy. The others are inert.

// 1. Cloudflare Workers
export default {
  fetch(request) {
    return handleRequest(request);
  },
};

// 2. Deno Deploy / Netlify Edge Functions
//    (uncomment the line below, comment out the `export default` above)
// Deno.serve(handleRequest);

// 3. Vercel Edge Functions
//    Replace the `export default { fetch }` above with:
//    export const config = { runtime: "edge" };
//    export default function handler(request) { return handleRequest(request); }
