# SNI — Stream Ninja Interface

A terminal-based anime streaming client inspired by [ani-cli](https://github.com/pystardust/ani-cli). Search, browse, and stream anime from multiple providers directly in your terminal.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](#installation)

---

## Features

- **Multi-provider support** — HiAnime (sub+dub), AllAnime (sub+dub), Animepahe (sub)
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
| HiAnime | Yes | Yes | Active |
| AllAnime | Yes | Yes | Active |
| Animepahe | Yes | No | API deprecated |

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

AllAnime sometimes blocks API requests with a Cloudflare captcha wall (`NEED_CAPTCHA` error). SNI ships with **three** bypass options. Run `sni config --cookie-info` to see them all in a single panel:

### Option 1 — Cloudflare Worker (recommended, most reliable)

Deploy the XAN CF Worker (free, takes 2 minutes):

1. Go to https://dash.cloudflare.com → Workers & Pages → Create
2. Paste the contents of [`cf-worker/worker.js`](https://github.com/smithmx20/XAN/blob/main/cf-worker/worker.js) from the XAN repo
3. Deploy, copy the worker URL (e.g. `https://xan-proxy.you.workers.dev`)
4. Save it to SNI:

   ```bash
   sni config --update allanime_cf_worker_url='https://xan-proxy.you.workers.dev'
   ```

The Worker proxies AllAnime API requests through Cloudflare's own IPs, which AllAnime rarely challenges. **This works even on VPN/shared IPs where cookies fail.**

### Option 2 — Browser cookies

If your IP isn't already flagged, browser cookies will work:

```bash
# Option A — config key:
sni config --update allanime_cookies='k1=v1; k2=v2'

# Option B — cookies file (easier to refresh):
echo 'k1=v1; k2=v2' > ~/.config/sni/allanime_cookies.txt

# Option C — one-off flag:
sni play "one piece" --cookie 'k1=v1; k2=v2'
```

Get the cookie string from your browser:
1. Open https://allanime.day, solve any captcha.
2. DevTools → Application → Cookies → allanime.day.
3. Copy the full cookie string.

### Option 3 — Switch providers

```bash
sni play "one piece" -p hianime
```

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

### AllAnime `NEED_CAPTCHA` error

See the [AllAnime captcha fix](#allanime-captcha-fix) section above. TL;DR: deploy the Cloudflare Worker and run `sni config --update allanime_cf_worker_url='https://your-worker.workers.dev'`.

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
