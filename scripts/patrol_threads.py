#!/usr/bin/env python3
"""
AK-Threads-Booster: Keyword Patrol Pipeline

A DIY Threads keyword-patrol system that monitors public posts and generates replies.

Features:
- Keyword/topic search via Meta Threads Graph API
- SQLite persistence with deduplication
- Configurable screening rules
- LLM-powered reply drafting (Traditional Chinese by default)
- Human approval gate before publishing
- Dry-run mode for testing

Usage:
    # Initial setup (creates database)
    python patrol_threads.py init

    # Fetch posts matching keywords
    python patrol_threads.py fetch --keywords "關鍵字1,關鍵字2"

    # Screen and draft replies
    python patrol_threads.py draft

    # List pending drafts
    python patrol_threads.py list

    # Approve a draft
    python patrol_threads.py approve <draft_id>

    # Reject a draft
    python patrol_threads.py reject <draft_id>

    # Publish approved drafts
    python patrol_threads.py publish

    # Scheduled fetch (for cron)
    python patrol_threads.py auto

Prerequisites:
    1. Meta Developer App with Threads API
    2. Required permissions: threads_basic, threads_keyword_search, threads_manage_replies
    3. Long-lived user access token
    4. (Optional) OpenAI/Anthropic API key for LLM drafting

Environment Variables:
    THREADS_ACCESS_TOKEN    - Required: Threads API token
    OPENAI_API_KEY         - Optional: For LLM reply drafting
    ANTHROPIC_API_KEY      - Optional: Alternative LLM provider
    PATROL_DRY_RUN         - Set to "1" for dry-run mode
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required.")
    print("Install it with: pip install requests")
    sys.exit(1)

# Constants
API_BASE = "https://graph.threads.net/v1.0"
RATE_LIMIT_DELAY = 0.5
DEFAULT_CONFIG_PATH = "patrol_config.json"
DEFAULT_DB_PATH = "patrol_threads.db"

# Database schema
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitored_posts (
    post_id TEXT PRIMARY KEY,
    author_username TEXT,
    text TEXT,
    permalink TEXT,
    media_type TEXT,
    timestamp TEXT,
    discovered_at TEXT,
    keywords_matched TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS reply_drafts (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    draft_created_at TEXT,
    status TEXT DEFAULT 'pending',
    llm_provider TEXT,
    approved_at TEXT,
    rejected_at TEXT,
    published_at TEXT,
    reply_post_id TEXT,
    notes TEXT,
    FOREIGN KEY (post_id) REFERENCES monitored_posts(post_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_discovered ON monitored_posts(discovered_at);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON reply_drafts(status);
"""

# Default configuration
DEFAULT_CONFIG = {
    "keywords": ["AI", "演算法", "社群經營"],
    "exclude_terms": ["廣告", "抽獎"],
    "search_type": "RECENT",
    "search_mode": "KEYWORD",
    "media_type": None,
    "min_engagement_threshold": 0,
    "max_posts_per_fetch": 50,
    "reply_language": "zh-TW",
    "brand_voice": {
        "tone": "professional yet approachable",
        "style": "直接、具體、不講空話",
        "signature_elements": [
            "提供可執行的建議",
            "引用數據或案例",
            "避免 AI 感的制式回應"
        ]
    },
    "llm_settings": {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 300
    },
    "screening_rules": {
        "min_text_length": 20,
        "skip_replies": True,
        "skip_own_posts": True
    }
}


class PatrolDB:
    """Database manager for patrol data."""
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def init_schema(self):
        """Initialize database schema."""
        self.connect()
        self.conn.executescript(DB_SCHEMA)
        self.conn.commit()
        self.close()
    
    def post_exists(self, post_id: str) -> bool:
        """Check if a post already exists in the database."""
        self.connect()
        cursor = self.conn.execute(
            "SELECT 1 FROM monitored_posts WHERE post_id = ?",
            (post_id,)
        )
        exists = cursor.fetchone() is not None
        self.close()
        return exists
    
    def insert_post(self, post: Dict[str, Any], keywords_matched: List[str]):
        """Insert a new monitored post."""
        self.connect()
        self.conn.execute(
            """INSERT INTO monitored_posts 
               (post_id, author_username, text, permalink, media_type, 
                timestamp, discovered_at, keywords_matched, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post["id"],
                post.get("username", ""),
                post.get("text", ""),
                post.get("permalink", ""),
                post.get("media_type", "TEXT"),
                post.get("timestamp", ""),
                datetime.now(timezone.utc).isoformat(),
                ",".join(keywords_matched),
                json.dumps(post)
            )
        )
        self.conn.commit()
        self.close()
    
    def insert_draft(self, post_id: str, reply_text: str, provider: Optional[str] = None):
        """Insert a new reply draft."""
        self.connect()
        cursor = self.conn.execute(
            """INSERT INTO reply_drafts 
               (post_id, reply_text, draft_created_at, llm_provider)
               VALUES (?, ?, ?, ?)""",
            (
                post_id,
                reply_text,
                datetime.now(timezone.utc).isoformat(),
                provider
            )
        )
        draft_id = cursor.lastrowid
        self.conn.commit()
        self.close()
        return draft_id
    
    def get_pending_drafts(self) -> List[Dict]:
        """Get all pending drafts."""
        self.connect()
        cursor = self.conn.execute(
            """SELECT d.*, m.author_username, m.text as post_text, m.permalink
               FROM reply_drafts d
               JOIN monitored_posts m ON d.post_id = m.post_id
               WHERE d.status = 'pending'
               ORDER BY d.draft_created_at ASC"""
        )
        drafts = [dict(row) for row in cursor.fetchall()]
        self.close()
        return drafts
    
    def get_approved_drafts(self) -> List[Dict]:
        """Get all approved but unpublished drafts."""
        self.connect()
        cursor = self.conn.execute(
            """SELECT d.*, m.author_username, m.text as post_text, m.permalink
               FROM reply_drafts d
               JOIN monitored_posts m ON d.post_id = m.post_id
               WHERE d.status = 'approved' AND d.published_at IS NULL
               ORDER BY d.approved_at ASC"""
        )
        drafts = [dict(row) for row in cursor.fetchall()]
        self.close()
        return drafts
    
    def update_draft_status(self, draft_id: int, status: str, notes: Optional[str] = None):
        """Update draft status."""
        self.connect()
        timestamp_field = f"{status}_at"
        self.conn.execute(
            f"""UPDATE reply_drafts 
                SET status = ?, {timestamp_field} = ?, notes = ?
                WHERE draft_id = ?""",
            (status, datetime.now(timezone.utc).isoformat(), notes, draft_id)
        )
        self.conn.commit()
        self.close()
    
    def mark_draft_published(self, draft_id: int, reply_post_id: str):
        """Mark a draft as published."""
        self.connect()
        self.conn.execute(
            """UPDATE reply_drafts 
               SET published_at = ?, reply_post_id = ?
               WHERE draft_id = ?""",
            (datetime.now(timezone.utc).isoformat(), reply_post_id, draft_id)
        )
        self.conn.commit()
        self.close()
    
    def get_posts_without_drafts(self) -> List[Dict]:
        """Get posts that don't have any drafts yet."""
        self.connect()
        cursor = self.conn.execute(
            """SELECT * FROM monitored_posts m
               WHERE NOT EXISTS (
                   SELECT 1 FROM reply_drafts d WHERE d.post_id = m.post_id
               )
               ORDER BY m.discovered_at ASC"""
        )
        posts = [dict(row) for row in cursor.fetchall()]
        self.close()
        return posts


class ThreadsPatrol:
    """Main patrol operations."""
    
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, db_path: str = DEFAULT_DB_PATH):
        self.config_path = config_path
        self.db = PatrolDB(db_path)
        self.config = self._load_config()
        self.token = os.getenv("THREADS_ACCESS_TOKEN", "")
        self.dry_run = os.getenv("PATROL_DRY_RUN", "0") == "1"
        
        if not self.token and not self.dry_run:
            print("Warning: THREADS_ACCESS_TOKEN not set. Use PATROL_DRY_RUN=1 for testing.")
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Create default config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            print(f"Created default config at {self.config_path}")
            return DEFAULT_CONFIG
    
    def keyword_search(self, keyword: str) -> List[Dict]:
        """Search for posts matching a keyword."""
        if self.dry_run:
            print(f"  [DRY RUN] Would search for keyword: {keyword}")
            return []
        
        params = {
            "q": keyword,
            "search_type": self.config.get("search_type", "RECENT"),
            "search_mode": self.config.get("search_mode", "KEYWORD"),
            "limit": min(self.config.get("max_posts_per_fetch", 50), 100),
            "fields": "id,username,text,timestamp,media_type,permalink,is_reply",
            "access_token": self.token
        }
        
        if self.config.get("media_type"):
            params["media_type"] = self.config["media_type"]
        
        try:
            resp = requests.get(f"{API_BASE}/keyword_search", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"  Error searching for '{keyword}': {e}")
            return []
    
    def passes_screening_rules(self, post: Dict) -> bool:
        """Check if a post passes screening rules."""
        rules = self.config.get("screening_rules", {})
        
        # Skip replies if configured
        if rules.get("skip_replies", True) and post.get("is_reply", False):
            return False
        
        # Check text length
        text = post.get("text", "")
        min_length = rules.get("min_text_length", 20)
        if len(text) < min_length:
            return False
        
        # Check exclude terms
        exclude_terms = self.config.get("exclude_terms", [])
        if any(term in text for term in exclude_terms):
            return False
        
        # TODO: Add engagement threshold check when insights are available
        
        return True
    
    def fetch_keywords(self, keywords: Optional[List[str]] = None):
        """Fetch posts matching keywords."""
        keywords = keywords or self.config.get("keywords", [])
        
        print(f"[FETCH] Searching for {len(keywords)} keyword(s)...")
        
        new_posts = 0
        skipped_existing = 0
        skipped_screening = 0
        
        for keyword in keywords:
            print(f"  Searching: {keyword}")
            time.sleep(RATE_LIMIT_DELAY)
            
            posts = self.keyword_search(keyword)
            print(f"    Found {len(posts)} posts")
            
            for post in posts:
                post_id = post["id"]
                
                # Skip if already tracked
                if self.db.post_exists(post_id):
                    skipped_existing += 1
                    continue
                
                # Apply screening rules
                if not self.passes_screening_rules(post):
                    skipped_screening += 1
                    continue
                
                # Insert new post
                self.db.insert_post(post, [keyword])
                new_posts += 1
                print(f"    ✓ New post from @{post.get('username', 'unknown')}")
        
        print(f"\n[FETCH SUMMARY]")
        print(f"  New posts: {new_posts}")
        print(f"  Skipped (existing): {skipped_existing}")
        print(f"  Skipped (screening): {skipped_screening}")
    
    def generate_reply_llm(self, post_text: str, author: str) -> Optional[Dict[str, str]]:
        """Generate a reply using LLM (OpenAI or Anthropic)."""
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        llm_settings = self.config.get("llm_settings", {})
        provider = llm_settings.get("provider", "openai")
        
        brand_voice = self.config.get("brand_voice", {})
        reply_lang = self.config.get("reply_language", "zh-TW")
        
        prompt = f"""你是一個專業的 Threads 社群經營者。

品牌語調：
- 語氣：{brand_voice.get('tone', 'professional yet approachable')}
- 風格：{brand_voice.get('style', '直接、具體、不講空話')}

請為以下貼文撰寫一個有價值的回覆（{reply_lang}）：

作者：@{author}
內容：
{post_text}

回覆要求：
1. 提供具體、可執行的建議或觀點
2. 自然、不像 AI 生成
3. 字數控制在 150 字以內
4. 不要使用表情符號（除非原文大量使用）
5. 避免「很棒的分享」這類空洞的客套話

只輸出回覆內容，不要其他說明。"""
        
        try:
            if provider == "openai" and openai_key:
                return self._generate_openai(prompt, llm_settings)
            elif provider == "anthropic" and anthropic_key:
                return self._generate_anthropic(prompt, llm_settings)
            else:
                return None
        except Exception as e:
            print(f"    LLM generation error: {e}")
            return None
    
    def _generate_openai(self, prompt: str, settings: Dict) -> Dict[str, str]:
        """Generate reply using OpenAI."""
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model=settings.get("model", "gpt-4"),
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.get("temperature", 0.7),
            max_tokens=settings.get("max_tokens", 300)
        )
        
        return {
            "reply": response.choices[0].message.content.strip(),
            "provider": "openai"
        }
    
    def _generate_anthropic(self, prompt: str, settings: Dict) -> Dict[str, str]:
        """Generate reply using Anthropic."""
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model=settings.get("model", "claude-3-5-sonnet-20241022"),
            max_tokens=settings.get("max_tokens", 300),
            temperature=settings.get("temperature", 0.7),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "reply": response.content[0].text.strip(),
            "provider": "anthropic"
        }
    
    def generate_reply_template(self, post_text: str) -> str:
        """Generate a template reply (fallback when no LLM key)."""
        templates = [
            "感謝分享！這個觀點很有參考價值。",
            "很實用的內容，已收藏。",
            "同意你的看法，這點確實很重要。"
        ]
        # Simple: return first template (in real scenario, could be smarter)
        return templates[0]
    
    def draft_replies(self):
        """Generate draft replies for posts without drafts."""
        posts = self.db.get_posts_without_drafts()
        
        print(f"[DRAFT] Generating replies for {len(posts)} post(s)...")
        
        if not posts:
            print("  No new posts to draft replies for.")
            return
        
        for post in posts:
            post_data = json.loads(post["raw_json"])
            post_text = post["text"]
            author = post["author_username"]
            
            print(f"\n  Post from @{author}:")
            print(f"    {post_text[:80]}...")
            
            # Try LLM generation first
            llm_result = self.generate_reply_llm(post_text, author)
            
            if llm_result:
                reply_text = llm_result["reply"]
                provider = llm_result["provider"]
                print(f"    ✓ Generated reply via {provider}")
            else:
                reply_text = self.generate_reply_template(post_text)
                provider = "template"
                print(f"    ✓ Generated template reply (no LLM key)")
            
            # Insert draft
            draft_id = self.db.insert_draft(post["post_id"], reply_text, provider)
            print(f"    Draft ID: {draft_id}")
    
    def list_drafts(self, status: str = "pending"):
        """List drafts by status."""
        if status == "pending":
            drafts = self.db.get_pending_drafts()
        elif status == "approved":
            drafts = self.db.get_approved_drafts()
        else:
            print(f"Unknown status: {status}")
            return
        
        print(f"\n[{status.upper()} DRAFTS] Found {len(drafts)} draft(s)\n")
        
        if not drafts:
            return
        
        for draft in drafts:
            print(f"Draft ID: {draft['draft_id']}")
            print(f"  Post: {draft['permalink']}")
            print(f"  Author: @{draft['author_username']}")
            print(f"  Original: {draft['post_text'][:100]}...")
            print(f"  Reply: {draft['reply_text']}")
            print(f"  Created: {draft['draft_created_at']}")
            print()
    
    def approve_draft(self, draft_id: int):
        """Approve a draft for publishing."""
        self.db.update_draft_status(draft_id, "approved")
        print(f"✓ Draft {draft_id} approved")
    
    def reject_draft(self, draft_id: int, reason: Optional[str] = None):
        """Reject a draft."""
        self.db.update_draft_status(draft_id, "rejected", notes=reason)
        print(f"✗ Draft {draft_id} rejected")
    
    def publish_replies(self):
        """Publish approved drafts."""
        drafts = self.db.get_approved_drafts()
        
        print(f"[PUBLISH] Publishing {len(drafts)} approved draft(s)...")
        
        if not drafts:
            print("  No approved drafts to publish.")
            return
        
        for draft in drafts:
            draft_id = draft["draft_id"]
            post_id = draft["post_id"]
            reply_text = draft["reply_text"]
            
            print(f"\n  Publishing draft {draft_id}...")
            print(f"    Target post: {draft['permalink']}")
            
            if self.dry_run:
                print(f"    [DRY RUN] Would publish reply: {reply_text[:50]}...")
                reply_post_id = f"dry_run_{draft_id}"
            else:
                # Call Threads API to publish reply
                try:
                    reply_post_id = self._publish_reply_api(post_id, reply_text)
                    print(f"    ✓ Published! Reply ID: {reply_post_id}")
                except Exception as e:
                    print(f"    ✗ Publish failed: {e}")
                    continue
            
            # Mark as published
            self.db.mark_draft_published(draft_id, reply_post_id)
            time.sleep(RATE_LIMIT_DELAY)
    
    def _publish_reply_api(self, post_id: str, reply_text: str) -> str:
        """Publish a reply via Threads API."""
        # Step 1: Create media container for reply
        resp = requests.post(
            f"{API_BASE}/me/threads",
            data={
                "media_type": "TEXT",
                "text": reply_text,
                "reply_to_id": post_id,
                "access_token": self.token
            }
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        
        time.sleep(1)  # Wait for container processing
        
        # Step 2: Publish the container
        resp = requests.post(
            f"{API_BASE}/me/threads_publish",
            data={
                "creation_id": container_id,
                "access_token": self.token
            }
        )
        resp.raise_for_status()
        return resp.json()["id"]


def main():
    parser = argparse.ArgumentParser(
        description="AK-Threads-Booster Keyword Patrol Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init command
    subparsers.add_parser("init", help="Initialize database")
    
    # fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch posts by keywords")
    fetch_parser.add_argument("--keywords", help="Comma-separated keywords")
    
    # draft command
    subparsers.add_parser("draft", help="Generate reply drafts")
    
    # list command
    list_parser = subparsers.add_parser("list", help="List drafts")
    list_parser.add_argument("--status", default="pending", choices=["pending", "approved"])
    
    # approve command
    approve_parser = subparsers.add_parser("approve", help="Approve a draft")
    approve_parser.add_argument("draft_id", type=int)
    
    # reject command
    reject_parser = subparsers.add_parser("reject", help="Reject a draft")
    reject_parser.add_argument("draft_id", type=int)
    reject_parser.add_argument("--reason", help="Rejection reason")
    
    # publish command
    subparsers.add_parser("publish", help="Publish approved drafts")
    
    # auto command (for cron)
    subparsers.add_parser("auto", help="Auto-fetch and draft (for scheduled runs)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    patrol = ThreadsPatrol()
    
    if args.command == "init":
        print("Initializing database...")
        patrol.db.init_schema()
        print(f"✓ Database created at {DEFAULT_DB_PATH}")
        print(f"✓ Config created at {DEFAULT_CONFIG_PATH}")
        print("\nNext steps:")
        print("  1. Edit patrol_config.json with your keywords")
        print("  2. Set THREADS_ACCESS_TOKEN environment variable")
        print("  3. Run: python patrol_threads.py fetch")
    
    elif args.command == "fetch":
        keywords = None
        if args.keywords:
            keywords = [k.strip() for k in args.keywords.split(",")]
        patrol.fetch_keywords(keywords)
    
    elif args.command == "draft":
        patrol.draft_replies()
    
    elif args.command == "list":
        patrol.list_drafts(args.status)
    
    elif args.command == "approve":
        patrol.approve_draft(args.draft_id)
    
    elif args.command == "reject":
        patrol.reject_draft(args.draft_id, args.reason)
    
    elif args.command == "publish":
        patrol.publish_replies()
    
    elif args.command == "auto":
        print("=== AUTO MODE ===")
        patrol.fetch_keywords()
        print()
        patrol.draft_replies()


if __name__ == "__main__":
    main()
