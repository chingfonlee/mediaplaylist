# 媒體啟動器 — Build 說明

## 前置準備

| 需求 | 說明 |
|------|------|
| Windows 10/11 | 建置與目標環境相同或更舊的 Windows 版本，確保 DLL 相容性 |
| Python 3.10–3.12 | 建議使用官方安裝版（非 Microsoft Store 版）；確認 `python --version` 可執行 |
| 網路連線 | 建置機需要網路安裝套件；目標（離線）機器**不需要**網路 |
| 磁碟空間 | 至少 1 GB（虛擬環境 + PyInstaller 暫存 + dist 輸出） |

---

## ffmpeg.exe 放置

影片縮圖功能需要 ffmpeg。請在**執行 build 之前**放置：

```
媒體啟動器\
└── tools\
    └── ffmpeg.exe        ← 這裡
```

ffmpeg 取得方式（擇一）：

- **gyan.dev**（GPL 靜態編譯版，推薦）：  
  https://www.gyan.dev/ffmpeg/builds/  
  下載 `ffmpeg-release-essentials.zip`，解壓取出 `bin\ffmpeg.exe`

- **BtbN/FFmpeg-Builds**（GitHub Releases）：  
  https://github.com/BtbN/FFmpeg-Builds/releases  
  下載 `ffmpeg-master-latest-win64-gpl.zip`

若 `tools\ffmpeg.exe` **不存在**，build script 仍可正常執行，  
只是打包後的 exe 不含 ffmpeg，影片縮圖會顯示 placeholder 圖示（不會 crash）。

---

## 執行 Build

從**任意位置**執行（PowerShell）：

```powershell
.\build\build_pyinstaller.ps1
```

腳本會自動：
1. 確認 launcher.py 存在
2. 建立 `.venv`（若不存在）
3. 安裝 `pillow`、`pymupdf`、`pyinstaller`
4. 清理舊的 `dist\MediaLauncher\`
5. 執行 PyInstaller，輸出到 `dist\MediaLauncher\`
6. 報告結果與下一步

> **重要**：腳本只清理 PyInstaller 產生物（`dist\MediaLauncher\`、`build\_pyinstaller_work\`），  
> 絕對不會刪除 `config.json`、`tasks.json`、`launcher.py` 或使用者資料。

---

## Build 輸出位置

```
媒體啟動器\
└── dist\
    └── MediaLauncher\           ← 整個資料夾即可部署
        ├── MediaLauncher.exe    ← 主程式（雙擊啟動）
        ├── config.json          ← 預設設定（frozen 首次啟動時複製到 %APPDATA%）
        ├── tasks.json           ← 預設任務資料（同上）
        ├── 說明.txt
        ├── tools\
        │   └── ffmpeg.exe       ← 若存在才有此目錄
        ├── _internal\           ← PyInstaller 的 Python 執行環境（必須隨 exe 一起）
        │   ├── python3xx.dll
        │   ├── *.pyd
        │   └── ...
        └── third_party_notices.txt  ← 若存在
```

> `_internal\` 是 PyInstaller 5.8+ 的新目錄名稱（舊版會在 exe 旁邊直接放 dll）。  
> 整個 `dist\MediaLauncher\` 資料夾必須完整複製，不能只複製 exe。

---

## 手動測試 dist 輸出

### 基本測試（有 Python 的建置機）

```powershell
dist\MediaLauncher\MediaLauncher.exe
```

確認：
- 主控台視窗出現，顯示「媒體啟動器已啟動」
- 主控台顯示「資料目錄：C:\Users\<你的帳號>\AppData\Roaming\MediaLauncher」
- 瀏覽器自動開啟 `http://localhost:8765`
- UI 正常顯示

### 確認 frozen 模式的資料目錄

首次執行後，確認 `%APPDATA%\MediaLauncher\` 被建立：

```powershell
Get-ChildItem "$env:APPDATA\MediaLauncher"
```

預期看到：
```
config.json
tasks.json
.thumbs\      ← 會在第一次掃描後出現
```

### 重測首次啟動

若要重新測試「第一次啟動時複製預設檔」的邏輯：

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\MediaLauncher"
dist\MediaLauncher\MediaLauncher.exe
```

### 測試多開防護

1. 啟動 `MediaLauncher.exe`，讓 server 在背景執行
2. 再次雙擊 `MediaLauncher.exe`
3. 預期：第二個視窗出現「已有媒體啟動器正在執行，已開啟現有視窗」後立即關閉

### 離線環境測試（最終驗證）

在**無網路、無 Python** 的 Windows 機器上：

1. 複製整個 `dist\MediaLauncher\` 資料夾
2. 雙擊 `MediaLauncher.exe`
3. 確認瀏覽器開啟且所有功能正常

---

## PyInstaller Hidden Imports 說明

spec 檔中手動指定了以下 hidden imports，原因如下：

| 套件 | 原因 |
|------|------|
| `tkinter`, `tkinter.filedialog` | PyInstaller 有時無法自動偵測 tkinter（尤其是 Windows Embeddable Python）|
| `fitz`, `fitz.utils` | PyMuPDF 使用 C extension，PyInstaller 靜態分析不一定能追蹤 |
| `PIL.JpegImagePlugin` 等 | Pillow 的格式 plugin 是動態載入，需逐一列出常用格式 |

若 build 後遇到 `ModuleNotFoundError` 或功能異常，請在 spec 的 `hiddenimports` 清單中補充缺少的模組，再重新 build。

---

## UPX 壓縮說明

spec 預設啟用 UPX（`upx=True`），可縮小 exe 約 30%。

若部署到的學校電腦防毒軟體對 UPX 壓縮的 exe 有誤判，請修改 spec：

```python
# build\MediaLauncher.spec
exe = EXE(
    ...
    upx=False,    # 改這裡
    ...
)
coll = COLLECT(
    ...
    upx=False,    # 以及這裡
    ...
)
```

---

## console=True vs console=False

| 設定 | 建議時機 |
|------|---------|
| `console=True`（目前預設） | 開發與測試階段：使用者可看到 server 是否在跑，便於診斷問題 |
| `console=False` | 最終 release 版本：背景執行，沒有黑色主控台視窗 |

修改方式：編輯 `build\MediaLauncher.spec`，找到 `console=True` 改為 `console=False`，重新執行 build script。

> **注意**：`console=False` 後，程式執行錯誤會完全無聲失敗，建議測試充分後再改。

---

## PyMuPDF 授權注意（重要）

PyMuPDF（`fitz`）2.x 版採用 **AGPL 授權**：

- 學術、研究、開源用途：AGPL 條款下可免費使用
- 商業用途或學校行政部署（若不打算公開原始碼）：需購買商業授權
  - 詳見：https://pymupdf.readthedocs.io/en/latest/about.html

若需迴避 AGPL，PDF 縮圖功能可改用：

- `pypdf`（MIT）：不含縮圖功能，只能讀取文字
- `pdf2image`（MIT）：需要系統安裝 poppler，增加依賴複雜度
- 直接移除 PDF 縮圖功能：PDF 項目顯示 placeholder 圖示

---

## 第三方授權清單

打包發佈前，請在專案根目錄建立 `third_party_notices.txt`，包含：

```
Pillow         — MIT License       https://github.com/python-pillow/Pillow
PyMuPDF        — AGPL v3 License   https://pymupdf.readthedocs.io/about.html
PyInstaller    — GPL v2 + exception https://pyinstaller.org/
ffmpeg         — LGPL/GPL License  https://ffmpeg.org/legal.html
               （請依使用的 build 版本確認確切授權版本）
```

`third_party_notices.txt` 若存在，build script 會自動打包進 dist。

---

## 常見問題

### Build 時出現 `ModuleNotFoundError: No module named 'fitz'`

```powershell
.venv\Scripts\pip install --upgrade pymupdf
```

然後重新執行 build script。

### 執行 dist\MediaLauncher\MediaLauncher.exe 後無法開啟瀏覽器

確認 port 8765 未被占用：

```powershell
netstat -ano | findstr :8765
```

若有其他程式佔用，關閉後再試。

### 防毒軟體偵測到 MediaLauncher.exe

1. 嘗試設定 `upx=False` 重新 build（見上方 UPX 說明）
2. 將 `dist\MediaLauncher\` 資料夾加入防毒白名單
3. 如有預算，申請 Code Signing Certificate 對 exe 簽名

### 舊版 PyInstaller 5.x 的 spec 相容性

spec 檔已自動偵測 PyInstaller 版本並調整 `cipher` 參數，  
支援 PyInstaller 5.x 和 6.x，無需手動調整。
