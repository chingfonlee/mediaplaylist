# MediaLauncher.spec
# PyInstaller one-folder build specification
#
# Usage (run from project root):
#   .venv\Scripts\python -m PyInstaller build\MediaLauncher.spec --noconfirm
#
# Or use the helper script:
#   .\build\build_pyinstaller.ps1
#
# Target: dist\MediaLauncher\MediaLauncher.exe (one-folder, NOT one-file)
#
# Compatibility: PyInstaller 5.x / 6.x
#   5.x uses cipher=None; 6.x removed cipher. The conditional below handles both.

from pathlib import Path

# SPECPATH is provided by PyInstaller at spec-execution time.
# It is the directory that contains this .spec file (i.e. build/).
ROOT = Path(SPECPATH).parent   # project root (where launcher.py lives)

# ── Detect PyInstaller version for cipher compatibility ────────────────
import PyInstaller as _pi
_pi_major = int(_pi.__version__.split('.')[0])
_cipher_kwarg = {'cipher': None} if _pi_major < 6 else {}

# ── Collect datas ──────────────────────────────────────────────────────
# Each entry: (source_path_str, dest_dir_relative_to_dist_root)
_datas = []

# Default data files — seeded to %APPDATA%\MediaLauncher on first frozen run
# by _init_data_dir() in launcher.py.
for _fname in ('config.json', 'tasks.json'):
    _src = ROOT / _fname
    if _src.exists():
        _datas.append((str(_src), '.'))

# User-facing documentation
for _fname in ('說明.txt', 'third_party_notices.txt'):
    _src = ROOT / _fname
    if _src.exists():
        _datas.append((str(_src), '.'))

# License directory (if present)
_license_dir = ROOT / 'license'
if _license_dir.is_dir():
    _datas.append((str(_license_dir / '*'), 'license'))

# Bundled ffmpeg (optional — video thumbnails won't work without it, but
# the app won't crash; it will just show placeholder icons for video files)
_ffmpeg_src = ROOT / 'tools' / 'ffmpeg.exe'
if _ffmpeg_src.exists():
    _datas.append((str(_ffmpeg_src), 'tools'))

# ── Analysis ───────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'launcher.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # http.server deps — email.utils is used for date header parsing
        'email',
        'email.utils',
        'email.message',
        'email.parser',
        'email.headerregistry',
        # tkinter: used by /api/browse (folder picker dialog)
        'tkinter',
        'tkinter.filedialog',
        'tkinter.ttk',
        # PyMuPDF: used for PDF thumbnail generation
        'fitz',
        'fitz.utils',
        # Pillow: used for image thumbnail generation
        'PIL',
        'PIL.Image',
        'PIL.ImageFile',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.TiffImagePlugin',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy stdlib modules not needed at runtime
    excludes=[
        'unittest', 'pydoc', 'doctest',
        'xmlrpc',
        'distutils', 'lib2to3',
        'test', 'tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
    **_cipher_kwarg,
)

pyz = PYZ(a.pure, a.zipped_data, **_cipher_kwarg)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MediaLauncher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compression reduces size ~30% but can increase AV false-positive rate.
    # Disable with upx=False if antivirus blocks the exe.
    upx=True,
    # Never compress these system DLLs — compressing them increases AV false-positives.
    upx_exclude=['vcruntime140.dll', 'ucrtbase.dll', 'python3*.dll'],
    # console=True keeps the terminal window visible.
    # Recommended during development/testing so users can see errors and Ctrl+C.
    # Change to False before building the final Inno Setup release if a silent
    # background process is preferred.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,   # Replace None with 'icon.ico' if you have an application icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'ucrtbase.dll', 'python3*.dll'],
    name='MediaLauncher',
)
