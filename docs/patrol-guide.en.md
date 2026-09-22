# Threads Keyword Patrol Guide

## Overview

The Threads Keyword Patrol system enables automated monitoring of public posts matching specific keywords and generates reply drafts. All replies require human approval before publishing.

## Core Features

1. **Keyword Search** — Search public posts via Meta Threads Graph API
2. **SQLite Persistence** — Automatic deduplication by post ID
3. **Screening Rules** — Configurable exclude terms, minimum text length, etc.
4. **LLM Reply Drafting** — Generate Traditional Chinese replies using OpenAI or Anthropic (optional)
5. **Human Approval Gate** — All replies require explicit approval before publishing
6. **Dry-run Mode** — Test the pipeline without a real token

## Prerequisites

### 1. Meta Developer App Setup

1. Go to [Facebook Developers](https://developers.facebook.com/apps/)
2. Create a new App (select "Consumer" type)
3. Add "Threads API" product
4. In "Threads API" settings:
   - Configure OAuth Redirect URI
   - Enable the following permissions:
     - `threads_basic` (required)
     - `threads_keyword_search` (required - keyword search)
     - `threads_content_publish` (required - publish replies)
     - `threads_manage_replies` (optional - manage replies)

### 2. Obtain Long-lived Access Token

Short-lived tokens expire in 1 hour. Exchange for a long-lived token (60 days):

```bash
# Method 1: Use fetch_threads.py built-in token exchange
python scripts/fetch_threads.py \
  --token YOUR_SHORT_LIVED_TOKEN \
  --app-secret YOUR_APP_SECRET \
  --output test.json

# Method 2: Direct API call
curl "https://graph.threads.net/v1.0/access_token?grant_type=th_exchange_token&client_secret=YOUR_APP_SECRET&access_token=YOUR_SHORT_LIVED_TOKEN"
```

### 3. Important Limits

- **Keyword Search Limit**: 500 queries / 7 days (~70 queries/day)
- **App Review Requirements**:
  - Without approval: Can only search your own posts
  - After approval: Can search all public posts
  - Advanced access to `threads_keyword_search` requires App Review

### 4. Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit .env with your token
nano .env
```

Required:

```
THREADS_ACCESS_TOKEN=your_long_lived_token_here
```

Optional (for LLM reply generation):

```
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage Workflow

### First-time Setup

```bash
# 1. Initialize database
python scripts/patrol_threads.py init

# 2. Edit config (optional)
nano patrol_config.json

# 3. Test dry-run mode (no real token needed)
PATROL_DRY_RUN=1 python scripts/patrol_threads.py fetch --keywords "test"
```

### Daily Workflow

```bash
# 1. Search for posts by keywords
python scripts/patrol_threads.py fetch --keywords "AI,algorithm,community"

# 2. Generate reply drafts
python scripts/patrol_threads.py draft

# 3. Review pending drafts
python scripts/patrol_threads.py list

# 4. Approve or reject drafts
python scripts/patrol_threads.py approve 1
python scripts/patrol_threads.py reject 2 --reason "Not appropriate"

# 5. Publish approved replies
python scripts/patrol_threads.py publish
```

### Automation (Cron Schedule)

For periodic fetching:

```bash
# Edit crontab
crontab -e

# Run every 6 hours (respects API limits)
0 */6 * * * cd /path/to/AK-Threads-booster && /usr/bin/python3 scripts/patrol_threads.py auto
```

The `auto` command runs `fetch` + `draft` automatically, but publishing still requires manual approval.

## Configuration

`patrol_config.json` main fields:

```json
{
  "keywords": ["AI", "algorithm", "community"],
  "exclude_terms": ["spam", "giveaway"],
  "search_type": "RECENT",
  "max_posts_per_fetch": 50,
  "reply_language": "zh-TW",
  "brand_voice": {
    "tone": "professional yet approachable",
    "style": "direct, specific, no fluff"
  },
  "screening_rules": {
    "min_text_length": 20,
    "skip_replies": true,
    "skip_own_posts": true
  }
}
```

### Field Descriptions

- `keywords` — List of keywords to monitor
- `exclude_terms` — Exclude posts containing these terms
- `search_type` — `RECENT` (latest) or `TOP` (popular)
- `search_mode` — `KEYWORD` (keyword) or `TAG` (topic tag)
- `max_posts_per_fetch` — Max posts per search (limit 100)
- `reply_language` — Reply language (default Traditional Chinese)
- `brand_voice` — Brand voice settings (passed to LLM)
- `screening_rules` — Filtering rules

## Database Schema

SQLite stores two types of data:

### 1. `monitored_posts` — Monitored posts

- `post_id` — Threads post ID (primary key)
- `author_username` — Author handle
- `text` — Post content
- `permalink` — Post URL
- `timestamp` — Published time
- `discovered_at` — Discovery time
- `keywords_matched` — Matched keywords
- `raw_json` — Full API response

### 2. `reply_drafts` — Reply drafts

- `draft_id` — Draft ID (auto-increment)
- `post_id` — Corresponding post ID
- `reply_text` — Reply content
- `status` — Status: `pending`, `approved`, `rejected`
- `llm_provider` — LLM provider (`openai`, `anthropic`, `template`)
- `approved_at` — Approval time
- `published_at` — Publish time
- `reply_post_id` — Published reply ID

## LLM Reply Generation

### Using OpenAI

```bash
export OPENAI_API_KEY=sk-...
python scripts/patrol_threads.py draft
```

Default model is `gpt-4`. Customize in `patrol_config.json`:

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

### Using Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Modify `patrol_config.json`:

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

### Without LLM Key

If no API key is set, the system uses default template replies (e.g., "Thanks for sharing!").

Recommended to set up LLM key before actual use for valuable replies.

## Dry-run Mode

For testing without a real token:

```bash
export PATROL_DRY_RUN=1

# Test commands
python scripts/patrol_threads.py fetch --keywords "test"
python scripts/patrol_threads.py draft
python scripts/patrol_threads.py list
python scripts/patrol_threads.py publish
```

In dry-run mode:

- `fetch` won't call API, only prints simulation messages
- `publish` won't actually publish, generates fake reply_post_id

## Integration with Existing Features

### Relationship with `/setup`, `/analyze`, etc.

- Patrol system is an **independent new feature** for monitoring **others' posts** and replying
- Existing `/analyze`, `/draft`, etc. are for analyzing and creating **your own posts**

They can be used together:

1. Use patrol to find topics worth engaging with
2. Use `/topics` to record these topics for future post ideas
3. Use `/draft` to create your original posts
4. Use `/analyze` to analyze pre-publish decisions

### Relationship with `fetch_threads.py`

- `fetch_threads.py` — Fetch **your own** historical posts to build tracker
- `patrol_threads.py` — Monitor **others'** public posts and generate replies

Both use the same Threads API but for different purposes.

## FAQ

### Q: Why are search results empty?

A: Possible reasons:

1. Your App hasn't passed App Review for `threads_keyword_search`
   - Before approval, can only search your own posts
2. Token lacks permissions
   - Ensure token includes `threads_keyword_search` scope
3. API limits
   - Check you haven't exceeded 500 queries / 7 days

### Q: How to check API usage?

A: Meta Developer Dashboard → Your App → Threads API → Insights

Or via API:

```bash
curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
```

### Q: Will replies auto-publish?

A: **No**. The system is designed with a human approval gate:

1. `fetch` → Find posts
2. `draft` → Generate drafts (`pending` status)
3. `approve` → Human approval (`approved` status)
4. `publish` → Actually publish

### Q: Can I approve multiple drafts at once?

A: Currently requires individual approval. For batch needs, use a simple shell script:

```bash
# Approve draft_id 1 to 5
for i in {1..5}; do
  python scripts/patrol_threads.py approve $i
done
```

### Q: How to delete published replies?

A: Patrol system doesn't include delete functionality. To delete:

1. Manually delete in Threads App
2. Or use Threads API DELETE endpoint:

```bash
curl -X DELETE "https://graph.threads.net/v1.0/{reply_post_id}?access_token=YOUR_TOKEN"
```

## Comparison with QuickDash/快客

QuickDash has broader scope (may include Facebook, Instagram, etc.).

This patrol system is a **lightweight Threads-only alternative** focused on:

- Single operator (not multi-tenant SaaS)
- Threads official API only (no HTML scraping)
- Human approval at core (no auto-publish)
- Open source, self-modifiable

## Advanced Usage

### Integration into Existing Projects

To use patrol functionality in your own project:

```python
from scripts.patrol_threads import ThreadsPatrol, PatrolDB

# Initialize
patrol = ThreadsPatrol(config_path="my_config.json")

# Use API
patrol.fetch_keywords(["AI", "Python"])
patrol.draft_replies()
drafts = patrol.db.get_pending_drafts()

# Custom reply logic
for draft in drafts:
    if "specific_keyword" in draft["post_text"]:
        patrol.approve_draft(draft["draft_id"])
```

### CSV Export (Optional)

To export data to CSV:

```python
import sqlite3
import csv

conn = sqlite3.connect("patrol_threads.db")
cursor = conn.execute("SELECT * FROM monitored_posts")

with open("posts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([i[0] for i in cursor.description])  # Headers
    writer.writerows(cursor)
```

## License

MIT License — same as AK-Threads-Booster main project.

## Resources

- [Meta Threads API Documentation](https://developers.facebook.com/docs/threads)
- [Keyword Search API](https://developers.facebook.com/docs/threads/keyword-search/)
- [Meta App Review](https://developers.facebook.com/docs/app-review)
