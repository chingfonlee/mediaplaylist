# 媒體啟動器 — Installer 製作說明

## 前置條件

必須先完成 **Phase B（PyInstaller build）**，確認以下檔案存在：

```
dist\MediaLauncher\MediaLauncher.exe    ← 主程式 exe
dist\MediaLauncher\_internal\           ← PyInstaller runtime（必須同行）
dist\MediaLauncher\config.json          ← 預設設定
dist\MediaLauncher\tasks.json           ← 預設任務資料
dist\MediaLauncher\說明.txt
dist\MediaLauncher\tools\ffmpeg.exe     ← 若有影片縮圖功能
```

若 `dist\MediaLauncher\` 不存在，請先執行：

```powershell
.\build\build_pyinstaller.ps1
```

---

## 安裝 Inno Setup 6

請在**建置機**（有網路的電腦）安裝：

- 官方下載：https://jrsoftware.org/isdl.php
- 選擇 `innosetup-6.x.x.exe`（穩定版）
- 預設安裝到 `C:\Program Files (x86)\Inno Setup 6\`
- 安裝完成後確認 `ISCC.exe` 存在於上述路徑

---

## 編譯 Installer

### 方式 A：PowerShell 腳本（建議）

```powershell
.\installer\build_installer.ps1
```

腳本會自動：
1. 確認 `dist\MediaLauncher\MediaLauncher.exe` 存在
2. 找到 `ISCC.exe`（自動搜尋常見安裝位置）
3. 編譯 `installer\MediaLauncher.iss`
4. 確認 `installer\MediaLauncherSetup.exe` 產生

### 方式 B：Inno Setup GUI 手動編譯

1. 開啟 Inno Setup 6
2. `File` → `Open` → 選擇 `installer\MediaLauncher.iss`
3. `Build` → `Compile`（或按 `Ctrl+F9`）
4. 等待完成，確認下方輸出視窗無錯誤

---

## Installer 輸出

| 項目 | 位置 |
|------|------|
| Installer 執行檔 | `installer\MediaLauncherSetup.exe` |
| 大小 | 約 60–120 MB（依是否含 ffmpeg 而定） |

---

## 安裝流程（使用者端）

1. 雙擊 `MediaLauncherSetup.exe`
2. 點「下一步」完成安裝精靈（**不需要管理員權限**）
3. 可選擇是否在桌面建立捷徑
4. 可選擇安裝後立即啟動

---

## 安裝後路徑

| 內容 | 路徑 |
|------|------|
| **程式本體**（exe、dll） | `%LOCALAPPDATA%\MediaLauncher\` |
| 主程式 | `%LOCALAPPDATA%\MediaLauncher\MediaLauncher.exe` |
| ffmpeg（若有） | `%LOCALAPPDATA%\MediaLauncher\tools\ffmpeg.exe` |
| 開始功能表捷徑 | 使用者的「開始」功能表 → 媒體啟動器 |
| 桌面捷徑 | `%USERPROFILE%\Desktop\媒體啟動器`（若安裝時勾選） |

---

## 使用者資料路徑

使用者的設定與任務資料儲存在**不同的位置**（與程式本體分開）：

| 內容 | 路徑 |
|------|------|
| **使用者資料目錄** | `%APPDATA%\MediaLauncher\` |
| 資料夾設定 | `%APPDATA%\MediaLauncher\config.json` |
| 任務清單 | `%APPDATA%\MediaLauncher\tasks.json` |
| 縮圖快取 | `%APPDATA%\MediaLauncher\.thumbs\` |

這些資料在**解除安裝後仍會保留**，確保使用者不會意外遺失任務清單。

> **首次安裝說明**：程式第一次啟動時，若 `%APPDATA%\MediaLauncher\` 不存在，  
> 會自動將安裝目錄中的預設 `config.json` 和 `tasks.json` 複製過去。  
> 後續重新安裝不會覆蓋已有資料。

---

## 解除安裝

### 方式 A：透過 Windows 設定

`Windows 設定` → `應用程式` → 搜尋「媒體啟動器」→ 解除安裝

### 方式 B：透過開始功能表

`開始` → `媒體啟動器` → `解除安裝 媒體啟動器`

### 解除安裝後保留的內容

**解除安裝只移除程式本體**（`%LOCALAPPDATA%\MediaLauncher\`），  
**不會自動刪除**使用者資料 `%APPDATA%\MediaLauncher\`。

這是刻意設計：確保使用者不會因為重新安裝而遺失任務清單與設定。

---

## 完全清除使用者資料（手動操作）

若使用者想完全移除所有資料（設定、任務清單、縮圖快取），  
需在解除安裝後**手動刪除**以下目錄：

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\MediaLauncher"
```

或在 Windows 檔案總管中：
1. 按 `Win + R` → 輸入 `%APPDATA%`
2. 找到並刪除 `MediaLauncher` 資料夾

> ⚠️ 此操作**永久刪除**所有任務清單、資料夾設定與縮圖快取，無法復原。

---

## USB 離線發佈包

若需要在無網路環境（學校電腦）部署：

### 最小發佈包（只需要 installer）

```
USB 隨身碟\
└── MediaLauncherSetup.exe    ← 單一檔案，複製此檔即可
```

使用者雙擊 `MediaLauncherSetup.exe`，完全不需要網路或其他軟體。

### 完整發佈包（含原始 dist，方便 IT 部門審查）

```
USB 隨身碟\
├── MediaLauncherSetup.exe    ← installer（一般使用者用這個）
├── dist\
│   └── MediaLauncher\        ← PyInstaller 展開內容（IT 審查用）
│       ├── MediaLauncher.exe
│       ├── _internal\
│       └── ...
└── README.txt                ← 簡易說明
```

---

## 常見問題

### 安裝時出現 Windows SmartScreen 警告

首次從網路下載或新製作的 installer，Windows 可能顯示「Windows 保護您的電腦」：

1. 點「更多資訊」
2. 點「仍要執行」

若要消除此警告，可對 `MediaLauncherSetup.exe` 進行 **Code Signing**（數位簽名）。

### 安裝後程式無法啟動

確認 Port 8765 未被其他程式佔用：

```powershell
netstat -ano | findstr :8765
```

若有衝突，結束佔用的程式後再試。

### 程式啟動但縮圖不顯示

確認 `%LOCALAPPDATA%\MediaLauncher\tools\ffmpeg.exe` 存在。  
若無影片縮圖需求，此問題不影響其他功能（顯示 placeholder 圖示）。

### 重新安裝後任務清單不見了

不應發生此情況：重新安裝只覆蓋程式檔案，不動使用者資料。  
若確認任務清單消失，請檢查 `%APPDATA%\MediaLauncher\tasks.json` 是否存在。

### 需要更新版本

1. 執行新版 `MediaLauncherSetup.exe`
2. Inno Setup 的 `CloseApplications=yes` 會提示關閉正在執行的程式
3. 安裝完成後即為新版本
4. 使用者資料（`%APPDATA%\MediaLauncher\`）完整保留

---

## 各 Phase 完成後的完整流程

```
Phase A  修改 launcher.py  ──→  支援 frozen 模式、資料寫入 %APPDATA%
           ↓
Phase B  build_pyinstaller.ps1  ──→  dist\MediaLauncher\MediaLauncher.exe
           ↓
Phase C  build_installer.ps1  ──→  installer\MediaLauncherSetup.exe
           ↓
Phase D  說明.txt + third_party_notices.txt  ──→  使用者文件
           ↓
Phase E  實機測試（無 Python、無網路的 Windows 電腦）
```
