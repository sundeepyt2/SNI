# SNI — Stream Ninja Interface

A terminal-based anime streaming client inspired by [ani-cli](https://github.com/pystardust/ani-cli). Search, browse, and stream anime from multiple providers directly in your terminal.

[![PyPI version](https://badge.fury.io/py/sni-cli.svg)](https://pypi.org/project/sni-cli/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](#installation)
[![CI](https://github.com/sundeepyt2/SNI/actions/workflows/test.yml/badge.svg)](https://github.com/sundeepyt2/SNI/actions/workflows/test.yml)
[![GitHub release](https://img.shields.io/github/v/release/sundeepyt2/SNI.svg)](https://github.com/sundeepyt2/SNI/releases/latest)

---

## Features

- **Multi-mirror AllAnime support** — auto-tries api.allanime.day + api.allmanga.to on captcha
- **Full TUI mode** — Rich terminal UI built with Textual
- **Interactive CLI** — fzf-based selection with numbered-input fallback
- **Watch history** — Resume from where you left off
- **Episode queuing** — Play ranges (e.g. `sni play "X" -e 1-12`)
- **mpv/VLC integration** — IPC socket controls (next, prev, reload, quit)
- **Captcha-bypass built-in** — Cloudflare Worker fallback + browser-cookie injection for AllAnime
- **Configurable** — TOML config with interactive wizard
- **Cross-platform** — Linux, macOS, Windows

---

## Installation

### One-command install

Pick the command for your OS, paste it into a terminal, and you're done. The installer detects your package manager, installs Python + mpv + fzf if missing, installs SNI, and adds `sni` to your PATH automatically — no manual steps required.

#### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/sundeepyt2/SNI/main/install.sh | bash
```

#### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/sundeepyt2/SNI/main/install.sh | bash
```

(Homebrew will be bootstrapped automatically if missing.)

#### Windows (PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/sundeepyt2/SNI/main/install.ps1)
```

If PowerShell blocks the script with an execution-policy error, run this first:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then re-run the install command.

---

### Install from PyPI

Once SNI is published to PyPI (after the v1.1.1 release), you can install it with plain pip — no cloning required:

```bash
# Linux / macOS
pip install --user sni-cli

# Windows
pip install sni-cli
```

> **Why `sni-cli` and not `sni`?** PyPI rejected the bare `sni` name as too similar to existing projects (`sni-auth`, `sni-bin`, `sni-sdk`, `snib`, `snic`, `snid`, ...). The package name on PyPI is `sni-cli`, but the console command is still just `sni` (e.g. `sni play`, `sni tui`, `sni search`).

This installs the SNI Python package and the `sni` command, but **does not** install `mpv` or `fzf` — install those separately if you don't have them already:

- **Linux**: `sudo apt install mpv fzf` (or your distro's equivalent)
- **macOS**: `brew install mpv fzf`
- **Windows**: `winget install mpv.net junegunn.fzf`

For a fully-automatic install (including mpv + fzf), use the one-command installers above instead.

---

### Install from a local clone

If you've already cloned the repo (or want to hack on SNI), run the installer from the repo root:

```bash
git clone https://github.com/sundeepyt2/SNI.git
cd SNI

# Linux / macOS:
./install.sh

# Windows PowerShell:
.\install.ps1
```

---

### What the installer does

Both `install.sh` and `install.ps1` perform the same four steps:

1. **Detects your package manager** and installs system dependencies:
   - Linux: `apt` / `dnf` / `pacman` / `zypper` / `apk` — installs `python3`, `python3-pip`, `mpv`, `fzf`, `git`
   - macOS: Homebrew — installs `python@3.12`, `mpv`, `fzf`
   - Windows: `winget` / `scoop` / `choco` (auto-detected) — installs Python, mpv.net, fzf
2. **Verifies Python >= 3.10**
3. **Installs SNI itself** via `pip install --user .` (no admin/sudo needed)
4. **Adds SNI to your PATH** idempotently:
   - Linux/macOS: injects an `export PATH=...` line into your `~/.bashrc` / `~/.zshrc` / `~/.profile` / `~/.config/fish/config.fish` (whichever is appropriate for your shell)
   - Windows: calls `[Environment]::SetEnvironmentVariable("Path", ..., "User")` to persist across reboots

The installer is **idempotent** — safe to re-run as many times as you want. It will skip packages that are already installed and won't add duplicate PATH entries.

---

### Manual install (alternative)

If you prefer to install everything by hand:

#### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install python3 python3-pip mpv fzf git

git clone https://github.com/sundeepyt2/SNI.git
cd SNI
pip install --user --break-system-packages .

# Add ~/.local/bin to PATH (one-time)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

sni --version
```

#### macOS

```bash
brew install python@3.12 mpv fzf git

git clone https://github.com/sundeepyt2/SNI.git
cd SNI
pip3 install --user .

# Add ~/Library/Python/3.12/bin to PATH (one-time)
echo 'export PATH="$HOME/Library/Python/3.12/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

sni --version
```

#### Windows

```powershell
# Install Python from https://python.org (check "Add to PATH")
# Install mpv from https://sourceforge.net/projects/mpv-player-windows/
# Install fzf from https://github.com/junegunn/fzf/releases

git clone https://github.com/sundeepyt2/SNI.git
cd SNI
pip install .

sni --version
```

---

## First-run setup

After installing, run the interactive config wizard to pick your default provider, quality, sub/dub, etc:

```bash
sni config --interactive
```

Or just start using SNI directly — sensible defaults are baked in.

---

## Usage

```bash
# Search and play (interactive)
sni play "one piece"

# Watch with ani-cli like flow (continue/resume support)
sni watch "naruto"

# Play specific episode range
sni play "attack on titan" -e 1-12

# Use a specific provider
sni play "jujutsu kaisen" -p allanime

# Watch dubbed
sni play "demon slayer" -d

# Resume from watch history
sni watch --resume

# Search only
sni search "spy x family"

# Launch full TUI
sni tui

# Configure
sni config --interactive
sni config --update quality=720
sni config --update default_provider=allanime
```

---

## Commands

| Command | Description |
|---------|-------------|
| `sni search <query>` | Search for anime titles |
| `sni play <query>` | Search and play with interactive flow |
| `sni watch <query>` | Watch with continue/resume support |
| `sni tui` | Launch full terminal UI |
| `sni config` | Manage configuration |
| `sni config --interactive` | Interactive config wizard |
| `sni config --cookie-info` | Show how to bypass AllAnime captcha (3 options) |
| `sni provider list` | List available providers |
| `sni provider status` | Health-check providers |

---

## Providers

| Provider | Sub | Dub | Status |
|----------|-----|-----|--------|
| AllAnime | Yes | Yes | Active (with multi-mirror auto-fallback) |

> **Note:** HiAnime and Animepahe providers were removed in v1.2.0 — both were dead (hianime.to domain gone, animepahe API deprecated). AllAnime is now the only provider, but it auto-tries multiple API mirrors (api.allanime.day + api.allmanga.to) on captcha, so most users never see a captcha error.

---

## Configuration

Config file: `~/.config/sni/config.toml` (Linux/macOS) or `%APPDATA%\sni\config.toml` (Windows)

```toml
[general]
default_provider = "allanime"
selector = "fzf"
icons = true

[stream]
player = "mpv"
quality = "1080"
translation_type = "sub"
auto_next = true
use_ipc = true

[ui]
show_description = true
show_score = true
show_genres = true

[providers]
allanime_cookies = ""
allanime_cf_worker_url = ""
```

Run `sni config --interactive` to set up via a guided wizard.

---

## TUI Mode

Launch the full terminal UI with:

```bash
sni tui
```

### Keybinds

| Key | Action |
|-----|--------|
| `/` | Focus search input |
| `j` / `k` | Navigate up/down |
| `Enter` | Select / Play |
| `Escape` | Go back / Close |
| `?` | Show help |
| `!` | Player controls |
| `@` | Watch history |
| `$` | About |
| `q` | Quit |

---

## AllAnime captcha fix

**First: you probably don't need any of this.** SNI now automatically tries multiple AllAnime API mirrors (`api.allanime.day` + `api.allmanga.to`) before giving up. Most users can just run `sni play "one piece"` directly and it works — if one mirror is captcha-walled, SNI silently falls back to the other.

If you DO hit a `NEED_CAPTCHA` error (all mirrors failed), try these in order. Run `sni config --cookie-info` to see all options in a single panel.

### Option 1 — Browser cookies (if your IP isn't permanently flagged)

Get cookies from a **working AllAnime mirror** — NOT `allanime.day` (which is currently broken with a redirect loop, see [Troubleshooting](#allanimeday-says-too-many-redirects)). Working mirrors include:

- https://allmanga.to
- https://allanime.uns.bio

Open one in your browser, solve any captcha, then copy the cookie string from DevTools → Application → Cookies. Save it:

```bash
# Option A — config key:
sni config --update allanime_cookies='cf_clearance=...;'

# Option B — cookies file (easier to refresh):
echo 'cf_clearance=...;' > ~/.config/sni/allanime_cookies.txt

# Option C — one-off flag:
sni play "one piece" --cookie 'cf_clearance=...;'
```

### Option 2 — Cloudflare Worker (only for VPN/shared IPs that are permanently captcha-walled AND cookies don't work)

This is the most powerful bypass — it proxies AllAnime API requests through Cloudflare's own IPs, which AllAnime rarely challenges. Only set this up if Option 1 fails.

**Deploy via Cloudflare** (free, requires a Cloudflare account):

1. Go to https://dash.cloudflare.com → Workers & Pages → Create
2. Paste the contents of [`cf-worker/worker.js`](https://github.com/smithmx20/XAN/blob/main/cf-worker/worker.js) from the XAN repo
3. Deploy, copy the worker URL (e.g. `https://xan-proxy.you.workers.dev`)
4. Save it to SNI:

   ```bash
   sni config --update allanime_cf_worker_url='https://xan-proxy.you.workers.dev'
   ```

**Can't create a Cloudflare account?** Deploy the same `worker.js` code to any of these alternative platforms (all have free tiers, none require a credit card):

- **Deno Deploy** (https://dash.deno.com) — free, no card required, fastest setup. Wrap the worker's `fetch` handler in a `Deno.serve()` call.
- **Vercel Edge Functions** (https://vercel.com) — free tier. Adapt the handler to Vercel's `export default function handler(req: Request)` signature.
- **Netlify Functions** (https://netlify.com) — free tier. Convert to Netlify's `exports.handler` format.

The worker code is platform-agnostic — it's just a `fetch` handler that proxies a request. The only thing that changes between platforms is the entry-point wrapper.

---

## Troubleshooting

### `sni: command not found` after install

The installer added SNI to your PATH, but your current shell session hasn't picked it up yet. Fix:

- **Linux/macOS**: open a new terminal, or run `source ~/.bashrc` (or `source ~/.zshrc`)
- **Windows**: open a new PowerShell window

Verify with `sni --version`.

### `mpv not found`

SNI needs a video player to actually play streams. Install mpv:

- **Linux**: `sudo apt install mpv` / `sudo dnf install mpv` / `sudo pacman -S mpv`
- **macOS**: `brew install mpv`
- **Windows**: `winget install mpv.net` or download from https://sourceforge.net/projects/mpv-player-windows/

### `fzf not found`

fzf is optional — SNI falls back to numbered selection if it's missing. To install:

- **Linux**: `sudo apt install fzf` / `sudo dnf install fzf` / `sudo pacman -S fzf`
- **macOS**: `brew install fzf`
- **Windows**: `winget install junegunn.fzf`

### `allanime.day` says "too many redirects"

This is a **server-side bug on AllAnime's website** — not a problem with your browser, your cookies, or SNI. As of July 2026, `https://allanime.day` returns `Location: https://allanime.day//` (note the double slash), which redirects to itself infinitely. It affects everyone globally.

**You don't need to visit allanime.day to use SNI.** SNI only talks to `api.allanime.day` (the API endpoint), which is independent of the broken website and is working normally.

If you need to grab browser cookies for the [captcha bypass](#allanime-captcha-fix), use a **working mirror** instead:

- https://allmanga.to
- https://allanime.uns.bio

If you just want to watch anime, skip the website entirely and run `sni play "one piece"` directly.

### AllAnime `NEED_CAPTCHA` error

SNI v1.2.0+ automatically tries multiple AllAnime API mirrors before giving up. If you still see this error, all mirrors failed. See the [AllAnime captcha fix](#allanime-captcha-fix) section above. TL;DR in order of preference:

1. **Browser cookies** from a working mirror: `sni config --update allanime_cookies='cf_clearance=...;'`
2. **CF Worker** (only for VPN/shared IPs): deploy the worker and `sni config --update allanime_cf_worker_url='https://...'`

### Python version too old

SNI requires Python 3.10 or newer. Check your version with `python3 --version`. If it's older:

- **Linux**: install `python3.12` from your package manager (Debian Backports, Ubuntu deadsnakes PPA, etc.)
- **macOS**: `brew install python@3.12`
- **Windows**: download from https://python.org

### `pip install` fails with "externally-managed-environment"

This happens on Debian 12+ / Fedora 38+ / PEP 668 systems. The installer handles it automatically with `--break-system-packages`. If you're installing manually:

```bash
pip install --user --break-system-packages .
```

Or, better, use a virtualenv:

```bash
python3 -m venv ~/.venvs/sni
source ~/.venvs/sni/bin/activate
pip install .
sni --version
```

---

## Uninstall

```bash
# Remove the Python package
pip uninstall sni-cli   # Linux/macOS
pip uninstall sni-cli   # Windows

# Remove config + cookies
rm -rf ~/.config/sni                    # Linux/macOS
Remove-Item -Recurse $env:APPDATA\sni   # Windows

# Remove PATH entries (search for "sni-path-inject" in your shell rc files)
# Linux/macOS: edit ~/.bashrc / ~/.zshrc / ~/.profile and delete the marked lines
# Windows: System Properties → Environment Variables → edit user Path
```

---

## Development

```bash
git clone https://github.com/sundeepyt2/SNI.git
cd SNI
pip install --user -e ".[test]"

# Run tests
pytest -q

# Lint
ruff check .
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
