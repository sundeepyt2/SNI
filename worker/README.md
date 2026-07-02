# SNI Stream Proxy — Self-Hostable Captcha Bypass

This directory contains the proxy worker code that SNI uses as a fallback when your IP is captcha-walled on `api.allanime.day`. The worker is a simple JavaScript `fetch` handler that proxies requests through a clean IP (the platform's IP, not yours), which AllAnime's Cloudflare edge doesn't flag.

## When you need this

You need this **only** if ALL of these are true:

1. `sni play "one piece"` fails with `NEED_CAPTCHA` or `ConnectTimeout`
2. `curl -I https://api.allanime.day` times out or returns 403 from your machine
3. `curl -I https://proxy.cors.sh` also times out (SNI's built-in public proxy fallback doesn't work for you)

If any of those work, you don't need this — SNI's built-in fallbacks already cover you.

## Three deployment options (all free, no credit card required)

Pick **one**. All three run the same JavaScript code (slightly different entry-point wrappers).

| Platform | Free tier | Signup difficulty | Setup time |
|---|---|---|---|
| **Deno Deploy** | 1M req/month | Easy (GitHub login) | ~2 min |
| **Vercel Edge Functions** | 1M req/month | Easy (GitHub login) | ~3 min |
| **Cloudflare Workers** | 100K req/day | Hard right now (deploy bugs) | ~5 min |

**If you can't create a Cloudflare Worker (the Hello World project won't deploy), use Deno Deploy instead — it's the most reliable as of 2026.**

---

## Option 1: Deno Deploy (recommended — most reliable)

**Easiest method — Playground (no GitHub repo needed):**

1. Go to https://dash.deno.com → Sign in with GitHub
2. Click **"New Project"**
3. Click **"Playground"** (top-right corner — IMPORTANT: don't pick "Import from GitHub" or you'll hit the `/tmp/build/src/main.ts` not found error)
4. Delete the default code in the editor
5. Paste the entire contents of [`main.ts`](./main.ts) from this directory
6. Click **"Save & Deploy"**
7. You'll get a URL like `https://your-project.deno.dev` — copy it
8. Test it in your browser: visit `https://your-project.deno.dev/` — you should see `{"ok":true,"service":"sni-stream-proxy",...}`
9. Save it to SNI:

   ```bash
   sni config --update allanime_cf_worker_url='https://your-project.deno.dev'
   ```

10. Try SNI: `sni play "one piece"`

**Alternative method — GitHub repo (if Playground doesn't work for you):**

1. Fork the SNI repo on GitHub
2. Go to https://dash.deno.com → "New Project" → pick your fork
3. Deno Deploy auto-detects `main.ts` (or `deno.json`'s `entrypoint` field) as the entrypoint
4. Click "Link" → "Deploy"
5. Copy the URL, save to SNI as above

**If you see "Entrypoint at '/tmp/build/src/main.ts' not found":** This means you picked "New Project" but Deno Deploy can't find the entrypoint. Fix by either using the Playground (above) or pushing `main.ts` to the root of your GitHub repo (not inside `src/`).

---

## Option 2: Vercel Edge Functions

1. Go to https://vercel.com → Sign in with GitHub
2. Click **"Add New"** → **"Project"**
3. Click **"Create New Project"** → under "No Framework", click **"Browse all templates"** → pick **"Blank"**
4. Name your project, click **"Deploy"** (this creates an empty project)
5. Once deployed, click **"Continue to Dashboard"** → **"Code"** tab → **"Files"** tab
6. Create a new folder called `api` and a file inside it called `proxy.js`
7. Paste the entire contents of [`api/proxy.js`](./api/proxy.js) into that file
8. Click **"Commit"** → **"Commit & Deploy"**
9. Once redeployed, your URL will be `https://your-project.vercel.app/api/proxy` — copy it
10. Test it in your browser: visit `https://your-project.vercel.app/api/proxy` — you should see `{"ok":true,...}`
11. Save it to SNI:

    ```bash
    sni config --update allanime_cf_worker_url='https://your-project.vercel.app/api/proxy'
    ```

12. Try SNI: `sni play "one piece"`

---

## Option 3: Cloudflare Workers

Use this only if Deno Deploy and Vercel both fail for you.

1. Go to https://dash.cloudflare.com → sign up / sign in
2. Left sidebar → **"Workers & Pages"** → **"Create"** → **"Create Worker"**
3. Give it a name (e.g. `sni-proxy`) → click **"Deploy"**
4. Click **"Edit code"** (top-right)
5. Delete the default code, paste the entire contents of [`proxy.js`](./proxy.js) from this directory
6. Click **"Deploy"** (top-right)
7. Your URL will be `https://sni-proxy.<your-subdomain>.workers.dev` — copy it
8. Test it in your browser: visit the URL — you should see `{"ok":true,...}`
9. Save it to SNI:

   ```bash
   sni config --update allanime_cf_worker_url='https://sni-proxy.your-subdomain.workers.dev'
   ```

10. Try SNI: `sni play "one piece"`

**If the "Hello World" project won't deploy:** This is a known Cloudflare dashboard bug. Try:
- Use a different browser (Chrome instead of Firefox, or vice versa)
- Disable ad-blockers / privacy extensions
- Try incognito mode
- Wait 30 minutes and retry (sometimes it's a transient outage)
- **Or just use Deno Deploy instead** (Option 1) — it's more reliable right now

---

## How it works

SNI's `AllAnimeProvider` tries these in order when fetching anime data:

1. **Direct request** to `api.allanime.day` — fastest, works for most users
2. **proxy.cors.sh** (built-in public proxy) — automatic fallback, no setup needed
3. **Your self-hosted worker** (this directory) — last resort, only used if you configured `allanime_cf_worker_url`
4. **CF Worker** (Cloudflare's own IPs) — same as #3, just deployed on Cloudflare specifically

The worker:
- Accepts GET and POST requests
- Proxies them to the target URL with proper headers (Referer, Origin, User-Agent)
- Only allows requests to a hardcoded list of AllAnime-related hosts (security: prevents abuse)
- Streams the response body back (supports large video files)

## Security

The worker has a hardcoded allowlist of hosts it will proxy (`ALLOWED_HOSTS` in the code). It will refuse to proxy requests to any other host. This prevents someone from using your worker as an open proxy for arbitrary traffic.

## Verification

After configuring your worker URL, verify SNI can use it:

```bash
# Should print the version
sni --version

# Should search successfully (using your worker if direct fails)
sni search "one piece"

# Should play successfully
sni play "one piece"
```

If you still get `NEED_CAPTCHA` or `ConnectTimeout`, run `sni config --cookie-info` for more options or open an issue at https://github.com/sundeepyt2/SNI/issues
