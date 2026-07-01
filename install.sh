#!/usr/bin/env bash
# SNI — Stream Ninja Interface — installer for Linux and macOS
#
# Usage:
#   ./install.sh                # install from this checkout
#   bash install.sh             # same, when ./ isn't executable
#   curl -fsSL https://raw.githubusercontent.com/sundeepyt2/SNI/main/install.sh | bash
#
# What it does:
#   1. Detects OS + package manager
#   2. Installs Python 3.10+, mpv, fzf (skips if already present)
#   3. pip install --user . (the SNI package itself)
#   4. Adds the Python user bin dir to PATH via shell rc (idempotent)
#   5. Verifies `sni --version` works
#
# Re-running is safe — every step is idempotent.

set -euo pipefail

# ─── Colors ────────────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4); CYAN=$(tput setaf 6); BOLD=$(tput bold); RESET=$(tput sgr0)
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""; BOLD=""; RESET=""
fi

log()  { echo "${BLUE}»${RESET} $*"; }
ok()   { echo "${GREEN}✓${RESET} ${BOLD}$*${RESET}"; }
warn() { echo "${YELLOW}⚠${RESET} $*"; }
err()  { echo "${RED}✗${RESET} $*" >&2; }
die()  { err "$*"; exit 1; }
section() { echo; echo "${CYAN}${BOLD}──[ $* ]──${RESET}"; }

# ─── OS detection ──────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
    Linux*)  PLATFORM="linux";;
    Darwin*) PLATFORM="macos";;
    *)       die "Unsupported OS: $OS (only Linux and macOS are supported).";;
esac

# When piped via curl, we have no checkout — clone first.
if [ ! -f "pyproject.toml" ]; then
    section "Cloning SNI repository"
    SNI_TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$SNI_TMPDIR"' EXIT
    git clone --depth 1 https://github.com/sundeepyt2/SNI.git "$SNI_TMPDIR/SNI"
    cd "$SNI_TMPDIR/SNI"
fi

section "SNI installer — $PLATFORM ($ARCH)"

# ─── Step 1: package manager + system dependencies ────────────────────────
section "Step 1/4 — System dependencies (Python 3.10+, mpv, fzf)"

have() { command -v "$1" >/dev/null 2>&1; }

if [ "$PLATFORM" = "macos" ]; then
    if ! have brew; then
        warn "Homebrew not found. Installing Homebrew (one time)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
            || die "Homebrew install failed. Install it manually from https://brew.sh"
        # Make brew available in this shell
        if [ -x /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -x /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi
    PKGS_TO_INSTALL=()
    have python3   || PKGS_TO_INSTALL+=(python@3.12)
    have mpv       || PKGS_TO_INSTALL+=(mpv)
    have fzf       || PKGS_TO_INSTALL+=(fzf)
    if [ ${#PKGS_TO_INSTALL[@]} -gt 0 ]; then
        log "brew install: ${PKGS_TO_INSTALL[*]}"
        brew install "${PKGS_TO_INSTALL[@]}" || die "brew install failed"
    fi
    ok "All macOS dependencies present"
else
    # Linux — detect distro
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID="${ID:-}"
        DISTRO_FAMILY="${ID_LIKE:-$DISTRO_ID}"
    else
        DISTRO_ID="unknown"
        DISTRO_FAMILY=""
    fi

    install_pkgs() {
        local mgr="$1"; shift
        local sudo_cmd=""
        if [ "$(id -u)" != "0" ] && have sudo; then
            sudo_cmd="sudo"
        fi
        log "$mgr install: $*"
        case "$mgr" in
            apt)
                $sudo_cmd apt-get update -qq
                $sudo_cmd apt-get install -y "$@"
                ;;
            dnf)
                $sudo_cmd dnf install -y "$@"
                ;;
            yum)
                $sudo_cmd yum install -y "$@"
                ;;
            pacman)
                $sudo_cmd pacman -Sy --noconfirm --needed "$@"
                ;;
            zypper)
                $sudo_cmd zypper install -y "$@"
                ;;
            apk)
                # apk usually doesn't need sudo in containers
                ${sudo_cmd:-} apk add --no-cache "$@"
                ;;
            *)
                die "Unknown package manager: $mgr"
                ;;
        esac
    }

    if echo "$DISTRO_FAMILY" | grep -q debian || [ "$DISTRO_ID" = "debian" ] || [ "$DISTRO_ID" = "ubuntu" ] || [ "$DISTRO_ID" = "linuxmint" ]; then
        PKGS=()
        have python3 || PKGS+=(python3)
        have pip3    || { have python3 && python3 -m pip --version >/dev/null 2>&1 || PKGS+=(python3-pip); }
        have mpv     || PKGS+=(mpv)
        have fzf     || PKGS+=(fzf)
        have git     || PKGS+=(git)
        [ ${#PKGS[@]} -gt 0 ] && install_pkgs apt "${PKGS[@]}"
        ok "Debian/Ubuntu dependencies installed"

    elif echo "$DISTRO_FAMILY" | grep -q fedora || echo "$DISTRO_FAMILY" | grep -q rhel || [ "$DISTRO_ID" = "fedora" ]; then
        PKGS=()
        have python3 || PKGS+=(python3)
        have pip3    || PKGS+=(python3-pip)
        have mpv     || PKGS+=(mpv)
        have fzf     || PKGS+=(fzf)
        have git     || PKGS+=(git)
        [ ${#PKGS[@]} -gt 0 ] && install_pkgs dnf "${PKGS[@]}"
        ok "Fedora/RHEL dependencies installed"

    elif echo "$DISTRO_FAMILY" | grep -q arch || [ "$DISTRO_ID" = "arch" ] || [ "$DISTRO_ID" = "manjaro" ]; then
        PKGS=()
        have python3 || PKGS+=(python)
        have mpv     || PKGS+=(mpv)
        have fzf     || PKGS+=(fzf)
        have git     || PKGS+=(git)
        # pip is bundled with python on Arch
        [ ${#PKGS[@]} -gt 0 ] && install_pkgs pacman "${PKGS[@]}"
        ok "Arch/Manjaro dependencies installed"

    elif echo "$DISTRO_FAMILY" | grep -q suse || [ "$DISTRO_ID" = "opensuse" ] || [ "$DISTRO_ID" = "opensuse-leap" ]; then
        PKGS=()
        have python3 || PKGS+=(python3)
        have pip3    || PKGS+=(python3-pip)
        have mpv     || PKGS+=(mpv)
        have fzf     || PKGS+=(fzf)
        have git     || PKGS+=(git)
        [ ${#PKGS[@]} -gt 0 ] && install_pkgs zypper "${PKGS[@]}"
        ok "openSUSE dependencies installed"

    elif [ "$DISTRO_ID" = "alpine" ]; then
        PKGS=()
        have python3 || PKGS+=(python3)
        have pip3    || PKGS+=(py3-pip)
        have mpv     || PKGS+=(mpv)
        # fzf is in community repo on Alpine
        have fzf     || PKGS+=(fzf)
        have git     || PKGS+=(git)
        [ ${#PKGS[@]} -gt 0 ] && install_pkgs apk "${PKGS[@]}"
        ok "Alpine dependencies installed"

    else
        warn "Unknown distro: $DISTRO_ID ($DISTRO_FAMILY)."
        warn "I'll try to install SNI anyway, but you may need to install python3, mpv, fzf, and git manually."
        have python3 || die "python3 is required but not installed. Please install Python 3.10+ manually and re-run."
    fi
fi

# ─── Step 2: Python version check ─────────────────────────────────────────
section "Step 2/4 — Verify Python >= 3.10"

if ! have python3; then
    die "python3 is not on PATH. Install Python 3.10+ manually and re-run this script."
fi
PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    die "Python $PY_VERSION found, but SNI requires Python 3.10 or newer. Upgrade Python and re-run."
fi
ok "Python $PY_VERSION detected"

# Ensure pip is available; bootstrap if missing
if ! python3 -m pip --version >/dev/null 2>&1; then
    warn "pip not found for python3 — bootstrapping via ensurepip..."
    python3 -m ensurepip --user || die "ensurepip failed. Install python3-pip via your package manager."
fi

# ─── Step 3: Install SNI ──────────────────────────────────────────────────
section "Step 3/4 — Install SNI (pip install)"

# Use --user to avoid needing sudo and to keep system Python clean.
# --break-system-packages is needed on Debian 12+/Fedora/PEP 668 systems
# where pip refuses to touch the system Python.
PIP_FLAGS=(--user)

# Detect EXTERNALLY-MANAGED marker (PEP 668). Can't use [ -f ...glob... ]
# because -f doesn't expand globs (shellcheck SC2144). Use compgen or ls instead.
if [ -d /usr/lib/python3 ] || [ -d /usr/lib/python3.11 ] || [ -d /usr/lib/python3.12 ]; then
    # shellcheck disable=SC2086  # glob needs to expand here
    if ls /usr/lib/python3*/EXTERNALLY-MANAGED >/dev/null 2>&1; then
        PIP_FLAGS+=(--break-system-packages)
    fi
fi

# Check if --user is actually viable (it isn't inside an active virtualenv)
USER_INSTALL_OK=1
python3 -c "import site; site.ENABLE_USER_SITE" 2>/dev/null || USER_INSTALL_OK=0
if [ "$USER_INSTALL_OK" -eq 0 ]; then
    warn "Active virtualenv detected — installing into the venv instead of --user."
    PIP_FLAGS=()
fi

log "pip install ${PIP_FLAGS[*]} . (this may take a minute)"
python3 -m pip install "${PIP_FLAGS[@]}" --upgrade pip >/dev/null 2>&1 || true

# Try the install; if --user fails (e.g. PEP 668 even with the flag, or venv),
# fall back to a plain install which goes into the active venv or system site.
if ! python3 -m pip install "${PIP_FLAGS[@]}" . 2>&1; then
    if [ ${#PIP_FLAGS[@]} -gt 0 ]; then
        warn "pip install --user failed. Retrying without --user..."
        if ! python3 -m pip install . ; then
            die "pip install failed. See errors above."
        fi
    else
        die "pip install failed. See errors above."
    fi
fi

ok "SNI installed"

# ─── Step 4: PATH injection (idempotent) ──────────────────────────────────
section "Step 4/4 — Add SNI to PATH"

# Determine the user bin dir where pip --user installs scripts.
USER_BIN_DIR=$(python3 -c '
import sysconfig, site, os
# Prefer site.getusersitepackages() path derivation
base = site.getuserbase()
print(os.path.join(base, "bin"))
')

if [ -z "$USER_BIN_DIR" ] || [ ! -d "$USER_BIN_DIR" ]; then
    # Fallback: ~/.local/bin on Linux, ~/Library/Python/3.X/bin on macOS
    if [ "$PLATFORM" = "macos" ]; then
        USER_BIN_DIR="$HOME/Library/Python/$PY_VERSION/bin"
    else
        USER_BIN_DIR="$HOME/.local/bin"
    fi
fi

log "User bin dir: $USER_BIN_DIR"

# Make sure the dir exists
mkdir -p "$USER_BIN_DIR"

# Idempotent PATH injection across multiple shell rc files.
# We add a guarded export line that's safe to source multiple times.
PATH_LINE='export PATH="'"$USER_BIN_DIR"':$PATH"'
PATH_MARKER='# sni-path-inject (safe to remove if SNI is uninstalled)'

# Function: add PATH line to a file if not already there
add_to_rc() {
    local rc_file="$1"
    [ -f "$rc_file" ] || touch "$rc_file"
    if grep -qF "$PATH_MARKER" "$rc_file" 2>/dev/null; then
        # Already there — make sure the path is current (in case user moved Python)
        # Use python to safely replace the line
        python3 - "$rc_file" "$USER_BIN_DIR" <<'PY' || true
import sys, re
path, user_bin = sys.argv[1], sys.argv[2]
with open(path) as f:
    content = f.read()
# Replace any existing sni-path-inject block
new_block = f"{sys.argv[2] if False else '# sni-path-inject (safe to remove if SNI is uninstalled)'}\nexport PATH=\"{user_bin}:$PATH\""
content = re.sub(
    r'# sni-path-inject.*?\nexport PATH=.*?(?:\$PATH|"$PATH")\n?',
    new_block + "\n",
    content,
    flags=re.DOTALL,
)
with open(path, 'w') as f:
    f.write(content)
PY
        log "  updated: $rc_file"
    else
        {
            echo ""
            echo "$PATH_MARKER"
            echo "$PATH_LINE"
        } >> "$rc_file"
        log "  added:   $rc_file"
    fi
}

# Choose which rc files to touch based on user's shell
USER_SHELL="${SHELL:-/bin/bash}"
case "$(basename "$USER_SHELL")" in
    zsh)
        add_to_rc "$HOME/.zshrc"
        ;;
    bash)
        add_to_rc "$HOME/.bashrc"
        # Also touch .profile / .bash_profile so login shells get it
        if [ -f "$HOME/.bash_profile" ]; then
            add_to_rc "$HOME/.bash_profile"
        elif [ ! -f "$HOME/.profile" ]; then
            add_to_rc "$HOME/.profile"
        fi
        ;;
    fish)
        # fish uses a different config format
        FISH_CONFIG_DIR="$HOME/.config/fish"
        mkdir -p "$FISH_CONFIG_DIR"
        FISH_RC="$FISH_CONFIG_DIR/config.fish"
        if grep -qF "$PATH_MARKER" "$FISH_RC" 2>/dev/null; then
            log "  already in: $FISH_RC"
        else
            {
                echo ""
                echo "$PATH_MARKER"
                echo "set -gx PATH $USER_BIN_DIR \$PATH"
            } >> "$FISH_RC"
            log "  added:      $FISH_RC"
        fi
        ;;
    *)
        warn "Unknown shell: $USER_SHELL. Adding to ~/.profile as a fallback."
        add_to_rc "$HOME/.profile"
        ;;
esac

# Export for this session so we can verify immediately
export PATH="$USER_BIN_DIR:$PATH"

# ─── Verify ───────────────────────────────────────────────────────────────
section "Verification"

if have sni; then
    SNI_VER=$(sni --version 2>&1 | head -1)
    ok "SNI is installed: $SNI_VER"
else
    warn "sni not on PATH in this shell session."
    warn "Open a new terminal, or run:  source ~/.bashrc  (or ~/.zshrc)"
    warn "Then verify with:  sni --version"
fi

# Optional deps check
echo
log "Optional dependencies:"
if have mpv; then
    ok "mpv: $(mpv --version 2>&1 | head -1)"
else
    warn "mpv not found — required for playback. Install it manually."
fi
if have fzf; then
    ok "fzf: $(fzf --version 2>&1 | head -1)"
else
    warn "fzf not found — recommended for fuzzy search. SNI will fall back to numbered selection."
fi

# ─── Done ─────────────────────────────────────────────────────────────────
section "Installation complete"

cat <<EOF

${GREEN}${BOLD}Next steps:${RESET}

  1. ${BOLD}Open a new terminal${RESET} (or run: source ~/.bashrc  /  source ~/.zshrc)
  2. Verify:        ${BOLD}sni --version${RESET}
  3. Configure:     ${BOLD}sni config --interactive${RESET}
  4. Search:        ${BOLD}sni search "one piece"${RESET}
  5. Play:          ${BOLD}sni play "one piece"${RESET}

If AllAnime hits a captcha wall, run:
  ${BOLD}sni config --cookie-info${RESET}
for the three bypass options (Cloudflare Worker is most reliable).

To launch the full TUI:
  ${BOLD}sni tui${RESET}

${CYAN}Happy streaming!${RESET}
EOF
