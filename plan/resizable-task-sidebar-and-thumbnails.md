# 媒體啟動器 — 可調寬 Sidebar ＋ 任務縮圖卡片 規格

> 版本：v1.0　日期：2026-06-25　狀態：草稿

---

## 1. 現況摘要

### 1.1 `.task-sidebar` 寬度設定（CSS，約 L458）

```css
.task-sidebar{
  width:280px;          /* 硬編碼，無法動態調整 */
  flex-shrink:0;
  transition:width .2s; /* 用於開關動畫；resize 時必須暫停 */
}
.task-sidebar.hidden{ width:0; border-left:none; overflow:hidden }
@media(max-width:900px){
  .task-sidebar:not(.hidden){
    position:fixed; right:0; top:0; bottom:0; z-index:300;
    /* 小螢幕時 overlay 模式，width 仍是 280px */
  }
}
```

### 1.2 `.task-list` 與 `.task-item` 呈現方式（CSS，約 L480–L516）

目前是純文字列表（list mode）：

```
[ N ]  [ 類型 emoji ]  [ 檔名（ellipsis）]  [ ✕ ]
```

每個 `.task-item` 是一個 `display:flex` row，高度約 34px。不含縮圖。
- `.ti-num`：序號，11px muted，min-width 18px
- `.ti-icon`：類型 emoji，14px
- `.ti-name`：檔名，12.5px，overflow ellipsis，flex:1
- `.ti-remove`：✕，hover 才顯示

### 1.3 拖曳加入與任務內重排（JS，約 L780–L1280）

**兩種拖曳類型以 dataTransfer type 區分：**
- `MEDIA_DRAG_TYPE = 'application/x-media-item'`：左側卡片拖到 sidebar
- `TASK_DRAG_TYPE  = 'application/x-task-reorder'`：sidebar 內重排

**拖曳加入流程：**
1. 左側卡片 `dragstart` → 設 `MEDIA_DRAG_TYPE`
2. `#taskList` 的 `dragover` 判斷 type → `drop-over` class
3. 若 drop 在空清單 → `addItemToActiveTask(item, null)`（append）
4. 若 drop 在現有 `.task-item` 上 → `dropOnTaskItem(e, index)` 判斷上下半

**重排流程：**
1. `.task-item` 本身 `draggable="true"`
2. `startTaskItemDrag(e, index)` → 設 `TASK_DRAG_TYPE` + `draggingTaskIndex`
3. `overTaskItem(e, index)` → 依 `e.clientY` 與 `getBoundingClientRect()` top/bottom half 設 `.drag-over-top/.drag-over-bot`
4. `dropOnTaskItem(e, index)` → 計算 `targetIndex = index + (after ? 1 : 0)` → `moveTaskItem(from, to)`
5. `endTaskItemDrag()` → 清除所有 drag class

**重要**：`dropOnTaskItem` 用 `e.clientY` 判斷插入位置。改成卡片模式後，高度變大（從 ~34px 到 ~80px），此邏輯仍可用，無需修改。

### 1.4 縮圖資料來源（JS `showGrid()` 區段）

左側媒體卡片使用：
```javascript
f.thumb     // 縮圖 key → GET /api/thumb?key=...（MD5.jpg）
f.img_url   // 僅 image 類型、無 Pillow 時設為 /api/img?path=...
// fallback：placeholderHtml(type, ext)
```

`allFiles` array 在 `reload()` 時填入，每個 file object 包含 `{path, thumb, img_url, type, ext, stem, name, ...}`。

task item 存的是 `{path, name, stem, type, ext}`，**不含** `thumb/img_url`。

---

## 2. 功能目標

### 2.1 可調寬 Sidebar

- sidebar 左側加一條 resize handle（視覺上約 4–6px 寬）
- 滑鼠按住 handle 拖曳 → sidebar 即時改寬
- 寬度有 min/max 限制（詳見第 3 節）
- 寬度存入 `localStorage['taskSidebarWidth']`，下次開啟恢復
- `transition:width .2s` 只在開關時有效；resize 期間停用（避免拖曳延遲感）

### 2.2 任務項目縮圖化（card mode）

- sidebar 寬度 ≥ 420px 時切換成 compact card mode
- card mode 每項高度約 64px，含縮圖（左）＋文字資訊（右）
- 縮圖從 `allFiles` 依 path 對照取得，找不到則用 placeholder
- **不** 把 thumb 存入 `tasks.json`（避免快取失效與資料膨脹）

---

## 3. 建議尺寸

| 參數 | 建議值 | 理由 |
|------|--------|------|
| `TASK_SB_MIN` | 240px | 低於此寬度 list mode 也難顯示檔名 |
| `TASK_SB_DEFAULT` | 320px | 比目前 280px 略寬，card mode 有空間 |
| `TASK_SB_MAX` | `min(640, window.innerWidth * 0.5)` | 不超過視窗一半，避免壓縮左側 grid 過多 |
| list → card 切換點 | 420px | 可容下 64px 高卡片的縮圖＋文字 |

### 小螢幕（< 900px）

sidebar 在此模式下已是 `position:fixed` overlay，不佔媒體 grid 空間。

**建議：**
- resize 功能在小螢幕仍啟用（固定 overlay 也可調寬，不影響 grid）
- `TASK_SB_MAX` 小螢幕改為 `min(640, window.innerWidth - 40)` 避免 handle 超出螢幕

---

## 4. UI/UX 設計

### 4.1 Resize Handle

```
┌──────────────────────────────────────────────────────────────┐
│         media grid                  │▌│  task sidebar         │
│         (flex:1, shrinks)           │▌│                       │
│                                     │▌│                       │
└──────────────────────────────────────┴─┴───────────────────── ┘
                                       ↑
                               .task-resize-handle
                               (4px wide, sits INSIDE sidebar,
                                at left edge via position:absolute)
```

**CSS：**
```css
.task-resize-handle {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  cursor: col-resize;
  background: transparent;
  transition: background .15s;
  z-index: 10;
}
.task-resize-handle:hover,
.task-sidebar.resizing .task-resize-handle {
  background: var(--accent);
}
```

**實作位置**：`.task-sidebar` 需設 `position:relative`，handle 放在 sidebar HTML 的第一個子元素。

### 4.2 拖曳中防止文字選取

```css
body.resizing-task-sb {
  user-select: none;
  cursor: col-resize;
}
```

`mousemove` handler 中檢查 `document.body.classList.contains('resizing-task-sb')`，只有在 resize 狀態才更新寬度。

### 4.3 `transition` 控制

- `toggleTaskSidebar()` 開關時：加 `is-toggling` class → CSS 設 `transition:width .2s`
- resize 拖曳時：不加 `is-toggling` → 無 transition（即時響應）

具體做法：
```css
.task-sidebar          { transition: none; }   /* 預設無動畫 */
.task-sidebar.toggling { transition: width .2s; }
```

```javascript
function toggleTaskSidebar() {
  const sb = document.getElementById('taskSidebar');
  sb.classList.add('toggling');
  sb.addEventListener('transitionend', () => sb.classList.remove('toggling'), {once:true});
  sb.classList.toggle('hidden');
  // ...
}
```

### 4.4 雙擊 Handle 重設寬度（可選，建議實作）

```javascript
handle.addEventListener('dblclick', () => {
  setTaskSidebarWidth(TASK_SB_DEFAULT);
  localStorage.setItem('taskSidebarWidth', TASK_SB_DEFAULT);
});
```

### 4.5 無障礙

```html
<div class="task-resize-handle"
     role="separator"
     aria-orientation="vertical"
     aria-label="調整任務側欄寬度"
     title="拖曳調整寬度，雙擊恢復預設">
</div>
```

---

## 5. 任務項目縮圖化設計

### 5.1 縮圖來源 Lookup Helper

`allFiles` 在每次 `reload()` 後都是最新狀態。task item 只存 `path`，render 時做對照：

```javascript
// Build a lookup map after reload()
let fileMap = new Map(); // path → file object
function rebuildFileMap() {
  fileMap = new Map(allFiles.map(f => [f.path, f]));
}

function getTaskItemVisual(item) {
  const f = fileMap.get(item.path);
  if (!f) return { thumb: null, img_url: null, type: item.type, ext: item.ext, missing: true };
  return { thumb: f.thumb, img_url: f.img_url, type: f.type, ext: f.ext, missing: false };
}
```

`rebuildFileMap()` 在 `reload()` 完成後呼叫，`renderTaskSidebar()` 也在 `reload()` 後重呼叫，確保一致性。

**為什麼不存 thumb 到 tasks.json？**

| 存入 tasks.json | 動態 lookup |
|-----------------|-------------|
| 跨 session 有縮圖（不需 reload） | 需先 reload 才有縮圖 |
| 檔案修改後縮圖 key 過期，顯示壞圖 | 始終反映最新 mtime |
| tasks.json 膨脹（每個 item 多 64 char MD5） | tasks.json 乾淨 |
| 縮圖刪除後需手動清理 tasks.json | 無此問題 |

**結論：動態 lookup，不存入 tasks.json。**

### 5.2 View Mode 判斷

```javascript
let taskItemViewMode = 'list'; // 'list' | 'card'

function updateTaskViewMode() {
  const sb = document.getElementById('taskSidebar');
  const w  = sb.offsetWidth;
  const next = w >= 420 ? 'card' : 'list';
  if (next !== taskItemViewMode) {
    taskItemViewMode = next;
    renderTaskSidebar();
  }
}
```

呼叫時機：
1. `setTaskSidebarWidth()` 中呼叫
2. `window.addEventListener('resize', updateTaskViewMode)`
3. `loadTasks()` 初始化後呼叫一次

### 5.3 List Mode 項目（現況，維持不變）

```
[ N ]  [ 📊 ]  [ 開學簡報（ellipsis）]  [ ✕ ]
```

高度 ~34px，精簡，適合窄 sidebar。

### 5.4 Card Mode 項目

```
┌──────────────────────────────────────────────────────┐
│  [ 縮圖 56×40 ]  開學簡報              [ 📊 PPTX ]  │
│                  2026/06/25                      [ ✕ ]│
└──────────────────────────────────────────────────────┘
  ← 序號在縮圖左上角 overlay（小圓角 badge） →
```

HTML 結構（card mode）：

```html
<div class="task-item task-item-card [current] [missing]"
     data-index="0" draggable="true"
     onclick="playTaskItem(0)"
     ondragstart="startTaskItemDrag(event,0)"
     ondragover="overTaskItem(event,0)"
     ondragleave="clearTaskDropMarks(event)"
     ondrop="dropOnTaskItem(event,0)"
     ondragend="endTaskItemDrag()">
  <div class="ti-card-thumb ph-ppt">
    <span class="ti-card-num">1</span>
    <img src="/api/thumb?key=..." alt="" loading="lazy"
         onerror="this.parentElement.innerHTML=compactPlaceholder('ppt','PPTX')">
  </div>
  <div class="ti-card-body">
    <div class="ti-card-name">開學簡報</div>
    <div class="ti-card-meta">
      <span class="type-badge tb-ppt">PPTX</span>
      <span class="ti-card-date">2026/06/25</span>
    </div>
  </div>
  <span class="ti-remove" onclick="removeTaskItem(event,0)" title="移除">✕</span>
</div>
```

CSS 新增：

```css
/* Card mode 項目 */
.task-item-card {
  padding: 8px 10px;
  gap: 10px;
  align-items: flex-start;
}
.ti-card-thumb {
  position: relative;
  width: 64px; height: 44px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surf2);
}
.ti-card-thumb img {
  width: 100%; height: 100%;
  object-fit: cover;
}
.ti-card-num {
  position: absolute;
  top: 3px; left: 4px;
  font-size: 10px; font-weight: 700;
  color: #fff;
  background: rgba(0,0,0,.55);
  border-radius: 3px;
  padding: 1px 4px;
  line-height: 1.4;
  pointer-events: none;
}
.ti-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ti-card-name {
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}
.ti-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
}
/* Compact placeholder for card thumbs */
.ti-card-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
```

### 5.5 `getTaskItemVisual` 完整實作

```javascript
function getTaskItemVisual(item) {
  const f = fileMap.get(item.path);
  const missing = !f;
  return {
    thumb:   f?.thumb   ?? null,
    img_url: f?.img_url ?? null,
    type:    f?.type    ?? item.type ?? 'doc',
    ext:     f?.ext     ?? item.ext  ?? '',
    missing
  };
}
```

`compactPlaceholder(type, ext)` — 簡化版 placeholder（emoji 放大，無文字）：
```javascript
function compactPlaceholder(type, ext) {
  const icons = {video:'🎬',audio:'🎵',image:'🖼',pdf:'📄',ppt:'📊',doc:'📝'};
  return `<div class="ti-card-placeholder ph-${type}">
    <span>${icons[type]||'📁'}</span>
  </div>`;
}
```

---

## 6. Layout 策略

### 6.1 兩種模式比較

| | List Mode | Card Mode |
|---|-----------|-----------|
| 觸發條件 | sidebar < 420px | sidebar ≥ 420px |
| 每項高度 | ~34px | ~64px |
| 縮圖 | 無（emoji icon） | 64×44px 縮圖 |
| 適合場景 | 快速確認清單 | 視覺識別媒體內容 |
| 拖曳 | 相同邏輯 | 相同邏輯（target 更高 → 更好點擊） |

### 6.2 切換方式

**建議：自動根據寬度切換（不提供手動按鈕）**

理由：
- 手動切換多一個操作成本
- 使用者拖曳調寬本身就是「我想看更多」的意圖表達
- 自動切換更直覺，且 breakpoint（420px）是合理的視覺臨界點

若未來需要，可在 footer 加一個小按鈕強制切換，但 v1 不實作。

### 6.3 不同寬度下的 Card Mode 呈現

```
240px (min, list mode):  [ N ][ icon ][ name ellipsis ][ ✕ ]

320px (default, list):   同上，較寬的 name 欄位

420px (card mode 觸發):
  [ 縮圖 ] name
             PPTX  2026/06/25           ✕

640px (max, card mode):
  [ 縮圖 ] name（更長）
             PPTX  2026/06/25           ✕
```

card mode 寬度拉大時，`ti-card-name` 自然展開，不需額外處理。

---

## 7. 實作計畫

### Phase A：可調寬 Sidebar（核心機制）

**HTML：**
- 在 `<div class="task-sidebar hidden" id="taskSidebar">` 的第一個子元素加入：
  ```html
  <div class="task-resize-handle" id="taskResizeHandle"
       role="separator" aria-orientation="vertical"
       aria-label="調整任務側欄寬度" title="拖曳調整寬度，雙擊恢復預設"></div>
  ```

**CSS：**
- `.task-sidebar` 加 `position:relative`，移除 `transition:width .2s`
- `.task-sidebar.toggling` 加 `transition:width .2s`
- 加 `.task-resize-handle` 樣式（見第 4.1 節）
- 加 `body.resizing-task-sb { user-select:none; cursor:col-resize }`

**JavaScript（新增函式）：**
```javascript
const TASK_SB_MIN     = 240;
const TASK_SB_DEFAULT = 320;
const TASK_SB_MAX_ABS = 640;

function clampTaskSidebarWidth(px) {
  const maxDyn = Math.min(TASK_SB_MAX_ABS, Math.floor(window.innerWidth * 0.5));
  return Math.max(TASK_SB_MIN, Math.min(maxDyn, px));
}

function setTaskSidebarWidth(px) {
  const w  = clampTaskSidebarWidth(px);
  const sb = document.getElementById('taskSidebar');
  sb.style.width = w + 'px';
  updateTaskViewMode();
}

function initTaskSidebarResize() {
  const handle = document.getElementById('taskResizeHandle');
  if (!handle) return;
  let startX, startW;

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startX = e.clientX;
    startW = document.getElementById('taskSidebar').offsetWidth;
    document.body.classList.add('resizing-task-sb');
    document.getElementById('taskSidebar').classList.add('resizing');
  });

  document.addEventListener('mousemove', e => {
    if (!document.body.classList.contains('resizing-task-sb')) return;
    const delta = startX - e.clientX;   // drag left = wider
    setTaskSidebarWidth(startW + delta);
  });

  document.addEventListener('mouseup', () => {
    if (!document.body.classList.contains('resizing-task-sb')) return;
    document.body.classList.remove('resizing-task-sb');
    document.getElementById('taskSidebar').classList.remove('resizing');
    const w = document.getElementById('taskSidebar').offsetWidth;
    localStorage.setItem('taskSidebarWidth', w);
  });

  handle.addEventListener('dblclick', () => {
    setTaskSidebarWidth(TASK_SB_DEFAULT);
    localStorage.setItem('taskSidebarWidth', TASK_SB_DEFAULT);
  });
}
```

**後端 API 變更：無**

---

### Phase B：localStorage 寬度保存

**JavaScript（新增函式）：**
```javascript
function loadTaskSidebarWidth() {
  const raw = localStorage.getItem('taskSidebarWidth');
  const px  = raw ? parseInt(raw, 10) : TASK_SB_DEFAULT;
  // clamp handles NaN and out-of-range values
  setTaskSidebarWidth(isNaN(px) ? TASK_SB_DEFAULT : px);
}
```

**呼叫時機：**
```javascript
async function init() {
  loadTaskSidebarWidth();              // ← 加這行（sidebar 開關後 width 才生效）
  await Promise.all([reload(), loadTasks()]);
  initTaskSidebarResize();             // ← 加這行
}
```

**注意**：`loadTaskSidebarWidth()` 在 sidebar 隱藏時也設定 `style.width`，`toggleTaskSidebar()` 開啟後 CSS `hidden` 移除，width 即生效。

**後端 API 變更：無**

---

### Phase C：縮圖 Lookup Helper

**JavaScript：**

1. 在 `allFiles` / `allDirs` 宣告旁加：
   ```javascript
   let fileMap = new Map(); // path → file object (rebuilt after each reload)
   ```

2. `reload()` 成功後加：
   ```javascript
   rebuildFileMap();
   renderTaskSidebar(); // re-render with new thumb data
   ```

3. 新增：
   ```javascript
   function rebuildFileMap() {
     fileMap = new Map(allFiles.map(f => [f.path, f]));
   }
   function getTaskItemVisual(item) { /* 見 5.5 節 */ }
   function compactPlaceholder(type, ext) { /* 見 5.5 節 */ }
   ```

**後端 API 變更：無**

---

### Phase D：任務項目 Compact Card Layout

**JavaScript：**

1. 在全域加 `let taskItemViewMode = 'list';`
2. 加 `updateTaskViewMode()` 函式
3. 修改 `renderTaskSidebar()` 中的 item render 邏輯：

```javascript
// 在 renderTaskSidebar() 的 items.map 中
list.innerHTML = items.map((item, i) => {
  if (taskItemViewMode === 'card') {
    return renderTaskItemCard(item, i, task.currentIndex);
  } else {
    return renderTaskItemList(item, i, task.currentIndex);
  }
}).join('');
```

4. 抽出 `renderTaskItemList(item, i, currentIndex)` — 現有邏輯
5. 新增 `renderTaskItemCard(item, i, currentIndex)` — card 邏輯（見 5.4 節）

**CSS：**
- 加 `.task-item-card` 及相關子 class（見 5.4 節）
- 加 `.ti-card-placeholder`

**後端 API 變更：無**

---

### Phase E：驗證拖曳仍正常

重點確認項目（無需改程式，純測試）：

1. **拖曳加入**：左側卡片拖到 card mode 的 task list → item 正確 append / 插入
2. **card 上重排**：card mode 下 `overTaskItem` 的 `getBoundingClientRect()` top/bottom half 判斷 → 以 64px card 高度驗證正確
3. **混合模式**：resize sidebar 跨過 420px 切換 mode 時，清單 item 仍可拖曳
4. **resize 不干擾卡片拖曳**：`resizing-task-sb` class 存在時，媒體卡片拖曳的 `dragover`/`drop` 事件不受影響（因為 `user-select:none` 只防文字選取，不影響 drag events）

---

## 8. 驗證方式

### 8.1 語法檢查

```powershell
python -m py_compile launcher.py && Write-Host "OK"
```

### 8.2 手動瀏覽器測試步驟

**Resize 功能：**
1. 開啟 `http://localhost:8765`，點「📋 任務」開啟 sidebar
2. 將滑鼠移到 sidebar 左邊界 → cursor 應變為 `col-resize`
3. 按住拖曳向左 → sidebar 變寬，媒體 grid 縮小
4. 按住拖曳向右 → sidebar 變窄直到 min 240px
5. 確認 sidebar 不會小於 240px、不超過視窗寬度的 50%
6. 雙擊 handle → 寬度恢復 320px
7. 按 F5 重整 → 寬度保留

**Card mode：**
1. 建立任務，加入 3 個以上媒體項目
2. 拖曳 handle 將 sidebar 拉到 ≥ 420px → 項目改為 card 樣式（含縮圖/placeholder）
3. 縮小到 < 420px → 回到 list 樣式

### 8.3 CSS/DOM 檢查點

| 點 | 預期狀態 |
|----|---------|
| resize 中 `document.body` | 有 `.resizing-task-sb` class |
| resize 中 `#taskSidebar` | 有 `.resizing` class，`style.width` 即時更新 |
| resize 結束後 | 兩個 class 都移除，`localStorage['taskSidebarWidth']` 更新 |
| sidebar 開關時 | `#taskSidebar` 有 `.toggling` class，動畫完成後移除 |

### 8.4 拖曳加入測試

1. 拖曳左側卡片到 list mode sidebar → 加入成功
2. 拖曳左側卡片到 card mode sidebar → 加入成功
3. 拖曳到現有 card 的上半 → 插入在該 card 之前
4. 拖曳到現有 card 的下半 → 插入在該 card 之後

### 8.5 任務內重排測試

1. list mode：拖曳第 3 項到第 1 項上方 → 第 3 項變第 1 項
2. card mode：同上操作
3. 重整後順序保留（tasks.json 已儲存）

### 8.6 寬度保留測試

1. 拖曳調整寬度至 500px
2. 按 F5 重整
3. sidebar 開啟後寬度仍為 500px（`localStorage` 有值）
4. 清除 localStorage (`localStorage.removeItem('taskSidebarWidth')`) 後重整 → 使用預設 320px

### 8.7 小螢幕行為測試（瀏覽器 DevTools 模擬 800px 寬）

1. sidebar 開啟時為 `position:fixed` overlay
2. resize handle 仍可拖曳
3. `TASK_SB_MAX` 計算改為 `min(640, innerWidth - 40)` → 不超出螢幕

---

## 9. 風險與注意事項

### 9.1 Resize 拖曳與媒體拖曳互相干擾

**問題**：`document.addEventListener('mousemove', ...)` 在 resize 時也監聽整個頁面；若使用者拖曳媒體卡片時碰到 handle，可能觸發 resize。

**緩解**：
- Resize 只在 `mousedown` 發生在 `.task-resize-handle` 時啟動
- `mousemove` handler 先檢查 `document.body.classList.contains('resizing-task-sb')`
- 媒體卡片的 `dragstart` 是 drag API event，而 resize 用的是 `mousedown/mousemove`（不同事件系統），兩者**不會衝突**
- `dragstart` 發生時，瀏覽器進入 drag 模式，`mousemove` 不觸發 → resize 自然停止

### 9.2 Sidebar 太寬壓縮左側媒體 Grid

**問題**：sidebar 拉到 50% 視窗寬時，media grid 僅剩 50% 空間，`auto-fill minmax(190px,1fr)` 可能只能排 2 欄。

**緩解**：
- `TASK_SB_MAX = min(640, window.innerWidth * 0.5)` 是軟限制；媒體 grid 用 `min-width:0` 防止溢出
- 不做額外處理，使用者拉寬 sidebar 是有意識的選擇
- 若 grid 欄數過少，使用者自然會縮回

### 9.3 Mobile/Fixed Overlay 下的 Resize

**問題**：`position:fixed` 時 sidebar 不佔文件 flow，`.main-area` 不感知寬度。

**緩解**：
- 小螢幕 resize 仍正常：直接改 `sidebar.style.width`
- `setTaskSidebarWidth()` 中：小螢幕時的 `TASK_SB_MAX` 用 `window.innerWidth - 40`
- 固定 overlay 下，左側 grid 不受影響（sidebar 浮在上面）

### 9.4 localStorage 值異常

**問題**：`localStorage['taskSidebarWidth']` 可能為 `'NaN'`、`'undefined'`、負數。

**緩解**：
```javascript
function loadTaskSidebarWidth() {
  const raw = localStorage.getItem('taskSidebarWidth');
  const px  = raw ? parseInt(raw, 10) : TASK_SB_DEFAULT;
  setTaskSidebarWidth(isNaN(px) ? TASK_SB_DEFAULT : px);
  // clampTaskSidebarWidth() 內部還會再 clamp 一次
}
```

雙重保護：`isNaN` 檢查 + `clamp`。

### 9.5 Card Mode 下 Drop Index 判斷

**問題**：`overTaskItem` 用 `e.clientY` 與 `getBoundingClientRect()` 判斷上下半。card mode 高度 ~64px vs list mode ~34px。

**結論**：邏輯完全一樣，無需修改。高度更大反而讓上下半更容易點到，**drag UX 更好**。

### 9.6 `transition` 殘留造成 resize 延遲

**問題**：若 `toggling` class 因為某些原因未移除，`transition:width .2s` 仍存在，resize 拖曳會有 0.2s 延遲。

**緩解**：
- `transitionend` 事件加 `{once:true}` → 只觸發一次，自動移除監聽器
- 在 `initTaskSidebarResize` 的 `mousedown` 中強制移除 `toggling`：
  ```javascript
  handle.addEventListener('mousedown', e => {
    document.getElementById('taskSidebar').classList.remove('toggling');
    // ...
  });
  ```

### 9.7 `rebuildFileMap()` 時機

**問題**：使用者開啟 sidebar、新增任務後尚未 reload，`fileMap` 是空的，所有 card 顯示 placeholder。

**緩解**：
- 初始 `init()` 中 `reload()` 和 `loadTasks()` 並行執行，`reload()` 完成後 `rebuildFileMap()`
- card mode render 時若 `fileMap` 為空，顯示 placeholder 是合理的 fallback，不算錯誤
- 加一個「⟳ 重新整理」會同步 fileMap，這本來就是使用者的已知操作

---

## 附錄：新增/修改的識別符號對照表

| 類別 | 名稱 | 說明 |
|------|------|------|
| CSS class | `.task-resize-handle` | sidebar 左側拖曳把手 |
| CSS class | `.task-sidebar.toggling` | 開關動畫時暫時加上 |
| CSS class | `.task-sidebar.resizing` | resize 拖曳進行中 |
| CSS class | `body.resizing-task-sb` | resize 進行中，防止文字選取 |
| CSS class | `.task-item-card` | card mode 的 task item |
| CSS class | `.ti-card-thumb` | card 縮圖容器 |
| CSS class | `.ti-card-num` | 縮圖上的序號 badge |
| CSS class | `.ti-card-body` | card 文字區 |
| CSS class | `.ti-card-name` | card 檔名 |
| CSS class | `.ti-card-meta` | card badge + date 行 |
| CSS class | `.ti-card-placeholder` | card 無縮圖時的 fallback |
| JS const | `TASK_SB_MIN` | 240 |
| JS const | `TASK_SB_DEFAULT` | 320 |
| JS const | `TASK_SB_MAX_ABS` | 640 |
| JS var | `taskItemViewMode` | `'list'` \| `'card'` |
| JS var | `fileMap` | `Map<path, fileObject>` |
| JS fn | `clampTaskSidebarWidth(px)` | 套用 min/max 限制 |
| JS fn | `setTaskSidebarWidth(px)` | 設定寬度 + 更新 viewMode |
| JS fn | `loadTaskSidebarWidth()` | 從 localStorage 讀取並套用 |
| JS fn | `initTaskSidebarResize()` | 初始化 mousedown/move/up 監聽 |
| JS fn | `updateTaskViewMode()` | 依寬度決定 list/card mode |
| JS fn | `rebuildFileMap()` | reload 後重建 path→file 對照表 |
| JS fn | `getTaskItemVisual(item)` | 從 fileMap 查找縮圖資料 |
| JS fn | `compactPlaceholder(type, ext)` | card 用的精簡 placeholder |
| JS fn | `renderTaskItemList(item, i, cur)` | list mode render |
| JS fn | `renderTaskItemCard(item, i, cur)` | card mode render |
