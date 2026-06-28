# 媒體啟動器 — 離線發佈流程

> 本文件說明如何從乾淨的建置環境，製作一個可交付給「無法上網的 Windows 使用者」的安裝包。

---

## 發佈流程總覽

```
[建置機（有網路）]                    [目標電腦（無網路、無 Python）]

1. 準備建置環境
2. 放置 tools/ffmpeg.exe
3. .\build\build_pyinstaller.ps1   → dist\MediaLauncher\
4. .\installer\build_installer.ps1 → installer\MediaLauncherSetup.exe
5. 複製 installer\MediaLauncherSetup.exe 到 USB ──────────────────→  雙擊安裝
                                                                       瀏覽器自動開啟
```

---

## 步驟一：準備乾淨建置環境

**建置機需求**：

| 項目 | 說明 |
|------|------|
| OS | Windows 10 / 11（與目標電腦相同版本或更舊） |
| Python | 3.10–3.12，官方安裝版（非 Microsoft Store 版） |
| 網路 | 需要下載 pillow、pymupdf、pyinstaller |
| Inno Setup 6 | 下載：https://jrsoftware.org/isdl.php |
| 磁碟空間 | 至少 1 GB |

確認 Python 可用：

```powershell
python --version
```

---

## 步驟二：放置 tools/ffmpeg.exe（若需要影片縮圖）

**必須在執行 build_pyinstaller.ps1 之前放置。**

```
媒體啟動器\
└── tools\
    └── ffmpeg.exe    ← 放這裡
```

**ffmpeg 來源（選擇其一，須在有網路的建置機下載）**：

- gyan.dev（推薦，GPL 靜態版）：https://www.gyan.dev/ffmpeg/builds/
  - 下載 `ffmpeg-release-essentials.zip`
  - 解壓 → 取出 `bin\ffmpeg.exe`

- BtbN/FFmpeg-Builds（GitHub）：https://github.com/BtbN/FFmpeg-Builds/releases
  - 下載 `ffmpeg-master-latest-win64-gpl.zip`

> ⚠️ **授權提醒**：ffmpeg GPL 版本為 GPL v2+，發佈時須附帶授權聲明。  
> 請確認使用的是合法取得的版本，不要從來源不明的網站下載。  
> 授權聲明模板見：`release/third-party-notices-template.md`

若**不需要影片縮圖**，可以跳過此步驟。影片項目會顯示 🎬 placeholder，不影響其他功能。

---

## 步驟三：執行 PyInstaller 打包

```powershell
.\build\build_pyinstaller.ps1
```

此腳本會：
- 建立虛擬環境 `.venv`（首次執行需下載套件）
- 安裝 pillow、pymupdf、pyinstaller
- 產生 `dist\MediaLauncher\`

**輸出確認**：

```
dist\MediaLauncher\
├── MediaLauncher.exe       ← 主程式
├── config.json             ← 預設設定（首次啟動時複製到 %APPDATA%）
├── tasks.json              ← 預設任務（首次啟動時複製到 %APPDATA%）
├── 說明.txt
├── tools\
│   └── ffmpeg.exe          ← 若 step 2 有放置
└── _internal\              ← PyInstaller runtime（必須隨 exe 一起）
    ├── python3xx.dll
    └── ...（許多 dll/pyd）
```

---

## 步驟四：編譯 Inno Setup Installer

```powershell
.\installer\build_installer.ps1
```

此腳本會：
- 確認 `dist\MediaLauncher\MediaLauncher.exe` 存在
- 找到本機安裝的 ISCC.exe（Inno Setup 編譯器）
- 產生 `installer\MediaLauncherSetup.exe`

**輸出**：`installer\MediaLauncherSetup.exe`（約 60–150 MB）

---

## 步驟五：整理離線交付包

建議在 USB 或內網分享上建立以下結構：

```
MediaLauncher-Offline-1.0.0\
├── MediaLauncherSetup.exe          ← 給使用者的安裝包（主要交付物）
├── user-guide.md                   ← 使用者操作說明（可選：轉為 PDF）
├── third-party-notices.txt         ← 第三方授權聲明（必要）
└── README.txt                      ← 簡短說明（如何安裝、資料位置）
```

**不應放入交付包的內容**：

| 路徑 | 原因 |
|------|------|
| `launcher.py` | 原始碼，非使用者需要 |
| `build/` | 建置腳本，非使用者需要 |
| `plan/` | 規格文件，非使用者需要 |
| `.venv/` | 開發虛擬環境，體積龐大 |
| `.thumbs/` | 建置機的縮圖快取，對使用者無用 |
| `__pycache__/` | Python 快取 |
| `dist/` | PyInstaller 展開內容，Installer 已包含 |
| `installer/MediaLauncher.iss` | 建置腳本，非使用者需要 |

---

## 步驟六：複製到 USB 或內網分享

```
USB 隨身碟\
└── MediaLauncher-Offline-1.0.0\
    └── MediaLauncherSetup.exe      ← 最小發佈包，只需這一個檔案也可以
```

或透過學校內網分享資料夾分發（同樣不需要網路）。

---

## 步驟七：在目標電腦安裝與初步測試

1. 雙擊 `MediaLauncherSetup.exe`
2. 點「下一步」完成精靈（**不需要管理員、不需要網路**）
3. 安裝完成勾選「立即啟動媒體啟動器」
4. 瀏覽器自動開啟 `http://localhost:8765`
5. 點「＋ 加入資料夾」加入含媒體的資料夾
6. 確認各類媒體可正常顯示與播放

完整測試清單見：`release/offline-test-checklist.md`

---

## 產物說明

| 產物 | 用途 |
|------|------|
| `dist\MediaLauncher\` | **未壓縮可直接測試版本**。可以複製到任何電腦直接跑，不用 installer。方便開發者快速測試，或 IT 人員審查 exe 內容。 |
| `installer\MediaLauncherSetup.exe` | **給使用者的安裝包**。透過 Inno Setup 壓縮打包，包含捷徑建立、資料目錄初始化、解除安裝功能。 |

---

## 授權提醒（發佈前必須確認）

### PyMuPDF（AGPL 授權）⚠️

PyMuPDF（`fitz`）採用 **AGPL v3 授權**：

- 學術研究、個人用途、開源軟體：可免費使用
- **學校行政部署、商業用途**：若不打算公開原始碼，需購買商業授權
- 詳見：https://pymupdf.readthedocs.io/en/latest/about.html

若無法接受 AGPL 條款，評估方案：
1. 移除 PDF 縮圖功能（PDF 顯示 📄 placeholder，仍可開啟播放）
2. 改用 LGPL 的 poppler + pdf2image（需系統安裝 poppler）

### ffmpeg（GPL/LGPL）

- GPL 靜態編譯版（含 libx264 等）：發佈時必須附帶 GPL 授權聲明與 source code 取得方式
- LGPL 動態連結版：授權較寬鬆，但打包複雜度較高
- 詳見：https://ffmpeg.org/legal.html

### 填寫授權聲明

請在發佈前填寫並附帶：`release/third-party-notices-template.md`  
（填寫實際版本號後更名為 `third-party-notices.txt`）

---

## 版本更新流程

若需要更新版本（修改 launcher.py 後）：

1. 修改 `build\MediaLauncher.spec` 中的版本號（若有）
2. 修改 `installer\MediaLauncher.iss` 中的 `AppVersion=`
3. 重新執行步驟三～五
4. 使用者重新安裝新版 installer（Inno Setup 的 `CloseApplications=yes` 會處理版本更新）
5. 使用者資料（任務清單、資料夾設定）在更新後完整保留

---

## 常見問題

### 建置機與目標電腦的 Windows 版本不一致

PyInstaller 打包的 exe 應該向下相容（在舊版 Windows 上執行）。  
建議在**不低於目標電腦版本**的 Windows 上建置。  
若目標是 Windows 10，建置機也應使用 Windows 10 或 11。

### 目標電腦被 Windows Defender / SmartScreen 攔截

首次在新電腦執行未簽名的 exe 可能出現警告。解法：
- 點「更多資訊」→「仍要執行」
- 或聯繫 IT 人員將程式加入白名單
- 根本解法：申請 Code Signing 憑證對 exe 簽名

### 安裝後無法啟動（port 8765 被占用）

```powershell
netstat -ano | findstr :8765
```

確認是否有其他程式佔用，結束後重試。
