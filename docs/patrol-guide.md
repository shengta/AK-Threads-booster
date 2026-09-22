# Threads 關鍵字巡邏系統使用指南

## 概述

Threads 關鍵字巡邏系統讓你能夠自動監控特定關鍵字的公開貼文，並生成回覆草稿。所有回覆都需要經過人工審批才會發布。

## Windows 使用者注意事項

### 編碼問題解決

在 Windows 上使用時，可能會遇到編碼錯誤（特別是繁體中文關鍵字）。請使用以下方法之一：

**方法 1：設定環境變數（推薦）**

```powershell
# PowerShell
$env:PYTHONUTF8=1
python scripts/patrol_threads.py fetch --keywords "AI,演算法"
```

```cmd
# CMD
set PYTHONUTF8=1
python scripts\patrol_threads.py fetch --keywords "AI,演算法"
```

**方法 2：變更控制台代碼頁**

```cmd
chcp 65001
python scripts\patrol_threads.py fetch --keywords "AI,演算法"
```

**方法 3：使用純英文關鍵字**

如果以上方法都無效，可以暫時使用英文關鍵字測試：

```powershell
python scripts/patrol_threads.py fetch --keywords "AI,algorithm"
```

## 核心功能

1. **關鍵字搜尋** — 透過 Meta Threads Graph API 搜尋公開貼文
2. **SQLite 持久化** — 自動去重，不會重複追蹤同一篇貼文
3. **篩選規則** — 可設定排除詞、最小文字長度等條件
4. **LLM 草稿回覆** — 使用 OpenAI 或 Anthropic 生成繁體中文回覆（可選）
5. **人工審批** — 所有回覆都需要明確批准才會發布
6. **乾跑模式** — 可在沒有真實 token 的情況下測試流程

## 前置需求

### 1. Meta Developer App 設定

1. 前往 [Facebook Developers](https://developers.facebook.com/apps/)
2. 建立新的 App，選擇 "Consumer" 類型
3. 新增 "Threads API" 產品
4. 在 "Threads API" 設定中：
   - 設定 OAuth Redirect URI
   - 啟用以下權限：
     - `threads_basic` (必要)
     - `threads_keyword_search` (必要 - 關鍵字搜尋)
     - `threads_content_publish` (必要 - 發布回覆)
     - `threads_manage_replies` (選用 - 管理回覆)

### 2. 獲取 Long-lived Access Token

Short-lived token 只有 1 小時有效期，需要換成 long-lived token (60天)：

```bash
# 方法 1: 使用 fetch_threads.py 內建的換 token 功能
python scripts/fetch_threads.py \
  --token YOUR_SHORT_LIVED_TOKEN \
  --app-secret YOUR_APP_SECRET \
  --output test.json

# 方法 2: 直接呼叫 API
curl "https://graph.threads.net/v1.0/access_token?grant_type=th_exchange_token&client_secret=YOUR_APP_SECRET&access_token=YOUR_SHORT_LIVED_TOKEN"
```

### 3. 重要限制

- **關鍵字搜尋限制**：500 次查詢 / 7 天（約 70 次/天）
- **App Review 要求**：
  - 未經審批：只能搜尋自己的貼文
  - 經審批後：可搜尋所有公開貼文
  - 申請 `threads_keyword_search` 權限的進階存取需要通過 App Review

### 4. 環境變數設定

```bash
# 複製範例檔案
cp .env.example .env

# 編輯 .env 填入你的 token
nano .env
```

必要設定：

```
THREADS_ACCESS_TOKEN=your_long_lived_token_here
```

選用設定（用於 LLM 回覆生成）：

```
OPENAI_API_KEY=sk-...
# 或
ANTHROPIC_API_KEY=sk-ant-...
```

## 使用流程

### 第一次設定

```bash
# 1. 初始化資料庫
python scripts/patrol_threads.py init

# 2. 編輯設定檔（可選）
nano patrol_config.json

# 3. 測試乾跑模式（不需要真實 token）
PATROL_DRY_RUN=1 python scripts/patrol_threads.py fetch --keywords "測試"
```

### 日常使用流程

```bash
# 1. 搜尋關鍵字貼文
python scripts/patrol_threads.py fetch --keywords "AI,演算法,社群經營"

# 2. 生成回覆草稿
python scripts/patrol_threads.py draft

# 3. 檢視待審批的草稿
python scripts/patrol_threads.py list

# 4. 批准或拒絕草稿
python scripts/patrol_threads.py approve 1
python scripts/patrol_threads.py reject 2 --reason "不適合回覆"

# 5. 發布已批准的回覆
python scripts/patrol_threads.py publish
```

### 自動化（Cron 排程）

如果你想定期自動抓取，可以設定 cron job：

```bash
# 編輯 crontab
crontab -e

# 每 6 小時執行一次（符合 API 限制）
0 */6 * * * cd /path/to/AK-Threads-booster && /usr/bin/python3 scripts/patrol_threads.py auto
```

`auto` 指令會自動執行 `fetch` + `draft`，但不會自動發布（仍需人工審批）。

## 設定檔說明

`patrol_config.json` 的主要欄位：

```json
{
  "keywords": ["AI", "演算法", "社群經營"],
  "exclude_terms": ["廣告", "抽獎"],
  "search_type": "RECENT",
  "max_posts_per_fetch": 50,
  "reply_language": "zh-TW",
  "brand_voice": {
    "tone": "professional yet approachable",
    "style": "直接、具體、不講空話"
  },
  "screening_rules": {
    "min_text_length": 20,
    "skip_replies": true,
    "skip_own_posts": true
  }
}
```

### 欄位說明

- `keywords` — 要監控的關鍵字列表
- `exclude_terms` — 排除含有這些詞的貼文
- `search_type` — `RECENT` (最新) 或 `TOP` (熱門)
- `search_mode` — `KEYWORD` (關鍵字) 或 `TAG` (主題標籤)
- `max_posts_per_fetch` — 每次搜尋最多抓幾篇（上限 100）
- `reply_language` — 回覆語言（預設繁體中文）
- `brand_voice` — 品牌語調設定（會傳給 LLM）
- `screening_rules` — 篩選規則

## 資料庫結構

系統使用 SQLite 儲存兩種資料：

### 1. `monitored_posts` — 監控的貼文

- `post_id` — Threads 貼文 ID（主鍵）
- `author_username` — 作者帳號
- `text` — 貼文內容
- `permalink` — 貼文連結
- `timestamp` — 發布時間
- `discovered_at` — 被發現的時間
- `keywords_matched` — 符合的關鍵字
- `raw_json` — 完整 API 回應

### 2. `reply_drafts` — 回覆草稿

- `draft_id` — 草稿 ID（自動遞增）
- `post_id` — 對應的貼文 ID
- `reply_text` — 回覆內容
- `status` — 狀態：`pending`, `approved`, `rejected`
- `llm_provider` — LLM 提供者（`openai`, `anthropic`, `template`）
- `approved_at` — 批准時間
- `published_at` — 發布時間
- `reply_post_id` — 發布後的回覆 ID

## LLM 回覆生成

### 使用 OpenAI

```bash
export OPENAI_API_KEY=sk-...
python scripts/patrol_threads.py draft
```

預設使用 `gpt-4`。可在 `patrol_config.json` 中調整：

```json
{
  "llm_settings": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 300
  }
}
```

### 使用 Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

修改 `patrol_config.json`：

```json
{
  "llm_settings": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.7,
    "max_tokens": 300
  }
}
```

### 無 LLM Key 的情況

如果沒有設定 API key，系統會使用預設模板回覆（如「感謝分享！」）。

建議在實際使用前先設定好 LLM key，才能產生有價值的回覆。

## 乾跑模式（Dry-run）

在沒有真實 token 或測試流程時使用：

```bash
export PATROL_DRY_RUN=1

# 測試各項指令
python scripts/patrol_threads.py fetch --keywords "測試"
python scripts/patrol_threads.py draft
python scripts/patrol_threads.py list
python scripts/patrol_threads.py publish
```

乾跑模式下：

- `fetch` 不會真的呼叫 API，只會印出模擬訊息
- `publish` 不會真的發布，會產生假的 reply_post_id

## 與現有功能的整合

### 與 `/setup`、`/analyze` 等 skill 的關係

- 巡邏系統是**獨立的新功能**，主要用於監控**別人的貼文**並回覆
- 現有的 `/analyze`、`/draft` 等是針對**自己的貼文**做分析和創作

兩者可以搭配使用：

1. 用巡邏系統找到值得參與的話題
2. 用 `/topics` 記錄這些話題作為未來發文靈感
3. 用 `/draft` 創作自己的原創貼文
4. 用 `/analyze` 分析發文前的決策

### 與 `fetch_threads.py` 的關係

- `fetch_threads.py` — 抓取**你自己**的歷史貼文，建立 tracker
- `patrol_threads.py` — 監控**其他人**的公開貼文，生成回覆

兩者使用相同的 Threads API，但用途不同。

## 常見問題

### Q: 為什麼搜尋結果都是空的？

A: 可能原因：

1. 你的 App 還沒通過 `threads_keyword_search` 的 App Review
   - 未審批前只能搜尋自己的貼文
2. Token 權限不足
   - 確認 token 包含 `threads_keyword_search` scope
3. API 限制
   - 確認沒有超過 500 queries / 7 days 的限制

### Q: 如何查看 API 使用量？

A: Meta Developer Dashboard → 你的 App → Threads API → Insights

或透過 API：

```bash
curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
```

### Q: 回覆會不會自動發布？

A: **不會**。系統設計就是要有人工審批門檻：

1. `fetch` → 找到貼文
2. `draft` → 生成草稿（`pending` 狀態）
3. `approve` → 人工批准（`approved` 狀態）
4. `publish` → 才會真正發布

### Q: 可以一次批准多個草稿嗎？

A: 目前需要逐個批准。如果有批量需求，可以寫簡單的 shell script：

```bash
# 批准 draft_id 1 到 5
for i in {1..5}; do
  python scripts/patrol_threads.py approve $i
done
```

### Q: 如何刪除已發布的回覆？

A: 巡邏系統目前不包含刪除功能。如需刪除，可以：

1. 手動到 Threads App 刪除
2. 或使用 Threads API 的 DELETE endpoint：

```bash
curl -X DELETE "https://graph.threads.net/v1.0/{reply_post_id}?access_token=YOUR_TOKEN"
```

## 與 QuickDash/快客 的對比

QuickDash/快客的功能範圍更廣（可能包含 Facebook、Instagram 等多平台）。

這個巡邏系統是針對 **Threads 單一平台的輕量替代方案**，專注於：

- 單一操作者（不是多租戶 SaaS）
- 僅 Threads 官方 API（不做 HTML scraping）
- 人工審批為核心（不自動發布）
- 開源、可自行修改

## 進階使用

### 整合到現有專案

如果你想在自己的專案中使用巡邏功能：

```python
from scripts.patrol_threads import ThreadsPatrol, PatrolDB

# 初始化
patrol = ThreadsPatrol(config_path="my_config.json")

# 使用 API
patrol.fetch_keywords(["AI", "Python"])
patrol.draft_replies()
drafts = patrol.db.get_pending_drafts()

# 自訂回覆邏輯
for draft in drafts:
    if "特定關鍵字" in draft["post_text"]:
        patrol.approve_draft(draft["draft_id"])
```

### CSV 匯出（選用）

如果需要匯出資料到 CSV：

```python
import sqlite3
import csv

conn = sqlite3.connect("patrol_threads.db")
cursor = conn.execute("SELECT * FROM monitored_posts")

with open("posts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([i[0] for i in cursor.description])  # 標題
    writer.writerows(cursor)
```

## 授權

MIT License — 同 AK-Threads-Booster 主專案。

## 相關資源

- [Meta Threads API 文件](https://developers.facebook.com/docs/threads)
- [Keyword Search API](https://developers.facebook.com/docs/threads/keyword-search/)
- [Meta App Review](https://developers.facebook.com/docs/app-review)
