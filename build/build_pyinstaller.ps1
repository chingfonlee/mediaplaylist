# build_pyinstaller.ps1
# MediaLauncher PyInstaller one-folder build script
#
# Usage:
#   .\build\build_pyinstaller.ps1
#
# Output:
#   dist\MediaLauncher\MediaLauncher.exe

$ErrorActionPreference = "Stop"

# ── Paths ──────────────────────────────────────────────────────────────
$BUILD_DIR = $PSScriptRoot
$ROOT      = Split-Path -Parent $BUILD_DIR

Set-Location $ROOT
Write-Host "Project root: $ROOT"

# ── 1. Verify launcher.py exists ───────────────────────────────────────
if (-not (Test-Path "launcher.py")) {
    Write-Error "launcher.py not found at: $ROOT\launcher.py"
    exit 1
}
Write-Host "[1/7] launcher.py found"

# ── 2. Verify Python is available ──────────────────────────────────────
try {
    $pyVersion = python --version 2>&1
    Write-Host "[2/7] Python: $pyVersion"
} catch {
    Write-Error "python command not found. Please install Python 3.10+."
    exit 1
}

# ── 3. Create .venv if missing ──────────────────────────────────────────
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[3/7] Creating virtual environment .venv ..."
    python -m venv .venv
} else {
    Write-Host "[3/7] .venv already exists, skipping"
}

$VENV_PY  = "$ROOT\.venv\Scripts\python.exe"
$VENV_PIP = "$ROOT\.venv\Scripts\pip.exe"

# ── 4. Upgrade pip ─────────────────────────────────────────────────────
Write-Host "[4/7] Upgrading pip ..."
& $VENV_PY -m pip install --upgrade pip --quiet
if (-not $?) { Write-Warning "pip upgrade failed, continuing..." }

# ── 5. Install build dependencies ──────────────────────────────────────
Write-Host "[5/7] Installing dependencies (pillow, pymupdf, pyinstaller) ..."
& $VENV_PIP install pillow pymupdf pyinstaller --quiet
if (-not $?) {
    Write-Error "Package install failed. Check network connection."
    exit 1
}

$pi_version = & $VENV_PY -c "import PyInstaller; print(PyInstaller.__version__)"
Write-Host "      PyInstaller $pi_version"

# ── 6. Clean old PyInstaller output ────────────────────────────────────
# Only removes PyInstaller artifacts; never touches config.json/tasks.json/launcher.py
Write-Host "[6/7] Cleaning old build artifacts ..."

$DIST_DIR = "$ROOT\dist\MediaLauncher"
$WORK_DIR = "$ROOT\build\_pyinstaller_work"

if (Test-Path $DIST_DIR) {
    Remove-Item -Recurse -Force $DIST_DIR
    Write-Host "      Removed dist\MediaLauncher\"
}
if (Test-Path $WORK_DIR) {
    Remove-Item -Recurse -Force $WORK_DIR
    Write-Host "      Removed build\_pyinstaller_work\"
}

# Safety check: warn if protected files are missing (not deleted by us)
$PROTECTED = @("config.json", "tasks.json", "launcher.py")
foreach ($f in $PROTECTED) {
    if (-not (Test-Path "$ROOT\$f")) {
        Write-Warning "$f not found (optional at build time; app creates it on first run)"
    }
}

# ── 7. Run PyInstaller ─────────────────────────────────────────────────
Write-Host "[7/7] Running PyInstaller ..."
Write-Host "      Spec: build\MediaLauncher.spec"

& $VENV_PY -m PyInstaller `
    "build\MediaLauncher.spec" `
    --noconfirm `
    --workpath "build\_pyinstaller_work" `
    --distpath "dist"

# ── Result ─────────────────────────────────────────────────────────────
$EXE_PATH = "$ROOT\dist\MediaLauncher\MediaLauncher.exe"

if (Test-Path $EXE_PATH) {
    $size = [math]::Round((Get-Item $EXE_PATH).Length / 1MB, 1)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host " Build succeeded!" -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host " exe : $EXE_PATH ($size MB)"

    # In PyInstaller 6.x one-folder mode, datas land in _internal/ rather than dist root
    $ffmpegInDist = "$ROOT\dist\MediaLauncher\_internal\tools\ffmpeg.exe"
    if (Test-Path $ffmpegInDist) {
        $ffSize = [math]::Round((Get-Item $ffmpegInDist).Length / 1MB, 1)
        Write-Host " ffmpeg : dist\MediaLauncher\_internal\tools\ffmpeg.exe ($ffSize MB) included" -ForegroundColor Green
    } else {
        Write-Host " ffmpeg : not included (video thumbnails unavailable; add tools\ffmpeg.exe later)" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Test the exe:  dist\MediaLauncher\MediaLauncher.exe"
    Write-Host "  2. Verify %APPDATA%\MediaLauncher\ is created on first run"
    Write-Host "  3. Browser should open http://localhost:8765 automatically"
    Write-Host "  4. To test fresh first-run:"
    Write-Host '       Remove-Item -Recurse "$env:APPDATA\MediaLauncher"'
    Write-Host "  5. To suppress console window (release build):"
    Write-Host "       Edit build\MediaLauncher.spec: console=True -> console=False"
    Write-Host "       Re-run this script"
    Write-Host "================================================================"
} else {
    Write-Error "Build failed: $EXE_PATH not found"
    Write-Host "Check PyInstaller output above for error details."
    exit 1
}
