; MediaLauncher.iss
; Inno Setup 6 installer script for 媒體啟動器
;
; 使用前提:
;   已先執行 build\build_pyinstaller.ps1，
;   使得 dist\MediaLauncher\MediaLauncher.exe 存在。
;
; 編譯方式:
;   1. GUI:  用 Inno Setup 6 開啟本檔案，按 Build → Compile
;   2. 命令列: .\installer\build_installer.ps1
;
; 輸出: installer\MediaLauncherSetup.exe

; ────────────────────────────────────────────────────────────────────
[Setup]
; 應用程式資訊
AppName=媒體啟動器
AppVersion=1.0.0
AppPublisher=School Media Tools
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=

; 不需要管理員權限（學校行政一般使用者即可安裝）
; lowest = 永遠以目前使用者身分安裝，不要求 UAC 提示
PrivilegesRequired=lowest

; 預設安裝位置：使用者的 %LOCALAPPDATA%（無需管理員可寫入）
; 注意：這是程式本體（exe、dll）的位置
;       使用者資料（config.json、tasks.json、.thumbs）在 %APPDATA%\MediaLauncher
DefaultDirName={localappdata}\MediaLauncher
DefaultGroupName=媒體啟動器
DisableProgramGroupPage=yes

; 安裝精靈樣式
WizardStyle=modern

; 輸出設定（相對路徑：從 .iss 檔所在的 installer\ 目錄起算）
OutputDir=.
OutputBaseFilename=MediaLauncherSetup
Compression=lzma2/ultra64
SolidCompression=yes

; 安裝時若程式正在執行，提示關閉
CloseApplications=yes
CloseApplicationsFilter=MediaLauncher.exe
RestartIfNeededByRun=no

; 不需要重新開機
AlwaysRestart=no
; 版本資訊（顯示在安裝程式屬性中）
VersionInfoVersion=1.0.0.0
VersionInfoProductName=媒體啟動器

; ────────────────────────────────────────────────────────────────────
[Languages]
; Default English (ChineseTraditional.isl not available in this installation)
Name: "en"; MessagesFile: "compiler:Default.isl"

; ────────────────────────────────────────────────────────────────────
[Tasks]
; 使用者可選擇是否建立桌面捷徑（預設不勾選）
Name: "desktopicon"; \
  Description: "在桌面建立「媒體啟動器」捷徑"; \
  GroupDescription: "其他選項:"; \
  Flags: unchecked

; ────────────────────────────────────────────────────────────────────
[Files]
; ── PyInstaller one-folder 輸出（全部內容） ──────────────────────────
; 路徑相對於本 .iss 檔位置（installer\），所以 dist 在 ..\dist
; recursesubdirs: 遞迴複製子目錄（_internal\、tools\ 等）
; createallsubdirs: 在 {app} 建立對應子目錄
; ignoreversion: 覆蓋安裝時不比較版本號（單純覆蓋即可）
Source: "..\dist\MediaLauncher\*"; \
  DestDir: "{app}"; \
  Flags: recursesubdirs createallsubdirs ignoreversion

; 注意：
;   - dist\MediaLauncher\ 中已包含 config.json、tasks.json、說明.txt
;   - dist\MediaLauncher\tools\ffmpeg.exe 若存在也會一起複製
;   - dist\MediaLauncher\_internal\ 或旁邊的 .dll/.pyd 也會一起複製
;   - 不需要另外列出這些檔案

; ────────────────────────────────────────────────────────────────────
[Icons]
; 開始功能表捷徑
Name: "{group}\媒體啟動器"; \
  Filename: "{app}\MediaLauncher.exe"; \
  WorkingDir: "{app}"

; 開始功能表的解除安裝捷徑
Name: "{group}\解除安裝 媒體啟動器"; \
  Filename: "{uninstallexe}"

; 桌面捷徑（根據 [Tasks] 中 desktopicon 是否勾選）
Name: "{userdesktop}\媒體啟動器"; \
  Filename: "{app}\MediaLauncher.exe"; \
  WorkingDir: "{app}"; \
  Tasks: desktopicon

; ────────────────────────────────────────────────────────────────────
[Run]
; 安裝完成畫面提供「立即啟動」勾選選項
; nowait: 不等待程式結束（背景啟動）
; postinstall: 在安裝完成頁面顯示
; skipifsilent: 靜音安裝（/SILENT 或 /VERYSILENT 旗標）時略過
Filename: "{app}\MediaLauncher.exe"; \
  Description: "立即啟動媒體啟動器"; \
  WorkingDir: "{app}"; \
  Flags: nowait postinstall skipifsilent

; ────────────────────────────────────────────────────────────────────
; [UninstallDelete] 刻意不設定
;
; 解除安裝行為說明：
;   - Inno Setup 自動移除它所安裝的檔案（{app}\ 下的內容）
;   - 使用者資料 %APPDATA%\MediaLauncher（config.json、tasks.json、.thumbs\）
;     「不會」被自動刪除——這是刻意設計，避免誤刪使用者的任務清單
;   - 若使用者想完全清除資料，請手動刪除：
;       %APPDATA%\MediaLauncher
;   - 詳見 README-installer.md
