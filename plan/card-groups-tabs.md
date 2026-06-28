# 卡片模式多群組分頁規格文件

> **狀態**：規格草稿，尚未實作  
> **目標**：讓另一個 agent 可以照此文件直接執行實作

---

## 目前狀態摘要（實作前請確認）

### 後端
- `load_cfg()` / `save_cfg(cfg)` 位於 launcher.py 第 88–97 行
- `GET /api/cards` 位於第 306–310 行，直接從 `load_cfg()` 讀取並回傳三個欄位
- `POST /api/cards/save` 位於第 474–482 行，覆寫三個欄位後呼叫 `save_cfg()`

### 前端全域變數（第 2172–2179 行）
```javascript
let cardModeActive = localStorage.getItem('cardModeActive') === '1';
let kcData         = [];
let kcCount        = 6;
let kcBackground   = '';
let kcBgPicking    = false;
let kcEditIndex    = -1;
let kcEditTmp      = {};
```

### 前端主要函式位置
| 函式 | 起始行 |
|------|--------|
| `loadCards()` | 2181 |
| `syncKcData()` | 2192 |
| `saveKcCards()` | 2198 |
| `toggleCardMode()` | 2207 |
| `renderCardMode()` | 2224 |
| `adjustKcCount(delta)` | 2294 |
| `openKCard(i)` | 2303 |
| `editKCard(e,i)` | 2309 |
| `kcBrowse(btn,field)` | 2339 |
| `kcClearField(field)` | 2362 |
| `closeKcModal()` | 2375 |
| `saveKcCard()` | 2380 |
| `kcSetBackground()` | 2397 |
| `kcClearBackground()` | 2412 |
| `clearKcCard()` | 2418 |

### 現有 CSS class 前綴
- 卡片格線：`.kcard-*`
- 卡片編輯 modal：`.kc-modal-*`、`.kc-field-*`、`.kc-pick-btn`、`.kc-clear-btn`、`.kc-danger-btn`、`.kc-preview-*`

### HTML 關鍵元素
- `#cardModeBtn`：topbar-right 裡的「🃏 卡片」按鈕
- `#kcModal`：卡片編輯 modal（在 Toast `<div>` 之前）
- `#gridArea`：`renderCardMode()` 將內容注入此元素

---

## 1. 資料模型

### 1.1 新的 config.json 結構

```json
{
  "dirs": [],
  "recursive": true,
  "card_active_group_id": "g_default",
  "card_groups": [
    {
      "id": "g_default",
      "name": "群組 1",
      "card_count": 6,
      "card_background": "",
      "cards": [
        {
          "id": 0,
          "title": "",
          "file": "",
          "thumbnail": ""
        }
      ]
    }
  ]
}
```

### 1.2 欄位規則

| 欄位 | 規則 |
|------|------|
| `id`（群組） | 格式 `g_` + 8 位隨機英數字，例如 `g_a3f9b2c1`。預設群組固定為 `g_default` |
| `name` | 最多 30 個字元，不可空白 |
| `card_count` | 整數 1–24，與現行限制相同 |
| `cards` | 陣列，元素數量 ≥ card_count（以 syncKcData 邏輯動態補齊空卡片） |
| `card_active_group_id` | 指向 `card_groups[*].id` 的字串；需驗證是否存在 |

**id 產生方式**（後端 Python）：
```python
import secrets
def new_group_id():
    return 'g_' + secrets.token_hex(4)  # 8 位 hex → 'g_a3f9b2c1'
```
**不使用 uuid4**，保持短小且易讀。

**active group 不存在時的 fallback**：若 `card_active_group_id` 指向的 id 在 `card_groups` 中找不到，自動切換至 `card_groups[0].id`。

**刪到最後一個群組**：不允許刪除，前端需先判斷 `kcGroups.length <= 1`，若是則顯示 toast 提示且中止。

---

## 2. 舊資料 Migration

### 2.1 觸發時機

在後端 `load_cfg()` 讀取完 JSON 之後，立刻執行 migration helper。也就是說，每次 `GET /api/cards` 都會自動轉換（已轉換的資料不重複轉換）。

### 2.2 Migration 邏輯（後端 Python）

在 `load_cfg()` 之後、呼叫端使用前，加入下列 helper 並調用：

```python
def migrate_cards_cfg(cfg):
    """
    若 cfg 含有舊格式欄位 (cards / card_count / card_background)
    但不含新格式欄位 (card_groups)，自動轉換為多群組格式。
    已轉換的資料（含 card_groups）原地回傳，不重複轉換。
    """
    if 'card_groups' in cfg:
        return cfg  # 已是新格式

    # 舊格式 → 新格式
    old_cards      = cfg.get('cards', [])
    old_count      = cfg.get('card_count', 6)
    old_background = cfg.get('card_background', '')

    cfg['card_groups'] = [{
        'id':              'g_default',
        'name':            '群組 1',
        'card_count':      max(1, min(24, int(old_count))),
        'card_background': old_background,
        'cards':           old_cards,
    }]
    cfg['card_active_group_id'] = 'g_default'

    # 保留舊欄位不刪除（降低風險；可在未來版本清理）
    return cfg
```

呼叫位置：`load_cfg()` 的 `return` 之前加上 `cfg = migrate_cards_cfg(cfg)`。

### 2.3 是否刪除舊欄位

**推薦：保留舊欄位，不刪除。**

理由：
1. `cards`、`card_count`、`card_background` 欄位對新程式碼無害（只有 `card_groups` 被讀取）
2. 萬一 migration 有 bug，使用者舊資料仍可手動復原
3. 此工具為單檔工具，config 體積無影響

若未來確認新格式穩定，可再加一個手動清理步驟刪除舊欄位。

---

## 3. API 設計

### 3.1 採用方案 A（推薦）

維持 `GET /api/cards` 和 `POST /api/cards/save`，一次傳輸整個 groups 狀態。

**理由**：
- 卡片資料量小（最多 24 群組 × 24 卡片 × 4 欄位），一次序列化無效能顧慮
- launcher.py 是單檔工具，減少 API 端點數量等於減少維護面
- 前端已有 `saveKcCards()` 的儲存模式，改動最小

### 3.2 更新後的 API 契約

**`GET /api/cards`**

回傳：
```json
{
  "card_active_group_id": "g_default",
  "card_groups": [
    {
      "id": "g_default",
      "name": "群組 1",
      "card_count": 6,
      "card_background": "",
      "cards": [...]
    }
  ]
}
```
後端需在回傳前呼叫 `migrate_cards_cfg(cfg)` 確保格式正確。

**`POST /api/cards/save`**

body：
```json
{
  "card_active_group_id": "g_default",
  "card_groups": [...]
}
```

後端邏輯：
```python
elif u.path == '/api/cards/save':
    groups     = body.get('card_groups', [])
    active_id  = body.get('card_active_group_id', '')
    cfg        = load_cfg()
    # 驗證每個 group 的 card_count 在 1–24 範圍內
    for g in groups:
        g['card_count'] = max(1, min(24, int(g.get('card_count', 6))))
    cfg['card_groups']           = groups
    cfg['card_active_group_id']  = active_id
    save_cfg(cfg)
    self.send_json({'ok': True})
```

---

## 4. 前端狀態設計

### 4.1 新增全域變數

在現有 `let cardModeActive ...` 區塊後加入：

```javascript
// 多群組狀態
let kcGroups        = [];   // 完整 card_groups 陣列
let kcActiveGroupId = '';   // 目前 active 群組 id
```

**保留** `kcData`、`kcCount`、`kcBackground` 作為 active group 的「投影（projection）」，理由：
- 現有 `syncKcData()`、`renderCardMode()`、`adjustKcCount()` 等函式都直接使用這三個變數，保留可減少改動範圍
- 每次切換群組或更新後呼叫 `syncActiveKcProjection()` 同步即可

### 4.2 需新增的 Helper 函式

```javascript
// 產生新群組 id（8 位英數字）
function newKcGroupId() {
  return 'g_' + Math.random().toString(36).slice(2, 10).padEnd(8, '0');
}

// 建立預設群組物件
function defaultKcGroup(name) {
  return {
    id:              newKcGroupId(),
    name:            name || '群組 1',
    card_count:      6,
    card_background: '',
    cards:           []
  };
}

// 取得目前 active group 物件（找不到則回傳 kcGroups[0]，再找不到回傳 null）
function activeKcGroup() {
  return kcGroups.find(g => g.id === kcActiveGroupId) || kcGroups[0] || null;
}

// 確保 kcGroups 至少有一個群組
function ensureKcGroups() {
  if (!kcGroups || kcGroups.length === 0) {
    kcGroups = [defaultKcGroup('群組 1')];
    // 將 id 固定為 g_default 以對應 migration
    kcGroups[0].id = 'g_default';
  }
  if (!kcActiveGroupId || !kcGroups.find(g => g.id === kcActiveGroupId)) {
    kcActiveGroupId = kcGroups[0].id;
  }
}

// 從 active group 同步到投影變數（kcData / kcCount / kcBackground）
function syncActiveKcProjection() {
  const g = activeKcGroup();
  if (!g) return;
  kcCount      = g.card_count;
  kcBackground = g.card_background;
  kcData       = g.cards || [];
  syncKcData();  // 補齊空卡片
}

// 將投影變數寫回 active group（儲存前呼叫）
function writeActiveKcProjection() {
  const g = activeKcGroup();
  if (!g) return;
  g.card_count      = kcCount;
  g.card_background = kcBackground;
  g.cards           = kcData;
}

// 切換 active group
function setActiveKcGroup(id) {
  if (!kcGroups.find(g => g.id === id)) return;
  writeActiveKcProjection();  // 先把目前編輯狀態寫回
  kcActiveGroupId = id;
  syncActiveKcProjection();
  renderCardMode();
}

// 新增群組
async function createKcGroup() {
  const name = '群組 ' + (kcGroups.length + 1);
  const g    = defaultKcGroup(name);
  writeActiveKcProjection();
  kcGroups.push(g);
  kcActiveGroupId = g.id;
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
}

// 重新命名群組
async function renameKcGroup(id) {
  const g = kcGroups.find(x => x.id === id);
  if (!g) return;
  const name = prompt('群組名稱（最多 30 字）', g.name);
  if (name === null) return;           // 使用者取消
  if (!name.trim()) { toast('名稱不可為空', 'err'); return; }
  if (name.trim().length > 30) { toast('名稱最多 30 字', 'err'); return; }
  g.name = name.trim();
  await saveKcCards();
  renderCardMode();
}

// 刪除群組
async function deleteKcGroup(id) {
  if (kcGroups.length <= 1) { toast('至少需要保留一個群組', 'err'); return; }
  const g = kcGroups.find(x => x.id === id);
  if (!g) return;
  if (!confirm('刪除「' + g.name + '」？此群組的所有卡片設定將一併移除。')) return;
  const idx = kcGroups.indexOf(g);
  kcGroups.splice(idx, 1);
  if (kcActiveGroupId === id) {
    kcActiveGroupId = kcGroups[Math.max(0, idx - 1)].id;
  }
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
}
```

### 4.3 修改現有函式

**`loadCards()`** — 改讀新格式：
```javascript
async function loadCards() {
  try {
    const r = await fetch('/api/cards');
    const d = await r.json();
    kcGroups        = d.card_groups || [];
    kcActiveGroupId = d.card_active_group_id || '';
    ensureKcGroups();
    syncActiveKcProjection();
  } catch {}
}
```

**`saveKcCards()`** — 改傳新格式：
```javascript
async function saveKcCards() {
  writeActiveKcProjection();
  try {
    await fetch('/api/cards/save', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({
        card_groups:          kcGroups,
        card_active_group_id: kcActiveGroupId
      })
    });
  } catch { toast('卡片設定儲存失敗', 'err'); }
}
```

**`adjustKcCount(delta)`** — 邏輯不變，但寫入 active group：
```javascript
async function adjustKcCount(delta) {
  const n = Math.max(1, Math.min(24, kcCount + delta));
  if (n === kcCount) return;
  kcCount = n;
  syncKcData();
  await saveKcCards();
  renderCardMode();
}
```
此函式無需修改，因為它操作 `kcCount`（投影），`saveKcCards()` 會在呼叫前執行 `writeActiveKcProjection()`。

**`kcSetBackground()` / `kcClearBackground()`** — 同上，操作 `kcBackground`（投影），不需額外修改。

**`saveKcCard()`** — 操作 `kcData`（投影），不需額外修改。

**`syncKcData()`** — 不需修改。

---

## 5. UI / UX 設計

### 5.1 控制列佈局

目前控制列（`.kcard-controls`）內容：
```
[卡片數量]  [−] [7] [＋]  [🖼 設定背景]  [清除]
```

新增後佈局（上下兩列或左右排列，依空間決定）：

**建議：改為兩列 flex**

第一列（群組分頁列）：
```
[群組 1 ●] [群組 2] [群組 3] [＋]
```

第二列（目前的控制列）：
```
[卡片數量]  [−] [6] [＋]  [🖼 設定背景]  [清除]
```

每個群組 tab 右側有 `⋯` 按鈕，下拉選單含「改名」和「刪除」。

### 5.2 群組 Tab 互動

| 操作 | 實作 |
|------|------|
| 點擊 tab | 切換 active group（`setActiveKcGroup(id)`） |
| 點擊 ⋯ | 顯示 inline dropdown：「重新命名」 / 「刪除」 |
| 重新命名 | `prompt()` 彈窗（簡單可接受） |
| 刪除 | `confirm()` + `deleteKcGroup(id)` |
| 點擊 ＋ | `createKcGroup()` |
| Active 樣式 | `background: var(--accent)` + `color: #fff` |
| Tab 過長 | `text-overflow: ellipsis` + `max-width: 120px` |
| 多 tab 水平捲動 | 群組列容器設 `overflow-x: auto; white-space: nowrap` |

### 5.3 新增群組流程

1. 使用者點 `[＋]` 按鈕
2. `createKcGroup()` 建立新群組（預設名稱「群組 N」、6 張空卡片）
3. 自動切換至新群組（active）
4. `saveKcCards()` 儲存
5. `renderCardMode()` 重繪

### 5.4 刪除群組流程

1. 點 `⋯` → 「刪除」
2. 若 `kcGroups.length <= 1`：toast 提示「至少需要保留一個群組」，中止
3. `confirm()` 確認：「刪除「群組 N」？此群組的所有卡片設定將一併移除。」
4. `deleteKcGroup(id)` 執行刪除
   - 若刪除的是 active group → 切到鄰近群組（優先上一個，若無則下一個）
5. `saveKcCards()` 儲存
6. `renderCardMode()` 重繪

### 5.5 重新命名流程

1. 點 `⋯` → 「重新命名」
2. `prompt()` 彈窗，預填目前名稱
3. 驗證：不可空白、最多 30 字
4. `g.name = name.trim()` 更新
5. `saveKcCards()` 儲存
6. `renderCardMode()` 重繪

---

## 6. `renderCardMode()` 改造

改造後的結構：

```javascript
function renderCardMode() {
  const group = activeKcGroup();
  if (!group) return;

  // 1. 確保投影與 active group 一致
  syncActiveKcProjection();

  // 2. 建立群組 tabs HTML
  const tabsHtml = kcGroups.map(g => {
    const isActive = g.id === kcActiveGroupId;
    return '<div class="kcard-group-tab' + (isActive ? ' active' : '') + '">' +
      '<span onclick="setActiveKcGroup(\'' + g.id + '\')">' + escHtml(g.name) + '</span>' +
      '<button class="kcard-group-menu-btn" onclick="kcGroupMenu(event,\'' + g.id + '\')" title="群組選項">⋯</button>' +
    '</div>';
  }).join('') +
  '<button class="kcard-group-add" onclick="createKcGroup()" title="新增群組">＋</button>';

  // 3. 建立卡片 HTML（與現有邏輯相同，使用 kcData / kcCount）
  syncKcData();
  const cardsHtml = kcData.slice(0, kcCount).map((card, i) => { /* 現有邏輯不變 */ }).join('');

  // 4. 背景按鈕 HTML（與現有邏輯相同，使用 kcBackground）
  const bgBtnHtml = kcBackground ? '...' : '...';

  // 5. 注入 gridArea
  const gridArea = document.getElementById('gridArea');
  gridArea.innerHTML =
    '<div class="kcard-view">' +
      '<div class="kcard-group-tabs">' + tabsHtml + '</div>' +
      '<div class="kcard-controls">' +
        '... 卡片數量 / 背景 ...' +
      '</div>' +
      '<div class="kcard-scroll"><div class="kcard-grid">' + cardsHtml + '</div></div>' +
    '</div>';

  // 6. 套用全域背景（與現有邏輯相同，使用 kcBackground）
  if (kcBackground) {
    gridArea.style.backgroundImage    = 'url(\'/api/card-image?path=' + encodeURIComponent(kcBackground) + '\')';
    gridArea.style.backgroundSize     = 'cover';
    gridArea.style.backgroundPosition = 'center';
  } else {
    gridArea.style.backgroundImage = gridArea.style.backgroundSize = gridArea.style.backgroundPosition = '';
  }
}
```

新增 `kcGroupMenu(event, id)` 函式，負責顯示 inline dropdown（或直接用 `kcShowGroupMenu(event, id)`）：
- 建立一個絕對定位的小 div，含「重新命名」、「刪除」兩個選項
- 點擊其他地方時自動移除（`document.addEventListener('click', ...)` 一次性監聽）

---

## 7. CSS 設計

### 7.1 新增 CSS class

所有新 class 加在現有 `/* ── 卡片模式 ── */` 區塊之後：

```css
/* ── 群組分頁列 ── */
.kcard-group-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px 0;
  overflow-x: auto;
  white-space: nowrap;
  background: rgba(255,255,255,.9);
  backdrop-filter: saturate(180%) blur(14px);
  /* 隱藏捲軸但仍可捲動 */
  scrollbar-width: none;
}
.kcard-group-tabs::-webkit-scrollbar { display: none; }

.kcard-group-tab {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background .14s, color .14s;
  flex-shrink: 0;
}
.kcard-group-tab span {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kcard-group-tab:hover {
  background: var(--surf2);
  color: var(--text);
}
.kcard-group-tab.active {
  background: var(--accent);   /* --accent = #007aff（Apple 藍） */
  color: #fff;
  border-color: transparent;
}

/* 群組選項按鈕（⋯）*/
.kcard-group-menu-btn {
  background: none;
  border: none;
  padding: 0 2px;
  cursor: pointer;
  font-size: 15px;
  color: inherit;
  opacity: .6;
  box-shadow: none;
  line-height: 1;
}
.kcard-group-menu-btn:hover { opacity: 1; transform: none; }
.kcard-group-tab.active .kcard-group-menu-btn { color: rgba(255,255,255,.8); }

/* ＋ 新增群組按鈕 */
.kcard-group-add {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  border: 1.5px dashed var(--border);
  background: transparent;
  font-size: 18px;
  color: var(--muted);
  cursor: pointer;
  padding: 0;
  box-shadow: none;
  transition: background .14s, border-color .14s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.kcard-group-add:hover {
  background: var(--surf2);
  border-color: var(--accent);
  color: var(--accent);
  transform: none;
}

/* 群組 inline dropdown 選單 */
.kcard-group-dropdown {
  position: fixed;       /* fixed 確保不被父層 overflow 裁切 */
  z-index: 900;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,.18);
  padding: 6px 0;
  min-width: 120px;
}
.kcard-group-dropdown-item {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  color: var(--text);
  transition: background .1s;
}
.kcard-group-dropdown-item:hover { background: var(--surf2); }
.kcard-group-dropdown-item.danger { color: var(--red); }
```

### 7.2 修改現有 CSS

**`.kcard-controls`**：移除 `border-bottom`（由群組列接手），或改為 `border-top: 1px solid ...` 視覺分隔。

**`.kcard-view`**：已是 `flex-direction:column`，無需修改。

### 7.3 Responsive 行為

- 群組分頁列（`.kcard-group-tabs`）設 `overflow-x: auto`，小螢幕可水平捲動
- 控制列（`.kcard-controls`）設 `flex-wrap: wrap; gap: 10px`，小螢幕自動換行
- 卡片格線已是 `grid-template-columns: repeat(auto-fill, minmax(260px,1fr))`，無需修改

---

## 8. 風險與解法

| 風險 | 解法 |
|------|------|
| 舊資料 migration 錯誤導致卡片遺失 | `migrate_cards_cfg()` 只在 `card_groups` 不存在時執行；保留舊欄位（`cards`、`card_count`）作為備份 |
| 切換群組前未保存 active group 修改 | `setActiveKcGroup()` 在切換前呼叫 `writeActiveKcProjection()`，確保編輯狀態同步至 `kcGroups` |
| `card_active_group_id` 指向不存在的 id | `ensureKcGroups()` 自動 fallback 至 `kcGroups[0].id`；`activeKcGroup()` 也有防守回傳 |
| 刪除最後一個群組 | `deleteKcGroup()` 進入時先檢查 `kcGroups.length <= 1`，若是則 toast 提示並 return |
| 背景圖路徑失效（圖片被移動） | 現有行為：`/api/card-image` 找不到檔案回傳 404，前端 `<img>` 的 `onerror` 處理，不 crash |
| config.json 膨脹 | 最多 24 群組 × 24 卡片 × 4 欄位，預估最大 ≈ 50 KB，對 JSON 無效能問題 |
| `prompt()` 改名 UX 較簡單 | 可接受，與目前任務清單改名方式一致；未來若需要可升級為 modal |
| 與任務播放清單（`kcData` vs task `items`）命名混淆 | 卡片模式所有變數維持 `kc` 前綴，任務模式維持 `task` 前綴，CSS class 分別為 `.kcard-*` 和 `.task-*`，無衝突 |
| 新增/刪除群組後，kcEditIndex 指向舊群組的卡片 | 切換群組時（`setActiveKcGroup()`）先 `closeKcModal()` 關閉 modal，重設 `kcEditIndex = -1` |

---

## 9. 實作 Phase Plan

### Phase A：資料模型與 Migration Helper

**目標**：後端支援新格式，舊資料自動轉換  
**要修改的區域**：
- `load_cfg()`（第 88 行）：回傳前呼叫 `migrate_cards_cfg(cfg)`
- 新增 `migrate_cards_cfg(cfg)` function（建議加在 `save_cfg` 之後）
- 新增 `new_group_id()` function

**驗證方式**：
- 手動將 config.json 還原為舊格式（只含 `cards`、`card_count`、`card_background`）
- 啟動 server，`GET /api/cards`，確認回傳含 `card_groups` 和 `card_active_group_id`

**完成條件**：
- `migrate_cards_cfg()` 通過 Python `-m py_compile` 檢查
- 舊格式 config.json 在 `GET /api/cards` 後自動包含正確的 `card_groups`

---

### Phase B：API 改為回傳 / 接受 groups 格式

**目標**：`GET /api/cards` 回傳新格式；`POST /api/cards/save` 接受新格式  
**要修改的區域**：
- 第 306–310 行（`GET /api/cards` handler）
- 第 474–482 行（`POST /api/cards/save` handler）

**驗證方式**：
- `curl` 或 PowerShell `Invoke-WebRequest` 測試 GET 回傳結構
- `curl` POST 送新格式 body，確認 config.json 正確更新
- 送舊格式 POST body（只含 `cards`、`card_count`），確認 server 不 crash（應 fallback gracefully）

**完成條件**：
- GET 回傳含 `card_groups[]`（至少一個群組）和 `card_active_group_id`
- POST 儲存後，再 GET 回傳相同資料

---

### Phase C：前端狀態 Helper 與 Active Group Projection

**目標**：前端狀態改用 `kcGroups` / `kcActiveGroupId`，投影機制建立  
**要修改的區域**（全在 `// ── Card Mode ──` 區塊）：
- 全域變數：新增 `kcGroups`、`kcActiveGroupId`
- 新增函式：`newKcGroupId()`、`defaultKcGroup()`、`activeKcGroup()`、`ensureKcGroups()`、`syncActiveKcProjection()`、`writeActiveKcProjection()`
- 修改 `loadCards()`
- 修改 `saveKcCards()`

**驗證方式**：
- 瀏覽器 console：`loadCards()` 後 `console.log(kcGroups, kcActiveGroupId)` 確認正確
- `saveKcCards()` 後確認 config.json 含新格式

**完成條件**：
- `loadCards()` 正確填充 `kcGroups` 和 `kcActiveGroupId`
- `saveKcCards()` 送出正確的 JSON body
- `activeKcGroup()` 回傳正確物件

---

### Phase D：UI Tabs / 新增 / 切換 / 改名 / 刪除

**目標**：群組分頁 UI 完整可操作  
**要修改的區域**：
- `renderCardMode()`：加入群組 tabs HTML 和控制（在現有 controls 上方）
- 新增函式：`setActiveKcGroup(id)`、`createKcGroup()`、`renameKcGroup(id)`、`deleteKcGroup(id)`、`kcGroupMenu(event, id)`
- CSS：新增 `.kcard-group-tabs`、`.kcard-group-tab`、`.kcard-group-tab.active`、`.kcard-group-add`、`.kcard-group-menu-btn`、`.kcard-group-dropdown`、`.kcard-group-dropdown-item`

**驗證方式**：
- 啟動 server，進入卡片模式，確認顯示「群組 1」tab 和 ＋ 按鈕
- 點 ＋ 新增群組，確認切換成功、tabs 更新
- 點 ⋯ 改名：輸入新名稱後顯示更新；輸入空白應顯示 toast 錯誤
- 點 ⋯ 刪除：confirm 後群組消失，active 切到鄰近
- 只剩一個群組時點刪除：出現 toast 提示，不執行刪除

**完成條件**：
- 新增、切換、改名、刪除四個操作均可正常使用
- 刪除最後一個群組時正確阻擋

---

### Phase E：串接卡片數量、背景、卡片編輯到 Active Group

**目標**：所有卡片操作只影響 active group  
**要修改的區域**：
- `adjustKcCount(delta)`：呼叫 `saveKcCards()` 已涵蓋 `writeActiveKcProjection()`，**確認**無需修改
- `kcSetBackground()` / `kcClearBackground()`：同上，**確認**無需修改
- `saveKcCard()` / `clearKcCard()`：同上，**確認**無需修改
- `editKCard(e, i)`：切換群組時需關閉 modal（在 `setActiveKcGroup()` 中處理）
- `init()`：確認 `loadCards()` 完成後，若 `cardModeActive`，呼叫 `renderCardMode()` 使用新格式

**驗證方式**：
- 群組 1 設定卡片 A，切換到群組 2，確認卡片 A 不見
- 切回群組 1，確認卡片 A 仍在
- 群組 1 設背景，切到群組 2，確認背景不同
- 調整卡片數量，切換群組後確認數量各自獨立

**完成條件**：
- 兩個群組的卡片、背景、數量完全互相獨立
- 所有操作後 config.json 正確更新

---

### Phase F：驗證與回歸測試

**目標**：所有測試計畫 checklist 通過  
**要修改的區域**：不修改程式碼，只執行測試  
**驗證方式**：見第 10 節測試計畫

**完成條件**：
- `python -m py_compile launcher.py` 通過
- 所有測試 checklist 項目打勾

---

## 10. 測試計畫 Checklist

### 資料 Migration
- [ ] 手動編輯 config.json 只保留 `dirs`、`recursive`、`cards`、`card_count`、`card_background`（舊格式），啟動 server 後 `GET /api/cards` 回傳 `card_groups`，且群組名稱為「群組 1」、cards 內容正確
- [ ] 上述操作後 config.json **原有的** `cards`、`card_count`、`card_background` 欄位仍然保留（不被刪除）

### 群組基本操作
- [ ] 進入卡片模式，顯示「群組 1」tab 和 ＋ 按鈕
- [ ] 點 ＋ 新增群組 → 顯示「群組 2」tab，自動切換到新群組
- [ ] 點「群組 1」tab → 切換回群組 1
- [ ] 點 ⋯ → 「重新命名」→ 輸入「教學組」→ tab 顯示「教學組」
- [ ] 點 ⋯ → 「重新命名」→ 輸入空白 → 顯示 toast「名稱不可為空」，不更新
- [ ] 點 ⋯ → 「刪除」→ confirm → 群組消失，active 切到鄰近群組
- [ ] 只剩一個群組時，點 ⋯ → 「刪除」→ 顯示 toast「至少需要保留一個群組」，不執行刪除

### 群組資料獨立性
- [ ] 群組 1 設定卡片 1 的播放檔案 A，切換到群組 2 → 卡片 1 為空
- [ ] 切回群組 1 → 卡片 1 仍顯示檔案 A
- [ ] 群組 1 卡片數量設為 3，群組 2 卡片數量設為 10 → 各自獨立
- [ ] 群組 1 設背景圖 X，群組 2 不設背景 → 切換時背景正確顯示/消失

### 持久性
- [ ] 關閉卡片模式（點「🃏 卡片」切換），再重新開啟 → active group 保留為最後操作的群組
- [ ] 關閉 server（Ctrl+C）重新啟動 → 所有群組資料（名稱、卡片、背景、卡片數量）正確讀取
- [ ] config.json 可被 JSON linter 正確解析（格式無誤）

### Python 語法
- [ ] `python -m py_compile launcher.py` 執行後無錯誤輸出

---

## 附錄：`--accent` CSS 變數確認

現有 CSS 中確認 `--accent` 是否已定義（群組 tab active 樣式使用）。若未定義，改用 `#007aff`（Apple 藍，與現有 `.btn-blue` 一致）。

```css
/* 建議在 :root 區塊加入（若尚未存在）*/
--accent: #007aff;
```

---

*文件版本：1.0 | 對應 launcher.py 當前版本（含卡片模式全域背景功能）*
