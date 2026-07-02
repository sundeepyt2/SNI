// SNI Stream Proxy — Deno Deploy (main.ts)
//
// This is the entrypoint file that Deno Deploy looks for by default.
// Paste this entire file into the Deno Deploy Playground, or push it to
// a GitHub repo as main.ts (or src/main.ts) and connect the repo.
//
// Deploy: https://dash.deno.com -> New Project -> Playground -> paste -> Save & Deploy
// No credit card required. Free tier: 1 million requests/month.
// After publishing, you get a URL like https://your-project.deno.dev
// Save it to SNI: sni config --update allanime_cf_worker_url='https://your-project.deno.dev'

const ALLOWED_HOSTS: string[] = [
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

function isAllowedHost(urlStr: string): boolean {
  try {
    const u = new URL(urlStr);
    const host = u.hostname.toLowerCase();
    return ALLOWED_HOSTS.some((h: string): boolean =>
      host === h || host.endsWith("." + h)
    );
  } catch (_e) {
    return false;
  }
}

function getHost(urlStr: string): string {
  try {
    return new URL(urlStr).hostname;
  } catch (_e) {
    return "invalid-url";
  }
}

const FORWARD_RESPONSE_HEADERS: string[] = [
  "content-type",
  "content-length",
  "content-range",
  "accept-ranges",
  "cache-control",
  "etag",
  "last-modified",
];
const FORWARD_REQUEST_HEADERS: string[] = [
  "range",
  "if-range",
  "if-modified-since",
];
const CORS_HEADERS: Record<string, string> = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers":
    "range, content-type, if-range, if-modified-since",
  "access-control-expose-headers":
    "content-length, content-range, content-type",
};

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status: status || 400,
    headers: {
      "content-type": "application/json",
      "access-control-allow-origin": "*",
    },
  });
}

async function handleRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);

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

  const target: string | null = url.searchParams.get("url");
  if (!target) {
    return new Response(
      JSON.stringify({
        ok: true,
        service: "sni-stream-proxy",
        version: 3,
        message: "SNI proxy. Pass ?url=<target_url> to proxy a GET or POST.",
      }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "access-control-allow-origin": "*",
        },
      },
    );
  }

  if (!isAllowedHost(target)) {
    return jsonError("Host not allowed: " + getHost(target), 403);
  }

  const customHeaders: Record<string, string> = {};
  url.searchParams.forEach(function (v: string, k: string): void {
    if (k.indexOf("h_") === 0) {
      customHeaders[k.slice(2)] = v;
    }
  });

  const upstreamHeaders: Record<string, string> = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "*/*",
  };
  Object.keys(customHeaders).forEach(function (k: string): void {
    upstreamHeaders[k] = customHeaders[k];
  });
  for (let i = 0; i < FORWARD_REQUEST_HEADERS.length; i++) {
    const h: string = FORWARD_REQUEST_HEADERS[i];
    const v: string | null = request.headers.get(h);
    if (v) upstreamHeaders[h] = v;
  }

  let bodyToSend: string | undefined = undefined;
  if (request.method === "POST") {
    const ct: string | null = request.headers.get("content-type");
    if (ct) upstreamHeaders["Content-Type"] = ct;
    bodyToSend = await request.text();
  }

  try {
    const upstream: Response = await fetch(target, {
      method: request.method,
      headers: upstreamHeaders,
      body: bodyToSend,
      redirect: "follow",
    });

    const respHeaders: Headers = new Headers(CORS_HEADERS);
    for (let i = 0; i < FORWARD_RESPONSE_HEADERS.length; i++) {
      const h: string = FORWARD_RESPONSE_HEADERS[i];
      const v: string | null = upstream.headers.get(h);
      if (v) respHeaders.set(h, v);
    }

    const contentType: string = upstream.headers.get("content-type") || "";
    const urlLower: string = target.toLowerCase();
    if (
      (contentType.indexOf("octet-stream") >= 0 || !contentType) &&
      (urlLower.indexOf(".mp4") >= 0 || urlLower.indexOf("/media") >= 0)
    ) {
      respHeaders.set("content-type", "video/mp4");
    }

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (err: unknown) {
    const msg: string = (err instanceof Error && err.message) ||
      "Unknown proxy error";
    return jsonError(msg, 502);
  }
}

Deno.serve(handleRequest);
