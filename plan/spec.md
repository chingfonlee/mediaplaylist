# 媒體啟動器 — 任務播放清單 功能規格

> 版本：v1.0　日期：2026-06-25　狀態：草稿

---

## 1. 現有架構摘要

### 1.1 專案結構

```
媒體啟動器/
├── launcher.py       # 單一 Python 檔：HTTP server + 內嵌 HTML/CSS/JS
├── config.json       # 設定檔：掃描目錄清單
├── 啟動.bat          # 啟動腳本（ASCII-only，避免 CP950 問題）
├── 說明.txt          # 使用說明
└── .thumbs/          # 縮圖快取（MD5 hash 命名，.jpg）
```

### 1.2 如何掃描檔案

- 入口：`scan(dirs, recursive=False)`（約 L42）
- 對每個目錄呼叫 `p.iterdir()` 或 `p.rglob('*')`
- 依副檔名判斷類型：`video / audio / image / pdf / ppt / doc`
- 回傳 list of dict：`{path, name, stem, type, ext, size, mtime, thumb}`
- 結果以 `mtime` 降冪排序（最新檔案優先）

### 1.3 如何開啟檔案

```python
def open_file(path):
    if sys.platform == 'win32':
        os.startfile(path)   # 呼叫 Windows 預設程式，非阻塞
```

- 完全非同步：Python 無法知道外部程式何時關閉
- 這是 **v1 不支援「播完自動跳下一個」** 的根本限制

### 1.4 前端如何呈現檔案卡片

- `reload()` → `GET /api/files` → `allFiles[]`
- `filterRender()` 過濾 type / 搜尋關鍵字 / checkedDirs
- `showGrid(files)` 動態建立 `.card` DOM 元素
- 每張卡片有縮圖區（`ph-{type}` 漸層底圖）＋卡片體（檔名、類型徽章、大小、日期）
- 點擊卡片 → `openFile(path)` → `GET /api/open?path=...`

### 1.5 設定如何保存

- `config.json`：`{"dirs": [...], "recursive": false}`
- `load_cfg()` / `save_cfg(cfg)` 直接讀寫 UTF-8 JSON
- 寫入時**無暫存檔保護**（現況風險，新功能需改善）

---

## 2. 新功能目標

### 2.1 右側任務區塊（Task Sidebar）

- 畫面右側固定寬度側欄（預設 `280px`，可拖曳調寬）
- 可摺疊（按鈕切換），摺疊時左側媒體區佔滿寬度
- 側欄頂部：任務選擇器（下拉選單 + 新增按鈕）
- 側欄主體：當前任務的有序播放清單
- 側欄底部：「播放當前」按鈕 + 項目計數

### 2.2 任務管理

| 操作 | 說明 |
|------|------|
| 新增任務 | 點「＋」→ 輸入名稱 → 建立空任務 |
| 改名任務 | 雙擊任務名稱 → inline 編輯 → Enter 確認 |
| 刪除任務 | 任務選單旁的「⋯」選單 → 刪除 → 確認對話框 |
| 切換任務 | 下拉選單選擇 → 側欄即時切換顯示 |

### 2.3 從媒體卡片拖曳加入任務

- 左側卡片設定 `draggable="true"`
- 拖曳開始：卡片輕微縮小＋半透明（視覺回饋）
- 拖曳進入側欄：側欄高亮顯示 drop zone
- 放開：呼叫 `addItemToTask(path, name, type, ext)`
- 若已在清單中：toast 提示「已在清單中（#N）」，不重複加入
- **點擊卡片不受影響**：`click` 與 `dragstart` 共存，dragstart 需移動超過 5px 才觸發

### 2.4 任務內拖曳重排

- 清單項目左側顯示拖曳把手（`⠿` 圖示）
- 使用 HTML5 Drag and Drop API（與外部拖曳同一套，用 `dataTransfer` type 區分）
- 放下後：立即更新 DOM 順序，並呼叫 `POST /api/tasks/save-items` 持久化

### 2.5 刪除任務中的單一項目

- 每個清單項目右側有「✕」按鈕（hover 才顯示）
- 點擊立即移除，無需確認（可 Ctrl+Z 撤銷，v1 不實作）
- 移除後自動存檔

### 2.6 點擊任務項目播放

- 點擊項目 → `GET /api/open?path=...`（與卡片行為相同）
- 同時更新該任務的 `currentIndex`（記住播放位置）
- 若檔案不存在：項目標示紅色警告圖示，點擊無效，tooltip 顯示路徑

### 2.7 可選功能（v1 低優先）

- 「播放下一個」按鈕：開啟 `currentIndex + 1` 的檔案
- 記住播放位置：`currentIndex` 存入 `tasks.json`，重開瀏覽器後恢復

---

## 3. 非目標（v1 明確排除）

- ❌ 自動偵測外部播放器是否播放完畢（`os.startfile` 非阻塞，無法得知）
- ❌ 內建影片/音樂播放器（需要大幅重構）
- ❌ 跨裝置同步或雲端備份
- ❌ 資料庫（SQLite 等）
- ❌ 播放清單匯入/匯出（.m3u 等）
- ❌ 鍵盤快捷鍵控制播放順序

---

## 4. 資料模型設計

### 4.1 新增 `tasks.json`

路徑：`C:\Users\user\Desktop\媒體啟動器\tasks.json`（與 `config.json` 同層）

```json
{
  "activeTaskId": "t_1750000000000",
  "tasks": [
    {
      "id": "t_1750000000000",
      "name": "學校開學演講",
      "currentIndex": 1,
      "items": [
        {
          "path": "C:\\Users\\user\\Desktop\\開學簡報.pptx",
          "name": "開學簡報.pptx",
          "stem": "開學簡報",
          "type": "ppt",
          "ext": "PPTX"
        },
        {
          "path": "C:\\Users\\user\\Videos\\開場影片.mp4",
          "name": "開場影片.mp4",
          "stem": "開場影片",
          "type": "video",
          "ext": "MP4"
        },
        {
          "path": "C:\\Users\\user\\Music\\背景音樂.mp3",
          "name": "背景音樂.mp3",
          "stem": "背景音樂",
          "type": "audio",
          "ext": "MP3"
        }
      ]
    },
    {
      "id": "t_1750000001000",
      "name": "畢業典禮",
      "currentIndex": 0,
      "items": []
    }
  ]
}
```

### 4.2 欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `activeTaskId` | string \| null | 目前選中的任務 ID；null = 無任務 |
| `tasks[].id` | string | `"t_" + Date.now()` 毫秒時間戳，全域唯一 |
| `tasks[].name` | string | 使用者命名，允許中文，長度上限 50 字元 |
| `tasks[].currentIndex` | int | 上次點擊播放的項目索引，0-based；-1 = 未播放 |
| `tasks[].items[].path` | string | 完整 Windows 絕對路徑（含中文亦可） |
| `tasks[].items[].name` | string | 檔案名（含副檔名），顯示用 |
| `tasks[].items[].stem` | string | 檔案名（不含副檔名），顯示用 |
| `tasks[].items[].type` | string | `video/audio/image/pdf/ppt/doc` |
| `tasks[].items[].ext` | string | 大寫副檔名，如 `"PPTX"` |

### 4.3 `path` 是否足夠作為識別鍵

**夠用，但需處理邊界情況：**

- 同一檔案不應在同一任務中出現兩次 → 加入時用 `path` 去重
- 檔案被移動後 path 失效 → UI 顯示警告，不自動移除（使用者手動清理）
- 中文路徑：`os.startfile()` 在 Windows 支援中文路徑，API 傳輸使用 `encodeURIComponent`

### 4.4 檔案不存在時的 UI 處理

```
[ ⚠ ]  開場影片.mp4          ✕
        路徑已無效，點此移除
```

- 項目變灰＋警告圖示
- 點擊項目：不觸發開啟，改為 toast 提示「檔案不存在：{path}」
- `GET /api/tasks` 回應時，後端可附加 `"exists": false` 欄位（可選，也可純前端判斷）

---

## 5. 後端 API 設計

所有 task API 讀寫 `tasks.json`；寫入時使用**暫存檔 + rename** 保護：

```python
def save_tasks(data):
    tmp = TASKS_F.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
    tmp.replace(TASKS_F)   # atomic on same filesystem
```

---

### `GET /api/tasks`

回傳完整 tasks.json 內容。

**Response**
```json
{
  "activeTaskId": "t_1750000000000",
  "tasks": [ { ...同上述資料模型... } ]
}
```

---

### `POST /api/tasks/create`

建立新任務。

**Request**
```json
{ "name": "學校開學演講" }
```

**Response**
```json
{
  "ok": true,
  "task": {
    "id": "t_1750000000000",
    "name": "學校開學演講",
    "currentIndex": -1,
    "items": []
  }
}
```

**驗證**：`name` 不可為空；長度上限 50 字元；同名任務允許存在（不強制唯一）。

---

### `POST /api/tasks/rename`

**Request**
```json
{ "id": "t_1750000000000", "name": "新名稱" }
```

**Response**
```json
{ "ok": true }
```

**錯誤**：`id` 不存在 → `{"ok": false, "err": "task not found"}`

---

### `POST /api/tasks/delete`

**Request**
```json
{ "id": "t_1750000000000" }
```

**Response**
```json
{ "ok": true, "activeTaskId": "t_1750000001000" }
```

邏輯：刪除後若 `activeTaskId` 指向被刪任務，改指向清單第一個；若清單變空則設為 `null`。

---

### `POST /api/tasks/save-items`

儲存某任務的完整項目清單（拖曳排序後呼叫）。

**Request**
```json
{
  "id": "t_1750000000000",
  "items": [
    {
      "path": "C:\\Users\\user\\Desktop\\開學簡報.pptx",
      "name": "開學簡報.pptx",
      "stem": "開學簡報",
      "type": "ppt",
      "ext": "PPTX"
    }
  ]
}
```

**Response**
```json
{ "ok": true }
```

注意：前端傳送**完整有序清單**，後端整個取代，不做 diff merge。

---

### `POST /api/tasks/set-active`

切換當前任務。

**Request**
```json
{ "id": "t_1750000000000" }
```

**Response**
```json
{ "ok": true }
```

---

### `POST /api/tasks/set-current`（可選）

記住目前播放位置。

**Request**
```json
{ "id": "t_1750000000000", "index": 2 }
```

**Response**
```json
{ "ok": true }
```

---

## 6. 前端 UI/UX 設計

### 6.1 版面配置變更

```
┌─────────────────────────────────────────────────────────────┐
│ topbar（搜尋、分頁、資料夾、重整）               [📋 任務] │
├─────────────────────────────────────────────────────────────┤
│ folderbar（可摺疊）                                          │
├───────────────────────────────────────┬─────────────────────┤
│                                       │  任務側欄 280px      │
│  媒體網格（flex:1，可捲動）           │  （可摺疊）          │
│                                       │                      │
│  [card][card][card]                   │  [任務選擇器 ▼] [+] │
│  [card][card][card]                   │  ─────────────────  │
│                                       │  1. 開學簡報.pptx   │
│                                       │  2. 開場影片.mp4    │
│                                       │  3. 背景音樂.mp3    │
│                                       │  ─────────────────  │
│                                       │  [▶ 播放 #1]  3項   │
└───────────────────────────────────────┴─────────────────────┘
```

- 側欄以 CSS `flex` 實現，`min-width:0` 讓媒體區能縮小
- topbar 右側加「📋 任務」切換按鈕，與「📁 資料夾」並排

### 6.2 任務選擇器

```html
<div class="task-header">
  <select id="taskSelect" onchange="switchTask(this.value)">
    <option value="t_xxx">學校開學演講 (3)</option>
    <option value="t_yyy">畢業典禮 (0)</option>
  </select>
  <button onclick="createTask()" title="新增任務">＋</button>
  <button onclick="showTaskMenu()" title="任務選項">⋯</button>
</div>
```

- 選項格式：`{任務名稱} ({項目數})`
- 「⋯」選單包含：改名、刪除

### 6.3 播放清單項目樣式

```
┌─────────────────────────────────────────────────┐
│ ⠿  🎬  開場影片.mp4                         ✕  │  ← 一般
│ ⠿  📊  開學簡報.pptx   ◀ 目前              ✕  │  ← 當前播放
│ ⠿  ⚠   消失的檔案.mp4  [路徑已無效]        ✕  │  ← 遺失
└─────────────────────────────────────────────────┘
```

CSS class：
- `.task-item` — 基本樣式
- `.task-item.current` — 藍色左邊框，標示當前位置
- `.task-item.missing` — 紅色，半透明
- `.task-item .drag-handle` — `cursor: grab`，hover 才顯示
- `.task-item .remove-btn` — hover 才顯示

### 6.4 拖曳互動設計

#### 從媒體卡片拖曳到側欄

```javascript
// 卡片設定
card.draggable = true;
card.addEventListener('dragstart', e => {
  e.dataTransfer.setData('application/x-media-item', JSON.stringify({
    path: f.path, name: f.name, stem: f.stem, type: f.type, ext: f.ext
  }));
  e.dataTransfer.effectAllowed = 'copy';
  card.classList.add('dragging');
});
card.addEventListener('dragend', () => card.classList.remove('dragging'));

// 防止拖曳觸發 click：只有在 dragstart 後 mouseup 不觸發 click
let isDragging = false;
card.addEventListener('dragstart', () => isDragging = true);
card.addEventListener('click', e => { if (isDragging) { isDragging = false; return; } openFile(f.path); });
```

#### 側欄 Drop Zone

```javascript
taskList.addEventListener('dragover', e => {
  if (e.dataTransfer.types.includes('application/x-media-item')) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    taskList.classList.add('drop-target');
  }
});
taskList.addEventListener('drop', e => {
  const item = JSON.parse(e.dataTransfer.getData('application/x-media-item'));
  addItemToActiveTask(item);
});
```

#### 清單內部重排

- 使用 `application/x-task-reorder` dataTransfer type 區分
- 記錄 `dragoverIndex` 並顯示插入線（`::before` 偽元素）
- drop 後呼叫 `saveItems()`

### 6.5 空狀態與邊界情況

| 狀態 | 顯示 |
|------|------|
| 無任何任務 | 側欄顯示「尚無任務，點「＋」新增」 |
| 任務為空 | 清單區顯示「拖曳左側媒體加入清單」＋虛線框 drop zone |
| 拖曳進入空清單 | drop zone 高亮放大 |
| 檔案遺失 | 項目紅色警告，點擊顯示 toast 不開啟檔案 |
| 刪除任務確認 | `confirm("確定刪除「{name}」？清單內容將一併移除。")` |
| 加入重複項目 | toast「已在清單 #N 位，不重複加入」 |

### 6.6 小螢幕（< 900px）

- 側欄預設**摺疊**，`[📋 任務]` 按鈕作為唯一入口
- 展開時側欄以 `position:fixed` 覆蓋右側，背景半透明遮罩
- 點遮罩可關閉側欄

---

## 7. 實作計畫

### Phase 1 — 後端 + 資料層（可獨立測試）

**修改檔案：`launcher.py`（Python 部分）**

1. 新增常數 `TASKS_F = SCRIPT / "tasks.json"`
2. 實作 `load_tasks()` / `save_tasks(data)`（含暫存檔保護）
3. 新增 6 個 POST endpoints（`/api/tasks/*`）
4. 新增 `GET /api/tasks`

**驗證方式：**
```powershell
# 啟動 server 後用 curl 測試
curl -X POST http://localhost:8765/api/tasks/create `
     -H "Content-Type: application/json" `
     -d '{"name":"測試任務"}'
# 應回傳 {"ok":true,"task":{"id":"t_...","name":"測試任務",...}}

curl http://localhost:8765/api/tasks
# 應回傳包含剛建立任務的 JSON
```

---

### Phase 2 — 側欄 HTML/CSS 骨架

**修改檔案：`launcher.py`（HTML/CSS 部分）**

1. 主體 layout 改為 `display:flex;flex-direction:row`
2. 加入 `<div id="taskSidebar" class="task-sidebar hidden">` 骨架
3. topbar 加入「📋 任務」按鈕
4. 加入完整 sidebar CSS（含動畫、響應式）

**驗證方式：** 重啟 server，確認「📋 任務」按鈕可展開/摺疊側欄，媒體網格能正常縮排。

---

### Phase 3 — 任務管理 UI

**修改檔案：`launcher.py`（JS 部分）**

1. `loadTasks()` — 初始化時呼叫 `GET /api/tasks`，填入 `taskState`
2. `renderTaskSidebar()` — 根據 `taskState` 渲染選擇器 + 清單
3. `createTask()` — prompt 輸入名稱，呼叫 API，重渲染
4. `switchTask(id)` — 呼叫 `set-active`，重渲染清單
5. `renameTask()` / `deleteTask()` — 對應 API 呼叫

**驗證方式：** 可新增、改名、切換、刪除任務，頁面重整後狀態保留。

---

### Phase 4 — 拖曳功能

**修改檔案：`launcher.py`（JS 部分）**

1. `showGrid()` 中為每張卡片加 `draggable=true` 和 dragstart/dragend handler
2. 側欄加 dragover/dragleave/drop handlers
3. `addItemToActiveTask(item)` — 去重後呼叫 `save-items`，重渲染
4. 清單項目加內部重排 drag handlers
5. 加入拖曳視覺回饋（ghost、drop zone 高亮、插入線）

**驗證方式：**
- 拖曳卡片到側欄，項目出現在清單
- 拖曳重排，順序持久化（重整後順序不變）
- 點擊卡片（不拖曳）仍能正常開啟檔案

---

### Phase 5 — 播放與狀態

**修改檔案：`launcher.py`（JS 部分）**

1. 點擊清單項目 → `openFile(path)` + 更新 `currentIndex`
2. 呼叫 `POST /api/tasks/set-current`
3. 「播放下一個」按鈕邏輯
4. 遺失檔案偵測（可在 `renderTaskSidebar` 時用 `fetch('/api/open?path=...')` 預檢，或純 UI 標示等實際點擊才判斷）

**驗證方式：** 點擊清單項目開啟檔案，`currentIndex` 標示正確，重整後標示保留。

---

## 8. 風險與注意事項

### 8.1 `os.startfile()` 無法偵測播放結束

- **影響**：v1 無法自動跳下一個
- **緩解**：提供「播放下一個 ▶▶」按鈕，由使用者手動觸發
- **未來**：可考慮監聽特定播放器的 IPC（如 VLC HTTP API），但超出 v1 範圍

### 8.2 Windows 中文路徑

- `os.startfile()` 支援中文路徑 ✅
- HTTP API 傳輸：前端用 `encodeURIComponent(path)`，後端用 `urllib.parse.unquote()`
- `tasks.json` 寫入：`ensure_ascii=False` 保留中文字元 ✅
- **潛在問題**：路徑含 `#` 或 `?` 字元時 URL 解析會出錯 → 建議 POST body 傳 path，不用 query string

### 8.3 拖曳不能破壞卡片點擊

- 問題：`dragstart` 和 `click` 同時設在卡片上，拖曳後可能觸發 `click`
- **解法**：`dragstart` 設 flag `isDragging=true`，`mouseup` 後延遲 0ms 重置；`click` handler 檢查 flag
- 測試：在觸控螢幕（若有）也需驗證

### 8.4 tasks.json 損壞保護

```python
def save_tasks(data):
    tmp = TASKS_F.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
        tmp.replace(TASKS_F)   # Windows 上 replace() 是 atomic（同磁碟）
    except Exception as e:
        if tmp.exists(): tmp.unlink()
        raise

def load_tasks():
    if TASKS_F.exists():
        try:
            return json.loads(TASKS_F.read_text('utf-8'))
        except json.JSONDecodeError:
            # 嘗試讀取備份
            pass
    return {"activeTaskId": None, "tasks": []}
```

### 8.5 同名任務的 ID 設計

- 使用 `"t_" + int(time.time() * 1000)` 作為 ID
- Python 後端生成（不在前端生成），避免時鐘問題
- 極罕見的毫秒碰撞：在 `create` endpoint 中加 while 迴圈確保唯一

### 8.6 拖曳至側欄的效能

- 每次 drop 呼叫 `save-items`，若清單很長（>100項）每次儲存整份
- v1 可接受；若未來有問題，改為 debounce 儲存

### 8.7 瀏覽器 Drag and Drop API 限制

- Firefox 不支援 `setDragImage()` 的某些用法 → 使用預設 ghost 即可
- 在 `dragover` 必須呼叫 `e.preventDefault()` 才能觸發 `drop` → 必要步驟勿省略

---

## 附錄：前端狀態物件設計

```javascript
// 全域狀態
let taskState = {
  activeTaskId: null,   // string | null
  tasks: [],            // Task[]
};

// 查詢工具
const activeTask = () =>
  taskState.tasks.find(t => t.id === taskState.activeTaskId) || null;

const taskById = id =>
  taskState.tasks.find(t => t.id === id) || null;
```

此物件在 `loadTasks()` 初始化，每次 API 呼叫成功後同步更新，再呼叫 `renderTaskSidebar()` 重渲染。**單向資料流**：API → taskState → DOM，DOM 不直接修改 taskState。
