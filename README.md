# SNI - Stream Ninja Interface

A terminal-based anime streaming client inspired by [ani-cli](https://github.com/pystardust/ani-cli). Search, browse, and stream anime from multiple providers directly in your terminal.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Features

- **Multi-provider support** — HiAnime (sub+ dub), AllAnime (sub+ dub), Animepahe (sub)
- **Full TUI mode** — Rich terminal UI built with Textual
- **Interactive CLI** — fzf-based selection with numbered-input fallback
- **Watch history** — Resume from where you left off
- **Episode queuing** — Play ranges (e.g. `-e 1-12`)
- **mpv/VLC integration** — IPC socket controls (next, prev, reload, quit)
- **Configurable** — TOML config with interactive wizard
- **Cross-platform** — Linux, macOS, Windows

---

## Installation

### Linux

#### Debian / Ubuntu / Mint

```bash
# System dependencies
sudo apt update
sudo apt install python3 python3-pip mpv fzf

# Install SNI
pip install --user sni
```

#### Arch / Manjaro

```bash
# System dependencies
sudo pacman -S python python-pip mpv fzf

# Install SNI
pip install --user sni
```

#### Fedora

```bash
# System dependencies
sudo dnf install python3 python3-pip mpv fzf

# Install SNI
pip install --user sni
```

#### From source (all distros)

```bash
git clone https://github.com/smithmx20/SNI.git
cd SNI
pip install --user .
```

---

### macOS

#### Homebrew

```bash
# System dependencies
brew install mpv fzf

# Install SNI
pip3 install sni
```

#### From source

```bash
git clone https://github.com/smithmx20/SNI.git
cd SNI
pip3 install .
```

---

### Windows

#### pip

```powershell
# Install Python from https://python.org (check "Add to PATH")
# Install mpv from https://sourceforge.net/projects/mpv-player-windows/ and add to PATH
# Install fzf from https://github.com/junegunn/fzf (or via scoop/choco)

pip install sni
```

#### Scoop

```powershell
scoop install mpv fzf
pip install sni
```

#### Chocolatey

```powershell
choco install mpv fzf
pip install sni
```

#### winget

```powershell
winget install mpv fzf
pip install sni
```

#### From source

```powershell
git clone https://github.com/smithmx20/SNI.git
cd SNI
pip install .
```

---

## System Dependencies

| Dependency | Required | Purpose | Install |
|------------|----------|---------|---------|
| [mpv](https://mpv.io/) | Yes | Video player | `apt install mpv` / `brew install mpv` |
| [VLC](https://www.videolan.org/) | Alternative | Video player | `apt install vlc` / `brew install vlc` |
| [fzf](https://github.com/junegunn/fzf) | Optional | Fuzzy finder for selection | `apt install fzf` / `brew install fzf` |
| [chafa](https://github.com/atierian/chafa) | Optional | ASCII thumbnails in TUI | `apt install chafa` / `brew install chafa` |

---

## Usage

```bash
# Search and play (interactive)
sni play "one piece"

# Watch with ani-cli like flow
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

## Providers

| Provider | Sub | Dub | Status |
|----------|-----|-----|--------|
| HiAnime | Yes | Yes | Active |
| AllAnime | Yes | Yes | Active |
| Animepahe | Yes | No | API deprecated |

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
| `sni provider list` | List available providers |
| `sni provider status` | Health-check providers |

---

## Configuration

Config file: `~/.config/sni/config.toml`

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

## Troubleshooting

### AllAnime "NEED_CAPTCHA" Error

AllAnime may require browser cookies to bypass captcha:

```bash
sni play "anime" --cookie 'cookie1=val1; cookie2=val2'
```

1. Open https://allanime.day in your browser
2. Open DevTools -> Application -> Cookies
3. Copy the cookie string and pass it with `--cookie`

### mpv not found

Make sure mpv is installed and in your `PATH`:

```bash
# Linux
sudo apt install mpv

# macOS
brew install mpv

# Windows - add mpv directory to PATH
```

### fzf not found

fzf is optional. If not installed, SNI falls back to numbered selection.

```bash
# Linux
sudo apt install fzf

# macOS
brew install fzf
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
