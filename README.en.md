[Chinese](README.md) | [English](README.en.md)

# AK體 - Threads Algorithm Optimization Skill

`AK-Threads-Booster` remains the internal package name and install id.

AK-Threads-Booster is an AI skill system for Threads creators who want better posting decisions, not just faster text generation.

Its job is to help users:

- find stronger topic angles faster
- avoid obvious repetition and red-line mistakes
- draft in a voice closer to their own
- learn from real post performance over time

It does not guarantee viral posts.

It turns topic selection, drafting, analysis, prediction, and review into a repeatable system backed by the user's own Threads history.

---

## Who It Is For

- creators already posting on Threads who want a steadier content process
- users who want to know which topic types actually travel for their account
- users tired of guessing what to post next
- users who want their post history to become a usable decision asset

If the goal is to choose better topics, improve distribution odds, and stop wasting posts on stale or repetitive angles, this skill is built for that.

---

## Core Modules

### `/topics`
Find the next most worthwhile topic by combining historical performance, comment demand, self-repetition risk, and external freshness.

### `/draft`
Generate a draft from the user's brand voice, style guide, and historical data. It also runs a freshness gate before drafting so the user does not write into a dead topic by accident.

### `/analyze`
Run decision-first analysis on a finished draft. It checks algorithm red lines, upside drivers, suppression risks, style fit, and AI-tone traces.

### `/predict`
Estimate likely 24-hour performance from comparable historical posts so expectations are anchored in data.

### `/review`
Compare actual results against the prediction and write the learning back into the tracker.

### `/refresh`
Update `threads_daily_tracker.json` through the Threads API when available, or via Chrome MCP when API access is not available.

### 🆕 Keyword Patrol
Monitor public posts by keywords and generate replies with human approval. A lightweight alternative to QuickDash focused on single-operator use with official Threads API only.

See [docs/patrol-guide.en.md](docs/patrol-guide.en.md) for the complete guide.

---

## What Setup Produces

After `/setup`, the working directory typically contains:

- `threads_daily_tracker.json`
- `style_guide.md`
- `concept_library.md`
- `brand_voice.md` after `/voice`
- `posts_by_date.md`
- `posts_by_topic.md`
- `comments.md`

The tracker is the canonical file. The rest exist to make the data easier to use and review.

---

## Recommended Flow

### First-time setup

```text
/setup
/voice
```

This builds the tracker first, then deepens the brand-voice layer for better drafting.

### Before posting

```text
/topics
/draft
/analyze
```

Use `/topics` to find the best next angle, `/draft` to create a starting point, and `/analyze` to pressure-test the finished draft before publishing.

### After posting

```text
/predict
/review
```

This closes the loop and makes the next decision better.

---

## Data Sources

Users can build the system from:

- Threads Developer API token
- Meta official export zip
- existing JSON / Markdown / CSV
- Chrome logged into Threads with Claude in Chrome MCP
- legacy tracker migration

API access is optional, but it makes refresh much easier.

---

## Keyword Patrol Feature

Beyond analyzing your own posts, AK-Threads-Booster can now monitor others' public posts and generate replies.

### Quick Start

```bash
# 1. Initialize patrol system
python scripts/patrol_threads.py init

# 2. Set token (or use dry-run mode for testing)
export THREADS_ACCESS_TOKEN=your_token
# or
export PATROL_DRY_RUN=1

# 3. Search by keywords
python scripts/patrol_threads.py fetch --keywords "AI,algorithm"

# 4. Generate reply drafts
python scripts/patrol_threads.py draft

# 5. Review and publish
python scripts/patrol_threads.py list
python scripts/patrol_threads.py approve 1
python scripts/patrol_threads.py publish
```

### Key Features

- ✅ **Official API Only** — No HTML scraping or reverse engineering
- ✅ **Human Approval Gate** — All replies require explicit approval before publishing
- ✅ **LLM Drafts** — Supports OpenAI/Anthropic, defaults to Traditional Chinese tone
- ✅ **SQLite Deduplication** — Won't track the same post twice
- ✅ **Dry-run Mode** — Test the full pipeline without a real token
- ✅ **Schedulable** — Works with cron for automatic keyword fetching

### Use Cases

- Monitor industry keywords and join relevant discussions
- Find potential customers' pain points and provide value
- Track competitor topics and build brand visibility
- Discover post ideas from others' discussions

Complete documentation:

- [Patrol Guide (English)](docs/patrol-guide.en.md)
- [繁體中文完整指南](docs/patrol-guide.md)

---

## Product Positioning

This is not a "guaranteed viral post" tool.

The durable promise is:

**help creators find better topics faster and improve the odds that their posts are worth sharing, saving, and discussing.**

That is a stronger and more honest product promise than claiming guaranteed results.

---

## Installation

### Claude Code

```bash
claude install-plugin https://github.com/akseolabs-seo/AK-Threads-booster
```

### Manual

```bash
git clone https://github.com/akseolabs-seo/AK-Threads-booster.git
```

Place the repo in the skill or plugin directory used by the target tool.

---

## Directory

```text
AK-Threads-booster/
|- SKILL.md
|- AGENTS.md
|- skills/
|  |- setup/SKILL.md
|  |- refresh/SKILL.md
|  |- analyze/SKILL.md
|  |- draft/SKILL.md
|  |- predict/SKILL.md
|  |- review/SKILL.md
|  |- topics/SKILL.md
|  |- voice/SKILL.md
|- knowledge/
|  |- _shared/
|  |- psychology.md
|  |- algorithm.md
|  |- ai-detection.md
|  |- data-confidence.md
|  |- chrome-selectors.md
|- scripts/
|  |- fetch_threads.py         # Fetch your own historical posts
|  |- patrol_threads.py         # 🆕 Keyword patrol system
|  |- parse_export.py
|  |- update_snapshots.py
|  |- update_topic_freshness.py
|  |- render_companions.py
|- docs/
|  |- patrol-guide.md           # 🆕 Patrol guide (Traditional Chinese)
|  |- patrol-guide.en.md        # 🆕 Patrol guide (English)
|- templates/
|- examples/
|- .env.example                 # 🆕 Environment variables template
```

---

## License

MIT License. See [LICENSE](./LICENSE).
