# 媒體啟動器 — 任務項目 Compact List Card 規格

> 版本：v1.0　日期：2026-06-26　狀態：草稿

---

## 1. 現況問題

### 1.1 目前卡片結構（`launcher.py` 約 L502–L551）

目前每個 `.task-item` 是「大縱向卡片」，HTML 結構如下：

```
.task-item (display:block; position:relative)
  .ti-num         ← position:absolute; top:7px; left:7px（序號 badge，覆蓋於縮圖上）
  .ti-remove      ← position:absolute; top:7px; right:7px（✕，hover 才顯示）
  .ti-thumb       ← width:100%; aspect-ratio:16/9（縮圖，全寬）
  .ti-body        ← padding:9px 10px 10px
    .ti-name      ← -webkit-line-clamp:2（最多兩行）
    .ti-meta      ← type-badge + ti-warn
```

### 1.2 問題

| 問題 | 細節 |
|------|------|
| 縮圖過大 | `.ti-thumb { width:100%; aspect-ratio:16/9 }` → sidebar 預設 320px，每張縮圖約 296×167px；加上 `.ti-body`（~50px）= **每張卡約 220px 高** |
| 任務累積難辨識 | sidebar 高 800px 時最多只能看到 3–4 張卡片，看不清下一個要播什麼 |
| 播放順序不清楚 | 只有 `.current` class 顯示藍框，沒有明確「下一個」標示 |
| 缺少狀態資訊 | 無法從 UI 直接看出目前 / 下一個 / 缺失 |
| 序號不顯眼 | 序號 badge 壓在縮圖上，小且半透明，快速掃視時難識別 |

---

## 2. 目標

- 每張卡高度壓縮到 **72–88px**，sidebar 中一次可看到 8–12 張
- 縮圖保留但縮小為左側小圖（84×48px）
- 檔名為主要視覺資訊（佔卡片右側寬度、最多兩行）
- 清楚標示「目前」與「下一個」播放項目
- 保留所有現有互動：拖曳重排、點擊播放、刪除

---

## 3. 版型設計

### 3.1 ASCII 佈局

```
┌────────────────────────────────────────────────────┐
│ [序號] ┌──────────┐  開學典禮簡報（第一學期）     ✕ │
│        │ 縮圖     │  📊 PPTX  · teacher/      [目前] │
│        │ 84×48px  │                                  │
│        └──────────┘                                  │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ [序號] ┌──────────┐  Week3_課程影片.mp4            ✕ │
│        │ 縮圖     │  🎬 MP4                   [下一個]│
│        └──────────┘                                  │
└────────────────────────────────────────────────────┘
```

### 3.2 CSS 尺寸

| 元素 | 尺寸 / 樣式 |
|------|------------|
| `.task-item`（compact） | `display:flex; align-items:center; padding:8px 10px; gap:10px; min-height:72px` |
| `.ti-thumb`（新尺寸） | `width:84px; height:48px; flex-shrink:0; border-radius:6px; overflow:hidden; position:relative` |
| `.ti-thumb img` | `width:100%; height:100%; object-fit:cover` |
| `.ti-num` | `position:absolute; bottom:3px; left:3px; font-size:10px; font-weight:700; padding:1px 4px; border-radius:3px; background:rgba(0,0,0,.65); color:#fff; pointer-events:none` |
| `.ti-body` | `flex:1; min-width:0; display:flex; flex-direction:column; gap:4px` |
| `.ti-name` | `font-size:13px; font-weight:500; line-height:1.35; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:break-all` |
| `.ti-meta` | `display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted); flex-wrap:wrap` |
| `.ti-status` | `font-size:10px; font-weight:600; border-radius:4px; padding:1px 6px; flex-shrink:0` |
| `.ti-remove` | `opacity:0; flex-shrink:0; width:22px; height:22px; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size:11px; cursor:pointer; color:var(--muted); background:transparent; transition:all .1s` |

**序號位置**：從縮圖左上移至左下角（`bottom:3px; left:3px`），避免遮擋縮圖主體內容。

**刪除按鈕位置**：改為 flex 行末（非 `position:absolute`），hover 才顯示，不佔視覺干擾。

### 3.3 檔名策略

- 最多兩行（`-webkit-line-clamp:2`）
- 顯示 `item.stem`（無副檔名的主檔名），fallback 用 `item.name`
- `title` 屬性設完整路徑，hover 可看完整資訊
- 不把文字壓在縮圖上 —— 文字在縮圖右側獨立區塊

### 3.4 Meta row 內容

```
[type-badge]  [副檔名]  ·  [資料夾最後一層]  [可選：資料夾名]
```

具體顯示邏輯：
```javascript
const folder = item.path.includes('\\')
  ? item.path.split('\\').at(-2)  // 取倒數第二段當作資料夾名
  : '';
```

缺失檔案時，meta row 顯示警告：
```html
<span class="ti-warn">⚠ 檔案未在掃描清單中</span>
```

---

## 4. 狀態設計

### 4.1 三種（四種）狀態

| Class | 視覺 | ti-status 文字 |
|-------|------|---------------|
| `.current` | 藍色左邊線（`border-left:3px solid var(--accent)`）+ 微亮背景 | `[目前]`（藍底白字） |
| `.next` | 淡藍左邊線（`border-left:3px solid rgba(47,129,247,.4)`）+ 極淡背景 | `[下一個]`（藍字外框） |
| 無 class | 一般狀態，hover 有底色 | 無 |
| `.missing` | 透明度 0.55，保留可刪除 | meta 顯示 `⚠ 檔案未在掃描清單中`（紅字） |

### 4.2 CSS

```css
/* 一律重置左邊線預設，各狀態各自加 */
.task-item { border-left:3px solid transparent; }
.task-item.current {
  border-left-color: var(--accent);
  background: rgba(47,129,247,.07);
}
.task-item.next {
  border-left-color: rgba(47,129,247,.4);
  background: rgba(47,129,247,.03);
}
.task-item.missing { opacity:.55 }

/* ti-status badge */
.ti-status.is-current {
  background: var(--accent);
  color: #fff;
}
.ti-status.is-next {
  background: transparent;
  color: var(--accent);
  border: 1px solid rgba(47,129,247,.5);
}
```

### 4.3 nextIndex 計算規則

與現有 `playNextItem()` 保持一致，使用**循環（wrap-around）**邏輯：

```javascript
function getNextTaskIndex(task) {
  if (!task || task.items.length === 0) return -1;
  if (task.currentIndex < 0) return 0;                         // 尚未播放，下一個是第 0 項
  return (task.currentIndex + 1) % task.items.length;          // 播到最後一項後循環到 0
}
```

**特殊情形**：若 `task.items.length === 1`，`nextIndex === currentIndex === 0` → current 優先，next 不顯示。

判斷方式：
```javascript
const cur  = task.currentIndex;
const next = getNextTaskIndex(task);
const isCurrent = i === cur;
const isNext    = !isCurrent && i === next;
```

---

## 5. 縮圖策略

### 5.1 現有 helpers（不改）

```javascript
fileMap              // Map<path, fileObject>，由 rebuildFileMap() 維護
getTaskItemVisual(item)  // 從 fileMap 查找，missing 時回傳 {missing:true}
taskThumbHtml(item)      // 回傳 <img> 或 placeholderHtml()
```

### 5.2 compact mode 的 placeholder 是否適用

目前 `placeholderHtml(type, ext)` 輸出完整 placeholder（含 emoji 大圖 + 副檔名文字），在
`aspect-ratio:16/9` 全寬縮圖中看起來正常。

**問題**：縮圖區域縮小到 84×48px 後，placeholder 文字會擠壓、emoji 也偏小。

**解法**：新增 `compactPlaceholderHtml(type, ext)` 只顯示 emoji，無文字：

```javascript
function compactPlaceholderHtml(type, ext) {
  const icons = {video:'🎬',audio:'🎵',image:'🖼',pdf:'📄',ppt:'📊',doc:'📝'};
  return `<div class="ti-compact-ph ph-${escHtml(type)}">
    <span>${icons[type]||'📁'}</span>
  </div>`;
}
```

CSS：
```css
.ti-compact-ph {
  width:100%; height:100%;
  display:flex; align-items:center; justify-content:center;
  font-size:22px;
}
```

### 5.3 taskThumbHtml 在 compact mode

`taskThumbHtml(item)` 內的 `onerror` 呼叫 `placeholderHtml(...)` — 在 compact mode 下需改呼叫 `compactPlaceholderHtml`。

解法：新增 `taskCompactThumbHtml(item)` 函式，邏輯與 `taskThumbHtml` 相同，但 `onerror` 呼叫 `compactPlaceholderHtml`：

```javascript
function taskCompactThumbHtml(item) {
  const visual = getTaskItemVisual(item);
  const type = visual.type || item.type || 'doc';
  const ext  = visual.ext  || item.ext  || '';
  if (visual.thumb) {
    return `<img src="/api/thumb?key=${encodeURIComponent(visual.thumb)}"
                 alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=compactPlaceholderHtml('${escHtml(type)}','${escHtml(ext)}')">`;
  }
  if (visual.img_url) {
    return `<img src="${visual.img_url}" alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=compactPlaceholderHtml('${escHtml(type)}','${escHtml(ext)}')">`;
  }
  return compactPlaceholderHtml(type, ext);
}
```

---

## 6. 拖曳重排影響評估

### 6.1 現有邏輯

`overTaskItem(e, index)` 使用：
```javascript
const rect  = e.currentTarget.getBoundingClientRect();
const after = e.clientY > rect.top + rect.height / 2;
e.currentTarget.classList.add(after ? 'drag-over-bot' : 'drag-over-top');
```

**結論**：此邏輯使用 `rect.height`（動態取得），不依賴固定高度，與卡片高度無關。**compact card（~80px）比舊 card（~220px）更容易點到上下半，drag UX 更好。不需要修改。**

### 6.2 drop indicator

`.drag-over-top { border-top:2px solid var(--accent) }`  
`.drag-over-bot { border-bottom:2px solid var(--accent) }`

compact card 改為使用 `border-left` 表示 current/next 狀態。這與 drag indicator 的 `border-top/bot` 沒有衝突。**不需要修改 drag indicator 邏輯。**

### 6.3 刪除按鈕與 drag/click 衝突

現有 `removeTaskItem(e, index)` 已有 `e.stopPropagation()`，阻止點擊事件冒泡到 `.task-item` 的 `onclick="playTaskItem()"` — **不需要修改**。

`.ti-remove` 改到 flex 行末後，需確保它不是 `draggable="true"` 的觸發來源：
- `.task-item[draggable="true"]` 的拖曳起點是整張卡片
- 在 `.ti-remove` 加 `ondragstart="event.stopPropagation()"` 防止從刪除按鈕開始拖曳

---

## 7. 實作計畫

### Phase A：CSS 改為 compact list card

**修改的 CSS class：**

| Class | 動作 | 說明 |
|-------|------|------|
| `.task-list` | 修改 `gap:12px → gap:6px` | 卡片緊湊後間距縮小 |
| `.task-item` | 全面重寫 | 改為 flex row、min-height:72px、border-left:3px |
| `.task-item:hover` | 修改 | 移除 `transform:translateY(-2px)`（compact 模式不適合彈跳效果） |
| `.task-item.current` | 修改 | 改為藍色左邊線 + 微亮背景 |
| `.task-item.next` | **新增** | 淡藍左邊線 + 極淡背景 |
| `.ti-thumb` | 修改 | `width:84px; height:48px`；移除 `aspect-ratio:16/9; width:100%` |
| `.ti-num` | 修改 | 移至縮圖左下角（`bottom:3px; left:3px`）；縮小字型 |
| `.ti-body` | 修改 | 改為 flex column，`gap:4px` |
| `.ti-name` | 微調 | 維持 line-clamp:2，字型微調 |
| `.ti-meta` | 維持 | 加 `flex-wrap:wrap` |
| `.ti-status` | **新增** | current / next badge |
| `.ti-status.is-current` | **新增** | 藍底白字 |
| `.ti-status.is-next` | **新增** | 藍字透明底 + 細框 |
| `.ti-remove` | 修改 | 從 `position:absolute` 改為 flex 行末 in-flow |
| `.ti-compact-ph` | **新增** | compact placeholder（只有 emoji） |

**不動的 class：**
- `.task-item.missing` — 只改透明度數值（`0.5 → 0.55`）
- `.task-item.dragging` — 不動
- `.task-item.drag-over-top/bot` — 不動
- `.task-item[draggable]` — 不動
- `.ti-warn` — 不動
- `.task-sb-header/footer` — 不動

---

### Phase B：`renderTaskSidebar()` 改輸出橫向結構

**修改的 JS 函式：**

**新增 `getNextTaskIndex(task)`**：

```javascript
function getNextTaskIndex(task) {
  if (!task || task.items.length === 0) return -1;
  if (task.currentIndex < 0) return 0;
  return (task.currentIndex + 1) % task.items.length;
}
```

**修改 `renderTaskSidebar()` 中 items.map 的 HTML 輸出**：

目前（L1185–L1208）：
```javascript
list.innerHTML = items.map((item, i) => {
  const isCurrent = i === task.currentIndex;
  const visual = getTaskItemVisual(item);
  const type = visual.type || item.type || 'doc';
  const ext = visual.ext || item.ext || '';
  const badge = `<span class="type-badge tb-${type}">${escHtml(ext)}</span>`;
  const missing = visual.missing ? '<span class="ti-warn">...</span>' : '';
  return `<div class="task-item${isCurrent?' current':''}${visual.missing?' missing':''}" ...>
    <span class="ti-num">${i+1}</span>
    <span class="ti-remove" ...>✕</span>
    <div class="ti-thumb ph-${type}">${taskThumbHtml(item)}</div>
    <div class="ti-body">
      <div class="ti-name" ...>${escHtml(item.stem||item.name)}</div>
      <div class="ti-meta">${badge}${missing}</div>
    </div>
  </div>`;
}).join('');
```

修改為呼叫獨立 render 函式：

```javascript
const nextIdx = getNextTaskIndex(task);
list.innerHTML = items.map((item, i) =>
  renderTaskItemCompact(item, i, task.currentIndex, nextIdx)
).join('');
```

**新增 `renderTaskItemCompact(item, i, currentIndex, nextIndex)`**：

```javascript
function renderTaskItemCompact(item, i, currentIndex, nextIndex) {
  const visual   = getTaskItemVisual(item);
  const type     = visual.type || item.type || 'doc';
  const ext      = visual.ext  || item.ext  || '';
  const isCurrent = i === currentIndex;
  const isNext    = !isCurrent && i === nextIndex;
  const missing   = visual.missing;

  // folder name: second-to-last path segment
  const parts  = item.path.replace(/\//g,'\\').split('\\');
  const folder = parts.length >= 2 ? parts[parts.length - 2] : '';

  const statusHtml = isCurrent
    ? '<span class="ti-status is-current">目前</span>'
    : isNext
      ? '<span class="ti-status is-next">下一個</span>'
      : '';

  const badge   = `<span class="type-badge tb-${type}">${escHtml(ext.toUpperCase())}</span>`;
  const folderSpan = folder
    ? `<span class="ti-folder" title="${escHtml(item.path)}">${escHtml(folder)}</span>`
    : '';
  const warnHtml = missing
    ? '<span class="ti-warn">⚠ 未在掃描清單</span>'
    : '';

  const stateClass = isCurrent ? ' current' : isNext ? ' next' : '';
  const missClass  = missing ? ' missing' : '';

  return `<div class="task-item${stateClass}${missClass}" data-index="${i}" draggable="true"
               onclick="playTaskItem(${i})"
               ondragstart="startTaskItemDrag(event,${i})"
               ondragover="overTaskItem(event,${i})"
               ondragleave="clearTaskDropMarks(event)"
               ondrop="dropOnTaskItem(event,${i})"
               ondragend="endTaskItemDrag()">
    <div class="ti-thumb ph-${type}">
      <span class="ti-num">${i + 1}</span>
      ${taskCompactThumbHtml(item)}
    </div>
    <div class="ti-body">
      <div class="ti-name" title="${escHtml(item.path)}">${escHtml(item.stem || item.name)}</div>
      <div class="ti-meta">
        ${badge}${folderSpan}${warnHtml}${statusHtml}
      </div>
    </div>
    <span class="ti-remove" onclick="removeTaskItem(event,${i})"
          ondragstart="event.stopPropagation()" title="從清單移除">✕</span>
  </div>`;
}
```

---

### Phase C：current / next 狀態 class 與 label

已在 Phase B 的 `renderTaskItemCompact` 中完成：
- `stateClass` 決定 `.current` / `.next`
- `statusHtml` 輸出 `.ti-status.is-current` / `.ti-status.is-next`
- `getNextTaskIndex(task)` 確保邏輯與 `playNextItem()` 一致

確認 `playTaskItem(index)` 會在播放後呼叫 `renderTaskSidebar()` → current/next badge 會自動更新。

---

### Phase D：縮圖尺寸調整與 placeholder

- 新增 `compactPlaceholderHtml(type, ext)`（見第 5.2 節）
- 新增 `taskCompactThumbHtml(item)`（見第 5.3 節）
- CSS 新增 `.ti-compact-ph`（見第 5.2 節）
- 舊的 `taskThumbHtml` 與 `placeholderHtml` 保留，仍供其他地方使用

---

### Phase E：驗證拖曳、刪除、播放、下一個

純測試，不改程式碼（見第 8 節驗證清單）。

---

## 8. 驗證方式

### 8.1 語法檢查

```powershell
python -m py_compile launcher.py && Write-Host "OK"
```

### 8.2 基本功能

| 測試 | 預期結果 |
|------|---------|
| 建立任務，加入 10 個項目 | sidebar 中一次可見 8+ 項，不需大量捲動 |
| 每個 item 的序號、縮圖、檔名都可見 | 序號在縮圖左下角，縮圖 84×48，檔名在右側 |
| 點擊 item → 播放 | 該 item 出現 `[目前]` badge + 藍色左邊線；下一項出現 `[下一個]` badge |
| 點「▶▶ 下一個」 | 下一個播放，current 移動，next 跟著更新 |
| 播到最後一項點「下一個」 | 循環回第 0 項（consistent with `playNextItem()` 的 modulo 邏輯） |
| 拖曳左側媒體卡片到 compact 清單 | 正確插入到 drag-over-top/bot 對應位置 |
| compact 清單內拖曳重排 | 正確移動，currentIndex 自動修正 |
| 點擊 ✕ 刪除項目 | 項目移除，不觸發播放，currentIndex 修正 |
| hover item | ✕ 按鈕浮現；整張 card 有 hover 底色 |
| 檔案不在掃描清單中 | 顯示 placeholder 縮圖；meta row 顯示紅色「⚠ 未在掃描清單」；透明度降低但可刪除 |
| 重整後任務資料保留 | tasks.json 內容正確，current/next badge 重新出現 |
| 任務清單為空 | 顯示「拖曳左側媒體卡片到此處」提示文字 |

---

## 9. 不做的事

| 項目 | 理由 |
|------|------|
| 不改後端 API | 純前端 CSS/JS 修改 |
| 不改 tasks.json schema | path/name/stem/type/ext 結構不變 |
| 不做自動播放完偵測 | 需要內建播放器或 OS 事件，超出範圍 |
| 不做真正內建播放器 | `os.startfile()` 呼叫系統預設程式已足夠 |
| 不保留「大縱向卡片」模式 | 全面換成 compact，不做雙模式切換 |
| 不做多欄瀑布流任務卡片 | 任務清單強調順序，單欄最清楚 |
| 不做 next loop 開關選項 | 與現有 `playNextItem()` 保持一致即可 |
| 不做鍵盤快捷鍵 | 超出本次範圍 |

---

## 附錄：新增 / 修改識別符號對照

| 類別 | 名稱 | 動作 | 說明 |
|------|------|------|------|
| CSS | `.task-list` | 修改 `gap` | `12px → 6px` |
| CSS | `.task-item` | **重寫** | flex row, border-left, min-height |
| CSS | `.task-item.current` | 修改 | 左邊線 + 微亮背景 |
| CSS | `.task-item.next` | **新增** | 淡藍左邊線 + 極淡背景 |
| CSS | `.ti-thumb` | 修改 | 固定 84×48px；移除 aspect-ratio:16/9 |
| CSS | `.ti-num` | 修改 | 移至縮圖左下；縮小字體 |
| CSS | `.ti-body` | 修改 | flex column gap:4px |
| CSS | `.ti-name` | 微調 | 維持 line-clamp:2 |
| CSS | `.ti-status` | **新增** | current / next badge 基底樣式 |
| CSS | `.ti-status.is-current` | **新增** | 藍底白字 |
| CSS | `.ti-status.is-next` | **新增** | 藍字 + 細框 |
| CSS | `.ti-remove` | 修改 | 從 absolute 改為 flex 行末 in-flow |
| CSS | `.ti-compact-ph` | **新增** | compact placeholder（emoji only） |
| CSS | `.ti-folder` | **新增** | 資料夾名 muted 文字 |
| JS | `getNextTaskIndex(task)` | **新增** | 計算下一個播放 index，循環邏輯 |
| JS | `renderTaskItemCompact(item, i, cur, next)` | **新增** | compact card HTML 輸出 |
| JS | `compactPlaceholderHtml(type, ext)` | **新增** | emoji-only placeholder |
| JS | `taskCompactThumbHtml(item)` | **新增** | compact mode 專用縮圖 HTML |
| JS | `renderTaskSidebar()` | 修改 | items.map 改呼叫 `renderTaskItemCompact` |
| JS | `taskThumbHtml(item)` | 保留不動 | 其他地方仍可用 |
| JS | `placeholderHtml(type, ext)` | 保留不動 | 其他地方仍可用 |
