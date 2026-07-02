// SNI Stream Proxy — Vercel Edge Function version
//
// Deploy:
//   1. Go to https://vercel.com -> New Project -> Import from GitHub
//      (or use the Vercel CLI: npm i -g vercel && vercel)
//   2. Create a file: api/proxy.js (this file, in the /api folder)
//   3. Deploy. You get a URL like https://your-project.vercel.app/api/proxy
//   4. Save to SNI:
//      sni config --update allanime_cf_worker_url='https://your-project.vercel.app/api/proxy'
//
// No credit card required. Free tier: 1 million Edge Function requests/month.

export const config = {
  runtime: "edge",
};

const ALLOWED_HOSTS = [
  "allanime.day", "allmanga.to", "allanime.uns.bio", "youtu-chan.com",
  "tools.fast4speed.rsvp", "fast4speed.rsvp", "megacloud.tv", "vixcloud.co",
  "mp4upload.com", "bysekoze.com", "vidnest.io", "ok.ru",
  "repackager.wixmp.com", "allanimenews.com", "sharepoint.com", "wixmp.com",
  "kwik.cx", "kwik.si", "streamwish.to", "megaplay.buzz", "flixcloud.cc",
];

function isAllowedHost(urlStr) {
  try {
    const u = new URL(urlStr);
    const host = u.hostname.toLowerCase();
    return ALLOWED_HOSTS.some((h) => host === h || host.endsWith("." + h));
  } catch (e) {
    return false;
  }
}

const FORWARD_RESPONSE_HEADERS = [
  "content-type", "content-length", "content-range",
  "accept-ranges", "cache-control", "etag", "last-modified",
];
const FORWARD_REQUEST_HEADERS = ["range", "if-range", "if-modified-since"];
const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "range, content-type, if-range, if-modified-since",
  "access-control-expose-headers": "content-length, content-range, content-type",
};

function jsonError(message, status) {
  return new Response(JSON.stringify({ error: message }), {
    status: status || 400,
    headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
  });
}

export default async function handler(request) {
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "range, content-type, if-range, if-modified-since",
        "access-control-max-age": "86400",
      },
    });
  }

  if (request.method !== "GET" && request.method !== "POST") {
    return jsonError("Method not allowed - use GET or POST", 405);
  }

  const target = url.searchParams.get("url");
  if (!target) {
    return new Response(JSON.stringify({
      ok: true, service: "sni-stream-proxy", version: 3,
      message: "SNI proxy. Pass ?url=<target_url> to proxy a GET or POST.",
    }), {
      status: 200,
      headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
    });
  }

  if (!isAllowedHost(target)) {
    let host = "invalid-url";
    try { host = new URL(target).hostname; } catch (e) {}
    return jsonError("Host not allowed: " + host, 403);
  }

  const customHeaders = {};
  url.searchParams.forEach((v, k) => {
    if (k.indexOf("h_") === 0) customHeaders[k.slice(2)] = v;
  });

  const upstreamHeaders = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    Accept: "*/*",
  };
  Object.keys(customHeaders).forEach((k) => { upstreamHeaders[k] = customHeaders[k]; });
  for (const h of FORWARD_REQUEST_HEADERS) {
    const v = request.headers.get(h);
    if (v) upstreamHeaders[h] = v;
  }

  let bodyToSend = undefined;
  if (request.method === "POST") {
    const ct = request.headers.get("content-type");
    if (ct) upstreamHeaders["Content-Type"] = ct;
    bodyToSend = await request.text();
  }

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: upstreamHeaders,
      body: bodyToSend,
      redirect: "follow",
    });

    const respHeaders = new Headers(CORS_HEADERS);
    for (const h of FORWARD_RESPONSE_HEADERS) {
      const v = upstream.headers.get(h);
      if (v) respHeaders.set(h, v);
    }

    const contentType = upstream.headers.get("content-type") || "";
    const urlLower = target.toLowerCase();
    if ((contentType.indexOf("octet-stream") >= 0 || !contentType) &&
        (urlLower.indexOf(".mp4") >= 0 || urlLower.indexOf("/media") >= 0)) {
      respHeaders.set("content-type", "video/mp4");
    }

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (err) {
    return jsonError((err && err.message) || "Unknown proxy error", 502);
  }
}
