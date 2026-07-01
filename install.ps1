# SNI — Stream Ninja Interface — installer for Windows
#
# Usage:
#   .\install.ps1
#   iex (irm https://raw.githubusercontent.com/sundeepyt2/SNI/main/install.ps1)
#
# What it does:
#   1. Detects winget / scoop / choco (in that order)
#   2. Installs Python 3.10+, mpv, fzf (skips if already present)
#   3. pip install . (the SNI package itself)
#   4. Adds Python Scripts\ dir to user PATH via [Environment]::SetEnvironmentVariable (idempotent)
#   5. Refreshes PATH in the current session
#   6. Verifies `sni --version` works
#
# Re-running is safe — every step is idempotent.

#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# ─── Helpers ───────────────────────────────────────────────────────────────
function Write-Step  { param([string]$msg) Write-Host "» $msg" -ForegroundColor Blue }
function Write-OK    { param([string]$msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn2 { param([string]$msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Err2  { param([string]$msg) Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Sect  { param([string]$msg) Write-Host ""; Write-Host "──[ $msg ]──" -ForegroundColor Cyan }
function Exit-Error  { param([string]$msg)
    Write-Err2 $msg
    exit 1
}

# ─── Header ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  SNI — Stream Ninja Interface — Windows Installer" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""

# ─── Detect SNI source dir ────────────────────────────────────────────────
# If running via iex (no local file), clone the repo first.
$SniDir = $null
if (Test-Path "pyproject.toml") {
    $SniDir = (Get-Location).Path
} elseif ($MyInvocation.MyCommand.Path) {
    $SniDir = Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    # Piped via iex — clone to a temp dir
    Write-Sect "Cloning SNI repository"
    $SniDir = Join-Path $env:TEMP "sni-install-$(Get-Random)"
    git clone --depth 1 https://github.com/sundeepyt2/SNI.git $SniDir
    if (-not $?) { Exit-Error "git clone failed" }
}

if (-not (Test-Path (Join-Path $SniDir "pyproject.toml"))) {
    Exit-Error "pyproject.toml not found in $SniDir. Make sure you're running this from the SNI repo root."
}

Set-Location $SniDir
Write-Step "SNI source: $SniDir"

# ─── Detect package manager (winget > scoop > choco) ──────────────────────
Write-Sect "Step 1/4 — System dependencies (Python 3.10+, mpv, fzf)"

function Get-CommandSafe { param([string]$name)
    try { Get-Command $name -ErrorAction Stop } catch { $null }
}

$PkgMgr = $null
if (Get-CommandSafe winget) {
    $PkgMgr = "winget"
} elseif (Get-CommandSafe scoop) {
    $PkgMgr = "scoop"
} elseif (Get-CommandSafe choco) {
    $PkgMgr = "choco"
} else {
    Write-Warn2 "No package manager found (winget / scoop / choco)."
    Write-Warn2 "I'll try to install anyway, but you may need to install Python, mpv, fzf manually."

    # Try to bootstrap winget (Win11 has it built-in; Win10 1809+ via App Installer)
    Write-Step "Attempting to bootstrap winget..."
    try {
        $wingetPkg = Get-AppxPackage -Name "*WindowsTerminal*" -ErrorAction Stop
        if (-not $wingetPkg) {
            Add-AppxPackage -RegisterByFamilyName -MainPackage "Microsoft.WindowsTerminal_8wekyb3d8bbwe" -ErrorAction Stop
        }
    } catch {
        Write-Warn2 "Could not bootstrap winget automatically."
    }

    if (-not (Get-CommandSafe winget)) {
        Write-Warn2 "winget still unavailable. Falling back to scoop bootstrap..."
        # Bootstrap scoop (user-only, no admin needed)
        try {
            Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
            Invoke-RestMethod -Uri "https://get.scoop.sh" | Invoke-Expression
            $env:Path += ";$env:USERPROFILE\scoop\shims"
        } catch {
            Exit-Error "Could not bootstrap any package manager. Install winget, scoop, or choco manually and re-run."
        }
        if (Get-CommandSafe scoop) { $PkgMgr = "scoop" }
    }
}

Write-Step "Package manager: $PkgMgr"

function Install-Pkg { param([string[]]$pkgs)
    foreach ($pkg in $pkgs) {
        Write-Step "Installing $pkg via $PkgMgr..."
        switch ($PkgMgr) {
            "winget" {
                winget install --id $pkg --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
            }
            "scoop" {
                scoop install $pkg
            }
            "choco" {
                choco install $pkg -y --no-progress
            }
        }
        if (-not $?) { Write-Warn2 "$pkg install reported a failure; will check if it's available anyway." }
    }
}

# Check what's already installed before installing
$pkgsToInstall = @()
if (-not (Get-CommandSafe python))   { $pkgsToInstall += @("Python.Python.3.12", "python") | Select-Object -First 1 }
if (-not (Get-CommandSafe mpv))      { $pkgsToInstall += @("mpv.net", "mpv") | Select-Object -First 1 }
if (-not (Get-CommandSafe fzf))      { $pkgsToInstall += @("junegunn.fzf", "fzf") | Select-Object -First 1 }

if ($pkgsToInstall.Count -gt 0 -and $PkgMgr) {
    # winget uses different IDs than scoop/choco
    if ($PkgMgr -eq "winget") {
        $wingetMap = @{
            "python" = "Python.Python.3.12"
            "mpv"    = "mpv.net"           # mpv.net is a Windows-friendly mpv fork
            "fzf"    = "junegunn.fzf"
        }
        $wingetIds = @()
        foreach ($p in $pkgsToInstall) {
            if ($wingetMap.ContainsKey($p)) { $wingetIds += $wingetMap[$p] }
        }
        if ($wingetIds.Count -gt 0) {
            Write-Step "winget install: $($wingetIds -join ', ')"
            winget install --id $wingetIds --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        }
    } else {
        Install-Pkg $pkgsToInstall
    }
}

# Refresh PATH in this session (winget/scoop/choco just installed may not be on PATH yet)
if ($PkgMgr -eq "scoop") {
    $env:Path += ";$env:USERPROFILE\scoop\shims"
}
if ($PkgMgr -eq "choco") {
    $env:Path += ";$env:ChocolateyInstall\bin"
}

# ─── Step 2: Verify Python ────────────────────────────────────────────────
Write-Sect "Step 2/4 — Verify Python >= 3.10"

$pythonExe = $null
foreach ($cand in @("python", "py", "python3")) {
    $c = Get-CommandSafe $cand
    if ($c) {
        $pythonExe = $c.Source
        break
    }
}

if (-not $pythonExe) {
    Exit-Error "Python not found on PATH. Install Python 3.10+ from https://python.org (check 'Add to PATH'), then re-run this script."
}

# Verify version
$pyVersionOutput = & $pythonExe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>&1
$pyVersion = "$pyVersionOutput".Trim()
$pyParts = $pyVersion.Split(".")
$pyMajor = [int]$pyParts[0]
$pyMinor = [int]$pyParts[1]

if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 10)) {
    Exit-Error "Python $pyVersion found, but SNI requires Python 3.10 or newer. Upgrade from https://python.org and re-run."
}

Write-OK "Python $pyVersion detected ($pythonExe)"

# ─── Step 3: Install SNI ──────────────────────────────────────────────────
Write-Sect "Step 3/4 — Install SNI (pip install)"

# Use --user to avoid touching system Python
Write-Step "pip install --user ."
& $pythonExe -m pip install --user --upgrade pip 2>&1 | Out-Null
& $pythonExe -m pip install --user .
if (-not $?) { Exit-Error "pip install failed. See errors above." }

Write-OK "SNI installed"

# ─── Step 4: PATH injection (idempotent) ──────────────────────────────────
Write-Sect "Step 4/4 — Add SNI to PATH"

# Determine the Python Scripts dir where pip --user installs the sni.exe entry point
$userScriptsDir = & $pythonExe -c "import site, os; print(os.path.join(site.getuserbase(), 'Scripts'))" 2>&1
$userScriptsDir = "$userScriptsDir".Trim()

if (-not (Test-Path $userScriptsDir)) {
    # Fallbacks
    $userScriptsDir = Join-Path $env:APPDATA "Python\Scripts"
}

Write-Step "User Scripts dir: $userScriptsDir"

# Persist to user PATH (idempotent)
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ";" -contains $userScriptsDir) {
    Write-OK "Already in user PATH: $userScriptsDir"
} else {
    $newPath = if ($userPath) { "$userScriptsDir;$userPath" } else { $userScriptsDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-OK "Added to user PATH: $userScriptsDir"
}

# Also make sure it's in this session's PATH so we can verify
if (-not ($env:Path -split ";" -contains $userScriptsDir)) {
    $env:Path = "$userScriptsDir;$env:Path"
}

# ─── Verify ───────────────────────────────────────────────────────────────
Write-Sect "Verification"

$sniCmd = Get-CommandSafe sni
if ($sniCmd) {
    $sniVer = & sni --version 2>&1 | Select-Object -First 1
    Write-OK "SNI is installed: $sniVer"
} else {
    Write-Warn2 "sni not on PATH in this session."
    Write-Warn2 "Open a new PowerShell window, then run:  sni --version"
}

# Optional deps
Write-Host ""
Write-Step "Optional dependencies:"
if (Get-CommandSafe mpv) {
    Write-OK "mpv: available"
} else {
    Write-Warn2 "mpv not found — required for playback. Install via 'winget install mpv.net' or from https://sourceforge.net/projects/mpv-player-windows/"
}
if (Get-CommandSafe fzf) {
    Write-OK "fzf: available"
} else {
    Write-Warn2 "fzf not found — recommended for fuzzy search. SNI will fall back to numbered selection."
}

# ─── Done ─────────────────────────────────────────────────────────────────
Write-Sect "Installation complete"

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host ""
Write-Host "  1. Open a new PowerShell window" -ForegroundColor White
Write-Host "  2. Verify:        sni --version" -ForegroundColor White
Write-Host "  3. Configure:     sni config --interactive" -ForegroundColor White
Write-Host "  4. Search:        sni search 'one piece'" -ForegroundColor White
Write-Host "  5. Play:          sni play 'one piece'" -ForegroundColor White
Write-Host ""
Write-Host "If AllAnime hits a captcha wall, run:" -ForegroundColor Yellow
Write-Host "  sni config --cookie-info" -ForegroundColor White
Write-Host "for the three bypass options (Cloudflare Worker is most reliable)."
Write-Host ""
Write-Host "To launch the full TUI:" -ForegroundColor Green
Write-Host "  sni tui" -ForegroundColor White
Write-Host ""
Write-Host "Happy streaming!" -ForegroundColor Cyan
Write-Host ""
