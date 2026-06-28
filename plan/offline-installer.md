# 媒體啟動器 — 離線 Windows Installer 規格

> 版本：v1.0　日期：2026-06-26　狀態：草稿
> 目標受眾：執行打包與安裝腳本的 agent / 開發者

---

## 0. 現況摘要（實作前提）

| 項目 | 現況 |
|------|------|
| 主要檔案 | `launcher.py`（單一 Python 檔，HTML/CSS/JS 內嵌） |
| 第三方依賴 | `Pillow`（圖片縮圖）、`PyMuPDF/fitz`（PDF 縮圖） |
| 外部工具 | `ffmpeg`（影片縮圖），目前直接以 `'ffmpeg'` 呼叫（依賴 PATH） |
| 路徑解析 | `SCRIPT = Path(__file__).parent`（**PyInstaller 下需修改**） |
| 使用者資料 | `config.json`、`tasks.json`、`.thumbs/` 全部在 `SCRIPT/` 同層（**Program Files 無法寫入**） |
| 單一實例 | 無偵測，多次啟動會衝突 port 8765 |
| Port 衝突 | 無處理，直接 crash |
| 瀏覽器開啟 | `time.sleep(1.2)` 後 `webbrowser.open()`（**PyInstaller one-file 啟動慢，不足**） |
| GUI | `tkinter.filedialog` 選資料夾，需明確告知 PyInstaller |

---

## 1. 發佈策略比較

### 方案 A：PyInstaller exe + Inno Setup installer ✅（推薦）

PyInstaller 將 Python 直譯器、所有套件（Pillow、PyMuPDF）、launcher.py 打包成 exe，再以 Inno Setup 建立 Windows 安裝程式（`.exe` installer）。

| 面向 | 評估 |
|------|------|
| 離線可用性 | ✅ 完全離線，不需 Python、pip、任何網路 |
| 使用者操作 | ✅ 雙擊 installer → 下一步 → 完成，無需任何技術知識 |
| 維護成本 | ⚠️ 每次更新需重新打包；PyInstaller 版本管理需注意 |
| 檔案大小 | ⚠️ 約 80–150 MB（Python + Pillow + PyMuPDF）；ffmpeg 另計（約 70 MB） |
| 中文路徑 | ✅ `pathlib` + `subprocess` list args 已正確處理 Unicode |
| 防毒誤判 | ⚠️ one-file 風險較高；one-folder 較低；可申請數位簽名降低誤判 |
| 更新方便性 | ⚠️ 需重新發佈 installer；無自動更新（離線環境不需要） |

---

### 方案 B：Python embeddable distribution + wheels + bat

將官方 Python Embeddable Package（zip）與所有 wheels（.whl）打包成 zip 或 installer，附帶 `install.bat` 解壓並安裝。

| 面向 | 評估 |
|------|------|
| 離線可用性 | ✅ 離線，但需執行 install.bat 一次 |
| 使用者操作 | ❌ 需執行 bat、可能遇到路徑或權限問題，技術門檻高 |
| 維護成本 | ✅ 相對透明，wheels 可單獨更換 |
| 檔案大小 | ⚠️ 與方案 A 相近（embeddable ~10 MB + wheels ~100 MB） |
| 中文路徑 | ⚠️ embeddable Python 路徑可能有中文問題 |
| 防毒誤判 | ✅ 純 Python 腳本，幾乎不誤判 |
| 更新方便性 | ✅ 只換 launcher.py 即可 |

**不推薦**：使用者操作難度不符合「雙擊即用」需求。

---

### 方案 C：要求使用者先安裝 Python + 離線 wheels

提供一個 zip，包含 launcher.py 與離線 wheels，附說明請使用者先裝 Python。

| 面向 | 評估 |
|------|------|
| 離線可用性 | ❌ 使用者需先有 Python（需網路下載） |
| 使用者操作 | ❌ 多步驟，不符合學校行政人員使用情境 |
| 維護成本 | ✅ 最低 |
| 防毒誤判 | ✅ 無風險 |

**不推薦**：不符合離線、無 Python 的使用者環境。

---

### 推薦結論

**主要推薦：方案 A — PyInstaller one-folder + Inno Setup**

理由：
- 真正零依賴，使用者完全無需技術知識
- one-folder 比 one-file 啟動更快、防毒誤判更低、ffmpeg 可自然放在旁邊
- Inno Setup 可指定「安裝到使用者目錄」（無需管理員權限），適合學校行政電腦

---

## 2. one-folder vs one-file 比較

| 面向 | one-folder（推薦）| one-file |
|------|-------------------|----------|
| 啟動速度 | ✅ 快（直接執行，無需解壓） | ❌ 慢（每次解壓到 `%TEMP%\\_MEIXXXXXX`，3–15秒）|
| 防毒誤判 | ✅ 較低（exe 旁邊有明確的 dll/pyd 檔案，更透明） | ❌ 較高（自解壓行為易被視為惡意） |
| 檔案透明度 | ✅ 使用者可看到各個 dll，有助 IT 審核 | ❌ 完全不透明 |
| 附帶 ffmpeg.exe | ✅ 直接放 `tools/ffmpeg.exe`，路徑解析簡單 | ⚠️ 需用 `--add-binary` 且 `sys._MEIPASS` 解析 |
| Inno Setup 打包 | ✅ 整個 dist/ 資料夾一起打包 | ✅ 單一 exe |
| 學校電腦部署 | ✅ 較適合，IT 可審查內容 | ❌ 自解壓行為常被學校 EDR 封鎖 |
| 更新維護 | ✅ 可只覆蓋主 exe | ⚠️ 單一 exe 但需整個重部署 |

**推薦：one-folder**

---

## 3. 必包與不包清單

### 必包（由 Inno Setup 放入安裝目錄）

```
dist/媒體啟動器/            ← PyInstaller one-folder 輸出（整個資料夾）
  媒體啟動器.exe
  *.dll / *.pyd
  _internal/               ← PyInstaller 5.x+ 的 lib 子資料夾
tools/
  ffmpeg.exe               ← 影片縮圖用，建議包入
說明.txt
third_party_notices.txt    ← Pillow、PyMuPDF、ffmpeg 授權聲明
```

### 由 Inno Setup 放入 `%APPDATA%\MediaLauncher`（使用者資料，僅首次安裝）

```
config.json    ← 預設檔（空 dirs 清單），onlyifdoesntexist flag
tasks.json     ← 預設檔（空任務），onlyifdoesntexist flag
```

### 不包

```
.thumbs/            ← 縮圖快取，執行時自動在 APPDATA 建立
__pycache__/
plan/               ← 規格文件，非使用者需要
.venv/              ← 開發環境
啟動.bat            ← 改成啟動 exe，不再需要 bat
launcher.py         ← 已打包進 exe
```

---

## 4. launcher.py 需要的修改

> **本節所有修改都在 Phase A 實作，目前不動 launcher.py。**

### 4.1 Base path 與 data path 分離

**問題**：現在 `SCRIPT = Path(__file__).parent` 在 PyInstaller 環境下指向 exe 位置（可能是 Program Files），但 `config.json`、`tasks.json`、`.thumbs/` 需要放在可寫入的使用者目錄。

**修改方案**：

```python
import sys, os
from pathlib import Path

def _app_dir() -> Path:
    """安裝目錄（唯讀，存放 exe 與 tools/）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def _data_dir() -> Path:
    """使用者資料目錄（可寫入）"""
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('APPDATA', Path.home()))
        d = base / 'MediaLauncher'
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent  # 開發模式：仍放在程式旁邊

APP_DIR   = _app_dir()
DATA_DIR  = _data_dir()
THUMB_DIR = DATA_DIR / '.thumbs'
CONFIG_F  = DATA_DIR / 'config.json'
TASKS_F   = DATA_DIR / 'tasks.json'
```

**注意**：移除原有的 `SCRIPT = Path(__file__).parent`，所有舊的 `SCRIPT /` 一律改成 `DATA_DIR /`。

**`sys._MEIPASS` 不使用**：`sys._MEIPASS` 是 one-file 模式的臨時解壓目錄。one-folder 模式只需 `sys.executable` 即可，不需要 `_MEIPASS`。

---

### 4.2 ffmpeg 路徑解析

**問題**：現在 `gen_video_thumb` 直接呼叫 `['ffmpeg', ...]`，依賴 PATH。

**修改方案**：在 top-level 常數區加入，並在程式啟動時解析一次：

```python
def _find_ffmpeg() -> str:
    """優先找 exe 同層 tools/ffmpeg.exe，找不到 fallback 到 PATH"""
    local = APP_DIR / 'tools' / 'ffmpeg.exe'
    if local.exists():
        return str(local)
    return 'ffmpeg'   # fallback，讓 subprocess 從 PATH 找

FFMPEG_BIN = _find_ffmpeg()
```

修改 `gen_video_thumb`：
```python
def gen_video_thumb(src, dst):
    try:
        r = subprocess.run(
            [FFMPEG_BIN, '-y', '-i', src, '-ss', '00:00:01',
             '-vf', 'scale=360:202:force_original_aspect_ratio=decrease,pad=360:202:(ow-iw)/2:(oh-ih)/2:black',
             '-frames:v', '1', str(dst)],
            capture_output=True, timeout=20)
        return dst.exists() and dst.stat().st_size > 0
    except:
        return False
```

---

### 4.3 單一實例偵測 + Port 衝突處理

**問題**：多次啟動會在 port 8765 衝突導致 crash，使用者不知道已在執行。

**修改方案**：在 `if __name__ == '__main__':` 開頭加入：

```python
import socket

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('localhost', port)) == 0

if __name__ == '__main__':
    if _port_in_use(PORT):
        print('媒體啟動器已在執行中，開啟瀏覽器...')
        webbrowser.open(f'http://localhost:{PORT}')
        sys.exit(0)
    # ...（原有啟動程式碼）
```

---

### 4.4 瀏覽器開啟時機（輪詢取代固定 sleep）

**問題**：現在 `time.sleep(1.2)` 後直接開啟瀏覽器。PyInstaller one-folder 啟動通常在 1 秒內，但在舊電腦或 AV 掃描時可能超過 3 秒，導致瀏覽器開到尚未就緒的頁面。

**修改方案**：改成輪詢 server 是否已回應：

```python
def _open_when_ready():
    import urllib.request
    deadline = time.time() + 15   # 最多等 15 秒
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'http://localhost:{PORT}/', timeout=1)
            break
        except Exception:
            time.sleep(0.3)
    webbrowser.open(f'http://localhost:{PORT}')

threading.Thread(target=_open_when_ready, daemon=True).start()
```

---

### 4.5 .thumbs 快取路徑

已在 4.1 中處理：`THUMB_DIR = DATA_DIR / '.thumbs'`。

初始化時 `DATA_DIR/.thumbs/` 自動建立，不需使用者操作。

---

### 4.6 tkinter 在 frozen 環境下的注意事項

PyInstaller 預設不一定包含 tkinter（視 Python 安裝而定）。需在 PyInstaller 指令加：

```
--hidden-import=tkinter
--hidden-import=tkinter.filedialog
```

若 tkinter 無法使用（例如學校電腦鎖定 GUI），`/api/browse` 端點應能 graceful fallback：

```python
try:
    import tkinter as tk
    from tkinter import filedialog
    # ...
except Exception as e:
    self.send_json({'ok': False, 'err': f'無法開啟資料夾選擇器：{e}'})
```

（現有程式已有 `except Exception as e`，確認這段有包住即可。）

---

### 4.7 首次執行資料初始化

安裝後第一次執行，`%APPDATA%\MediaLauncher\config.json` 若不存在，`load_cfg()` 會自動建立預設值（已有此邏輯）。

建議：Inno Setup 的 `onlyifdoesntexist` flag 負責放預設檔，launcher 的 `load_cfg()` 作為雙重保障。兩者邏輯一致，不衝突。

---

## 5. 建置流程

> **本節僅為規格，不在此 spec 執行任何指令。**

### 5.1 建置環境需求

| 項目 | 需求 |
|------|------|
| OS | Windows 10/11（與目標電腦相同或更舊） |
| Python | 3.11.x 或 3.12.x（穩定版，PyInstaller 支援最好） |
| 網路 | 建置機需要網路（下載套件）；目標機器不需要 |

### 5.2 建置步驟（PowerShell 指令範例，僅供參考，不執行）

```powershell
# 1. 建立隔離建置環境
cd "C:\Users\user\Desktop\媒體啟動器"
python -m venv .build-venv
.\.build-venv\Scripts\Activate.ps1

# 2. 安裝依賴（在有網路的建置機上執行）
python -m pip install --upgrade pip
pip install pillow pymupdf pyinstaller

# 3. 取得 ffmpeg（從官方或 gyan.dev 下載靜態編譯版）
#    解壓後取出 ffmpeg.exe，放到：
#    C:\Users\user\Desktop\媒體啟動器\tools\ffmpeg.exe

# 4. 執行 PyInstaller（使用 spec 檔，見 5.3 節）
pyinstaller launcher.spec

# 5. 確認 dist/ 內容
#    dist\媒體啟動器\媒體啟動器.exe 應存在
#    dist\媒體啟動器\tools\ffmpeg.exe 應存在

# 6. 用 Inno Setup 編譯 installer（見第 6 節）
#    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# 7. 驗證輸出
#    output\MediaLauncher-Setup-1.0.0.exe 應存在
```

### 5.3 PyInstaller spec 檔（`launcher.spec`）

```python
# launcher.spec
# 建置指令：pyinstaller launcher.spec

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[
        # ffmpeg 打包進 exe 旁的 tools/ 子目錄
        ('tools/ffmpeg.exe', 'tools'),
    ],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.ttk',
        'fitz',           # PyMuPDF
        'PIL',
        'PIL.Image',
        'PIL.ImageFile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest', 'pydoc', 'doctest',
        'email', 'html', 'http.client',  # 不需要 http client
        'xml', 'xmlrpc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='媒體啟動器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # 壓縮 exe，可加 upx_exclude 排除敏感 dll 避免誤判
    console=True,       # 保留主控台視窗（使用者可見 Ctrl+C 提示與錯誤訊息）
    icon=None,          # 若有 icon.ico 可改為 'icon.ico'
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'ucrtbase.dll'],   # 避免壓縮系統 dll 造成防毒誤判
    name='媒體啟動器',
)
```

**備註**：
- `console=True`：保留主控台視窗，方便使用者知道程式在執行中，也便於 IT 人員診斷問題。若要無主控台（背景執行），改 `console=False`，但需另外提供「結束程式」的方式。
- `upx=True`：UPX 壓縮可縮小約 30%，但部分防毒軟體對 UPX 壓縮的 dll 更敏感。若誤判嚴重，改 `upx=False`。

---

## 6. Inno Setup 規格草案（`installer.iss`）

```iss
; installer.iss
; Inno Setup 6.x

[Setup]
AppName=媒體啟動器
AppVersion=1.0.0
AppPublisher=（發行單位名稱）
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=

; 安裝到使用者本地目錄（不需要管理員權限）
DefaultDirName={localappdata}\MediaLauncher
DefaultGroupName=媒體啟動器
DisableProgramGroupPage=yes

; 不需要管理員，學校電腦的一般使用者即可安裝
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 輸出設定
OutputDir=output
OutputBaseFilename=MediaLauncher-Setup-1.0.0
SetupIconFile=icon.ico    ; 若有圖示
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; 避免同時安裝舊版
CloseApplications=yes
CloseApplicationsFilter=媒體啟動器.exe

; 安裝後不需要重開機
RestartIfNeededByRun=no

[Languages]
; Inno Setup 6 內建繁體中文
Name: "cht"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"

[Files]
; PyInstaller one-folder 全部內容
Source: "dist\媒體啟動器\*"; \
    DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs ignoreversion

; 說明文件
Source: "說明.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "third_party_notices.txt"; DestDir: "{app}"; Flags: ignoreversion

; 使用者資料預設檔（onlyifdoesntexist：已有設定的使用者重裝後不會蓋掉資料）
Source: "default_data\config.json"; \
    DestDir: "{userappdata}\MediaLauncher"; \
    Flags: onlyifdoesntexist
Source: "default_data\tasks.json"; \
    DestDir: "{userappdata}\MediaLauncher"; \
    Flags: onlyifdoesntexist

[Icons]
; 開始功能表
Name: "{group}\媒體啟動器"; Filename: "{app}\媒體啟動器.exe"
Name: "{group}\解除安裝 媒體啟動器"; Filename: "{uninstallexe}"

; 桌面捷徑（使用者可選擇）
Name: "{userdesktop}\媒體啟動器"; \
    Filename: "{app}\媒體啟動器.exe"; \
    Tasks: desktopicon

[Tasks]
Name: "desktopicon"; \
    Description: "在桌面建立捷徑"; \
    GroupDescription: "額外選項:"; \
    Flags: unchecked

[Run]
; 安裝完成後詢問是否立即啟動
Filename: "{app}\媒體啟動器.exe"; \
    Description: "立即啟動媒體啟動器"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 解除安裝時只刪除安裝目錄的內容
; 不刪除 {userappdata}\MediaLauncher（使用者的 config / tasks 保留）
Type: filesandordirs; Name: "{app}"

[Code]
; 解除安裝時詢問是否同時刪除使用者資料
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  MsgResult: Integer;
begin
  if CurUninstallStep = usPostUninstall then begin
    DataDir := ExpandConstant('{userappdata}\MediaLauncher');
    if DirExists(DataDir) then begin
      MsgResult := MsgBox(
        '是否同時刪除您的任務清單與設定資料？' + #13#10 +
        '（位於：' + DataDir + '）' + #13#10#13#10 +
        '選「是」將永久刪除所有任務與設定。' + #13#10 +
        '選「否」將保留資料，日後重新安裝後仍可使用。',
        mbConfirmation, MB_YESNO);
      if MsgResult = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
```

### 6.1 `default_data/` 預設檔說明

建置前需建立 `default_data/` 資料夾，放入：

```json
// default_data/config.json
{
  "dirs": [],
  "recursive": false
}
```

```json
// default_data/tasks.json
{
  "activeTaskId": null,
  "tasks": []
}
```

使用者第一次安裝時，這兩個檔案會複製到 `%APPDATA%\MediaLauncher\`。若使用者已有資料（重裝），Inno Setup 的 `onlyifdoesntexist` 旗標確保不覆蓋。

---

## 7. 測試計畫（離線部署 Checklist）

### 7.1 環境準備

- 測試機：與目標環境相同的 Windows 10/11
- 確認測試機**沒有安裝 Python**
- 確認測試機**沒有網路**（或斷網測試）
- 確認測試機**不在** PATH 上有 ffmpeg

### 7.2 安裝測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| I-1 | 雙擊 installer，一般使用者（非管理員）安裝 | 安裝成功，無需 UAC 提示 |
| I-2 | 安裝完成點「立即啟動」 | 主控台視窗出現，瀏覽器自動開啟 `localhost:8765` |
| I-3 | 開始功能表中可找到「媒體啟動器」 | 捷徑存在且可啟動 |
| I-4 | 若選擇桌面捷徑，桌面出現捷徑 | 捷徑存在且可啟動 |
| I-5 | `%APPDATA%\MediaLauncher\config.json` 存在 | 初始 `dirs: []` 內容 |
| I-6 | `%APPDATA%\MediaLauncher\tasks.json` 存在 | 初始空任務內容 |

### 7.3 基本功能測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| F-1 | 點「＋ 加入資料夾」，選擇含媒體檔的資料夾 | tkinter 對話框出現，選擇後媒體卡片顯示 |
| F-2 | 中文路徑資料夾（如 `C:\使用者\影片`） | 正常加入、正常掃描 |
| F-3 | 含空白的路徑（如 `C:\My Documents\`） | 正常運作 |
| F-4 | 點擊媒體卡片 | 以系統預設程式開啟（`.startfile()`） |

### 7.4 縮圖測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| T-1 | 加入含 `.jpg/.png` 的資料夾 | 圖片縮圖顯示（Pillow） |
| T-2 | 加入含 `.pdf` 的資料夾 | PDF 首頁縮圖顯示（PyMuPDF） |
| T-3 | 加入含 `.mp4/.mkv` 的資料夾 | 影片縮圖顯示（ffmpeg）；若 tools/ffmpeg.exe 存在 |
| T-4 | 無 ffmpeg 時加入影片 | 顯示影片 placeholder emoji，不 crash |
| T-5 | 加入 `.pptx` | 顯示 PPT placeholder（無縮圖，符合設計） |
| T-6 | 關閉後重開 | `.thumbs/` 中已有快取，縮圖立即顯示（不重算） |

### 7.5 任務清單功能測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| TK-1 | 建立新任務 | 任務出現在下拉選單 |
| TK-2 | 拖曳媒體卡片到任務清單 | 加入成功，顯示 compact card |
| TK-3 | 任務項目拖曳重排 | 順序正確，`tasks.json` 儲存 |
| TK-4 | 點「▶ 播放目前」 | 以系統程式開啟，顯示「目前」badge |
| TK-5 | 點「▶▶ 下一個」 | 開啟下一個，「下一個」badge 移動 |
| TK-6 | 改名任務 | 名稱更新，`tasks.json` 儲存 |
| TK-7 | 刪除任務項目 | 項目移除，順序更新 |
| TK-8 | 刪除任務 | 任務消失，自動切換到其他任務 |
| TK-9 | 關閉後重開 | 任務與 currentIndex 恢復 |

### 7.6 多開偵測測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| M-1 | 程式已在執行，再雙擊捷徑 | 瀏覽器開啟已在跑的實例，不另開 server |
| M-2 | 主控台關閉後再啟動 | 正常啟動新實例 |

### 7.7 解除安裝測試

| # | 測試項目 | 預期結果 |
|---|---------|---------|
| U-1 | 解除安裝時選「否」保留資料 | `%APPDATA%\MediaLauncher` 保留 |
| U-2 | 解除安裝時選「是」刪除資料 | `%APPDATA%\MediaLauncher` 刪除 |
| U-3 | 解除安裝後使用者媒體檔案完整 | 使用者的 `C:\影片\` 等資料夾完全未受影響 |
| U-4 | 解除安裝後重新安裝 | 若選「否」保留，config 和 tasks 恢復 |

---

## 8. 風險與決策

| 風險 | 嚴重度 | 緩解方案 |
|------|--------|---------|
| **防毒誤判（exe）** | 中 | 使用 one-folder（比 one-file 風險低）；若有預算申請 code signing certificate；提前提交給學校 AV 白名單 |
| **Program Files 寫入限制** | 高 | `DATA_DIR` 改用 `%APPDATA%`；Inno Setup `PrivilegesRequired=lowest` 安裝到 `%LOCALAPPDATA%` |
| **ffmpeg 授權** | 中 | ffmpeg 靜態編譯版通常為 GPL；需在 `third_party_notices.txt` 列出；建議從 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 取得 GPL 版本並保留 license 文件 |
| **PowerPoint 無法播放** | 低 | 屬 OS 層級問題（需 Microsoft Office）；在說明文件告知；`os.startfile()` 本身無問題 |
| **Port 8765 被占用** | 中 | 偵測後直接開啟已在跑的實例（見 4.3 節）；若非本程式佔用，提示錯誤訊息並建議結束佔用程式 |
| **Windows Defender SmartScreen** | 中 | 首次執行會警告「未知發行者」；可申請 code signing 消除；或在說明文件提示「點選更多資訊 → 仍要執行」 |
| **中文路徑 / 空白路徑** | 低 | `subprocess` 已用 list args（非字串拼接），`pathlib` 已處理 Unicode；風險極低 |
| **學校電腦 UAC / 群組原則限制** | 中 | `PrivilegesRequired=lowest` 確保不需管理員；若群組原則禁止安裝 exe，需由 IT 管理員授權 |
| **PyMuPDF 授權（AGPL）** | 中 | PyMuPDF 2.x 為 AGPL；若用於商業用途需購買授權；學校/教育用途請確認是否符合 AGPL 條款；替代方案：改用 `pdfplumber` 或 `pypdf`（MIT） |
| **tkinter 在學校電腦不可用** | 低 | 已有 `except Exception` 包住，會回傳錯誤訊息；使用者仍可手動輸入路徑 |

---

## 9. 分階段實作計畫

### Phase A：調整 launcher.py runtime path / data path / ffmpeg path

**目標**：讓 launcher.py 在 PyInstaller frozen 環境下正確運作。

**要改的檔案**：`launcher.py`

**具體修改**：
1. 用 `_app_dir()` / `_data_dir()` 取代 `SCRIPT = Path(__file__).parent`（見 4.1 節）
2. 加入 `_find_ffmpeg()` 常數，修改 `gen_video_thumb` 使用 `FFMPEG_BIN`（見 4.2 節）
3. 加入 `_port_in_use()` 單一實例偵測（見 4.3 節）
4. 改 `_open()` 為 `_open_when_ready()`（輪詢取代 sleep）（見 4.4 節）
5. 確認 tkinter `except Exception` 有包住（見 4.6 節）

**驗證方式**：
- `python -m py_compile launcher.py` — 語法無誤
- 直接執行 `python launcher.py` — 確認 dev 模式下仍正常（`DATA_DIR` = 程式旁邊）
- 確認 `config.json`、`tasks.json`、`.thumbs/` 仍在預期位置

**完成條件**：
- [ ] `_app_dir()` / `_data_dir()` 存在且邏輯正確
- [ ] `FFMPEG_BIN` 常數存在，`gen_video_thumb` 使用它
- [ ] 多開時第二個實例開啟瀏覽器後立即退出
- [ ] 瀏覽器輪詢開啟邏輯取代固定 sleep
- [ ] `python -m py_compile launcher.py` 通過

**輸出**：修改後的 `launcher.py`

---

### Phase B：建立 PyInstaller spec 與建置腳本

**目標**：可重複執行的 PyInstaller 建置，輸出 one-folder dist。

**要建立的檔案**：
- `build/launcher.spec`（見 5.3 節內容）
- `build/build.ps1`（建置腳本，包含 venv 建立、套件安裝、pyinstaller 執行步驟）
- `build/requirements.txt`（`pillow`, `pymupdf`, `pyinstaller`，固定版本號）

**具體步驟**：
1. 依 5.3 節建立 `launcher.spec`
2. 確認 `tools/ffmpeg.exe` 存在（建置前需手動放置）
3. 執行 `pyinstaller build/launcher.spec`
4. 檢查 `dist/媒體啟動器/媒體啟動器.exe` 存在
5. 在有 Python 的電腦上直接執行 `dist/媒體啟動器/媒體啟動器.exe` 初步測試

**驗證方式**：
- `dist/媒體啟動器/媒體啟動器.exe` 存在
- `dist/媒體啟動器/tools/ffmpeg.exe` 存在
- 直接執行 exe → 瀏覽器開啟，基本功能正常
- 確認 `%APPDATA%\MediaLauncher\` 建立（Phase A 的 `_data_dir()` 生效）

**完成條件**：
- [ ] `launcher.spec` 建置成功，無 error
- [ ] dist 資料夾中 exe 可直接執行
- [ ] `tools/ffmpeg.exe` 在 exe 旁邊
- [ ] APPDATA 資料夾自動建立

**輸出**：`dist/媒體啟動器/`（整個資料夾）

---

### Phase C：建立 Inno Setup 腳本與 installer

**目標**：可在無網路的 Windows 上安裝的 `.exe` installer。

**要建立的檔案**：
- `build/installer.iss`（見第 6 節）
- `default_data/config.json`
- `default_data/tasks.json`
- `third_party_notices.txt`（Pillow MIT、PyMuPDF AGPL、ffmpeg GPL 授權聲明）

**具體步驟**：
1. 安裝 Inno Setup 6（建置機）
2. 依第 6 節建立 `installer.iss`
3. 執行 `ISCC.exe build\installer.iss`
4. 確認 `output/MediaLauncher-Setup-1.0.0.exe` 產生

**驗證方式**：
- installer 可在有 Python 的電腦上安裝
- 安裝後 `%LOCALAPPDATA%\MediaLauncher\媒體啟動器.exe` 存在
- 安裝後 `%APPDATA%\MediaLauncher\config.json` 存在（預設檔）
- 解除安裝後詢問是否刪除使用者資料

**完成條件**：
- [ ] `installer.iss` 編譯成功
- [ ] 安裝後可啟動且功能正常
- [ ] 解除安裝邏輯（詢問保留/刪除使用者資料）正常

**輸出**：`output/MediaLauncher-Setup-1.0.0.exe`

---

### Phase D：建立 README 與使用說明

**目標**：使用者可理解如何安裝、使用、解除安裝。

**要建立/更新的檔案**：
- `說明.txt`（使用者看的，放進 installer）
- `build/BUILD_README.md`（開發者看的，說明如何重新建置）

**`說明.txt` 建議內容（繁體中文）**：
```
媒體啟動器 v1.0.0
==================

【安裝後如何啟動】
雙擊桌面的「媒體啟動器」捷徑，
或從開始功能表找到「媒體啟動器」。

啟動後瀏覽器會自動開啟，黑色主控台視窗請勿關閉。
關閉主控台視窗 = 關閉服務。

【如何加入媒體資料夾】
點畫面左側「＋ 加入資料夾」，選擇含有影片、圖片、文件的資料夾。

【播放任務清單】
...

【首次啟動 Windows 安全性警告】
若出現「Windows 保護您的電腦」提示：
1. 點「更多資訊」
2. 點「仍要執行」

【影片縮圖說明】
影片縮圖需要 ffmpeg。本程式已內建 ffmpeg，無需另行安裝。

【授權聲明】
詳見安裝目錄中的 third_party_notices.txt。
```

**完成條件**：
- [ ] `說明.txt` 內容完整、適合非技術使用者
- [ ] `BUILD_README.md` 記錄建置步驟
- [ ] `third_party_notices.txt` 列出所有第三方授權

**輸出**：`說明.txt`、`build/BUILD_README.md`、`third_party_notices.txt`

---

### Phase E：實機測試與修正

**目標**：在模擬目標環境的測試機上完整驗證。

**測試環境設定**：
- 新的 Windows 10/11 虛擬機或實體機
- 不安裝 Python
- 斷開網路
- 不在 PATH 設定 ffmpeg

**執行第 7 節所有 checklist 項目**

**完成條件**：
- [ ] 第 7.2 節全部通過（I-1 ~ I-6）
- [ ] 第 7.3 節全部通過（F-1 ~ F-4）
- [ ] 第 7.4 節至少 T-1、T-2、T-4 通過（T-3 需 ffmpeg）
- [ ] 第 7.5 節全部通過（TK-1 ~ TK-9）
- [ ] 第 7.6 節通過（M-1、M-2）
- [ ] 第 7.7 節全部通過（U-1 ~ U-4）

**輸出**：測試報告（哪些通過、哪些待修正），修正後的 installer

---

## 附錄：檔案結構

### 建置完成後的完整目錄結構

```
C:\Users\user\Desktop\媒體啟動器\
├── launcher.py                   ← 修改後（Phase A）
├── 說明.txt                      ← 更新後（Phase D）
├── build/
│   ├── launcher.spec             ← Phase B
│   ├── build.ps1                 ← Phase B
│   ├── requirements.txt          ← Phase B
│   ├── installer.iss             ← Phase C
│   └── BUILD_README.md           ← Phase D
├── default_data/
│   ├── config.json               ← Phase C
│   └── tasks.json                ← Phase C
├── tools/
│   └── ffmpeg.exe                ← 手動下載，Phase B 前放置
├── third_party_notices.txt       ← Phase D
├── dist/
│   └── 媒體啟動器/              ← Phase B 輸出
│       ├── 媒體啟動器.exe
│       ├── tools/
│       │   └── ffmpeg.exe
│       └── _internal/           ← PyInstaller libs
├── output/
│   └── MediaLauncher-Setup-1.0.0.exe   ← Phase C 輸出
└── plan/
    ├── spec.md
    ├── resizable-task-sidebar-and-thumbnails.md
    ├── task-compact-list-cards.md
    └── offline-installer.md      ← 本文件
```

### 使用者安裝後的目錄結構

```
%LOCALAPPDATA%\MediaLauncher\     ← 安裝目錄（唯讀，程式檔）
├── 媒體啟動器.exe
├── tools/
│   └── ffmpeg.exe
├── _internal/
├── 說明.txt
└── third_party_notices.txt

%APPDATA%\MediaLauncher\          ← 使用者資料（可寫入）
├── config.json                   ← 資料夾設定
├── tasks.json                    ← 任務清單
└── .thumbs/                      ← 縮圖快取（自動建立）
    ├── abc123.jpg
    └── ...
```
