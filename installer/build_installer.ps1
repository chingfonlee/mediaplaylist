# build_installer.ps1
# MediaLauncher Inno Setup compiler script
#
# Prerequisites:
#   1. Run .\build\build_pyinstaller.ps1 first to produce dist\MediaLauncher\MediaLauncher.exe
#   2. Install Inno Setup 6 (https://jrsoftware.org/isinfo.php)
#
# Usage (run from any directory):
#   .\installer\build_installer.ps1
#
# Output:
#   installer\MediaLauncherSetup.exe

$ErrorActionPreference = "Stop"

# ── Paths ──────────────────────────────────────────────────────────────
$INSTALLER_DIR = $PSScriptRoot
$ROOT          = Split-Path -Parent $INSTALLER_DIR
$ISS_FILE      = "$INSTALLER_DIR\MediaLauncher.iss"
$OUTPUT_EXE    = "$INSTALLER_DIR\MediaLauncherSetup.exe"
$DIST_EXE      = "$ROOT\dist\MediaLauncher\MediaLauncher.exe"

Set-Location $ROOT
Write-Host "Project root: $ROOT"

# ── 1. Verify dist exe exists ──────────────────────────────────────────
Write-Host ""
Write-Host "[1/4] Checking PyInstaller output..."
if (-not (Test-Path $DIST_EXE)) {
    Write-Host ""
    Write-Host "ERROR: dist\MediaLauncher\MediaLauncher.exe not found" -ForegroundColor Red
    Write-Host "Run PyInstaller build first:" -ForegroundColor Yellow
    Write-Host "  .\build\build_pyinstaller.ps1"
    exit 1
}
$distSize = [math]::Round((Get-Item $DIST_EXE).Length / 1MB, 1)
Write-Host "      dist\MediaLauncher\MediaLauncher.exe ($distSize MB) OK"

$distFileCount = (Get-ChildItem "$ROOT\dist\MediaLauncher" -Recurse -File).Count
Write-Host "      dist\MediaLauncher\ contains $distFileCount files"

# ── 2. Verify .iss script exists ───────────────────────────────────────
Write-Host "[2/4] Checking installer script..."
if (-not (Test-Path $ISS_FILE)) {
    Write-Error "Not found: $ISS_FILE"
    exit 1
}
Write-Host "      installer\MediaLauncher.iss OK"

# ── 3. Locate Inno Setup ISCC.exe ──────────────────────────────────────
Write-Host "[3/4] Locating Inno Setup 6 (ISCC.exe)..."

$ISCC = $null
$ISCC_CANDIDATES = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\Compil32.exe"
)

foreach ($candidate in $ISCC_CANDIDATES) {
    if (Test-Path $candidate) {
        $ISCC = $candidate
        break
    }
}

if (-not $ISCC) {
    try {
        $isccFromPath = (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue).Source
        if ($isccFromPath) { $ISCC = $isccFromPath }
    } catch {}
}

if (-not $ISCC) {
    Write-Host ""
    Write-Host "Inno Setup 6 (ISCC.exe) not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Choose one of:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option A: Install Inno Setup 6"
    Write-Host "    Download: https://jrsoftware.org/isdl.php"
    Write-Host "    Then re-run this script"
    Write-Host ""
    Write-Host "  Option B: Specify path manually"
    Write-Host '    Add at top of build_installer.ps1:'
    Write-Host '    $ISCC = "C:\your\path\ISCC.exe"'
    Write-Host ""
    Write-Host "  Option C: Compile via GUI"
    Write-Host "    Open Inno Setup -> File -> Open -> installer\MediaLauncher.iss"
    Write-Host "    Press Build -> Compile (Ctrl+F9)"
    exit 1
}

Write-Host "      ISCC.exe: $ISCC OK"

# ── 4. Compile ─────────────────────────────────────────────────────────
Write-Host "[4/4] Compiling installer..."
Write-Host "      Input:  installer\MediaLauncher.iss"
Write-Host "      Output: installer\MediaLauncherSetup.exe"
Write-Host ""

if (Test-Path $OUTPUT_EXE) {
    Remove-Item -Force $OUTPUT_EXE
}

& $ISCC $ISS_FILE

# ── Result ─────────────────────────────────────────────────────────────
if (Test-Path $OUTPUT_EXE) {
    $setupSize = [math]::Round((Get-Item $OUTPUT_EXE).Length / 1MB, 1)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host " Installer compiled successfully!" -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host " Output: $OUTPUT_EXE ($setupSize MB)"
    Write-Host ""
    Write-Host "Test on a machine without Python:"
    Write-Host "  1. Copy installer\MediaLauncherSetup.exe to target machine"
    Write-Host "  2. Double-click; no admin rights required"
    Write-Host "  3. Program installs to: %LOCALAPPDATA%\MediaLauncher\MediaLauncher.exe"
    Write-Host "  4. User data stored at: %APPDATA%\MediaLauncher\"
    Write-Host ""
    Write-Host "USB offline deployment:"
    Write-Host "  Copy installer\MediaLauncherSetup.exe to USB drive"
    Write-Host "================================================================"
} else {
    Write-Error "Installer compilation failed: $OUTPUT_EXE not found"
    Write-Host "Check ISCC output above for error details."
    exit 1
}
