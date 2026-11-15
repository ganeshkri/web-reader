#!/usr/bin/env python3
"""
Fetches the kipi.ai blog listing once a day and keeps data/posts.json up to date.

How it works (an incremental load, in data-engineer terms):
  1. Crawl the main /blog listing and each category page (following pagination).
  2. Any post URL we haven't seen before gets its own page fetched once
     for title, description, image and date.
  3. Merge into data/posts.json (existing posts are kept, categories are unioned).
  4. Optionally send a Telegram message listing new posts.

Personal-use reader: fetches politely (1 request/sec), stores only title,
short description and a link back to the original article.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.kipi.ai"
LISTING = f"{BASE}/blog"
POST_PATH_PREFIX = "/insights/blog/"
CATEGORIES = {
    "technology": "Technology",
    "conversational-ai": "Snowflake CoWork",
    "migration-and-modernization": "Migration & Modernization",
    "agentic-workflows-and-cortex-ai": "Agentic Workflows & Cortex AI",
    "press": "Press",
    "data-governance": "Data Governance & Optimization",
}
CATEGORY_URL = BASE + "/insights/blog-categories/{slug}"
MAX_PAGES_PER_LISTING = 60
DELAY_SECONDS = 1.0
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "posts.json"

DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s+(\d{4})\b"
)
PAGE_PARAM_RE = re.compile(r"[?&]([a-z0-9]+_page)=(\d+)")

session = requests.Session()
session.headers["User-Agent"] = "web-reader personal RSS-style fetcher (1 req/sec, daily)"


def fetch(url: str) -> str | None:
    """Fetch a page; returns HTML or None. Replaced in tests."""
    try:
        r = session.get(url, timeout=30)
        time.sleep(DELAY_SECONDS)
        if r.status_code == 200:
            return r.text
        print(f"  ! {r.status_code} {url}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"  ! {e} {url}", file=sys.stderr)
    return None


def parse_date(text: str) -> str | None:
    m = DATE_RE.search(text or "")
    if not m:
        return None
    mon, day, year = m.group(1)[:3], m.group(2), m.group(3)
    try:
        return datetime.strptime(f"{mon} {day} {year}", "%b %d %Y").date().isoformat()
    except ValueError:
        return None


def canonical(href: str) -> str | None:
    """Return a clean absolute post URL, or None if href isn't a blog post."""
    url = urljoin(BASE + "/", href)
    p = urlparse(url)
    if p.netloc.replace("www.", "") != "kipi.ai":
        return None
    path = p.path.rstrip("/")
    if not path.startswith(POST_PATH_PREFIX) or path == POST_PATH_PREFIX.rstrip("/"):
        return None
    return BASE + path


def parse_listing(html: str, page_url: str):
    """Returns ({post_url: listing_date_or_None}, [next page urls])."""
    soup = BeautifulSoup(html, "html.parser")
    posts: dict[str, str | None] = {}
    for a in soup.find_all("a", href=True):
        url = canonical(a["href"])
        if not url:
            continue
        # Look for a date in the link itself or its nearest container
        date = parse_date(a.get_text(" ", strip=True))
        node = a
        for _ in range(4):
            if date or node.parent is None:
                break
            node = node.parent
            # stop if this container holds several post links (date would be ambiguous)
            if len({canonical(x["href"]) for x in node.find_all("a", href=True)} - {None}) > 1:
                break
            date = parse_date(node.get_text(" ", strip=True))
        if url not in posts or (date and not posts[url]):
            posts[url] = date
    pages = set()
    for a in soup.find_all("a", href=True):
        if PAGE_PARAM_RE.search(a["href"]):
            pages.add(urljoin(page_url, a["href"]))
    return posts, sorted(pages)


def crawl_listing(start_url: str) -> dict[str, str | None]:
    seen_pages, queue, found = set(), [start_url], {}
    while queue and len(seen_pages) < MAX_PAGES_PER_LISTING:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        html = fetch(url)
        if not html:
            continue
        posts, next_pages = parse_listing(html, url)
        for u, d in posts.items():
            if u not in found or (d and not found[u]):
                found[u] = d
        queue.extend(p for p in next_pages if p not in seen_pages)
    print(f"  {start_url}: {len(seen_pages)} page(s), {len(found)} post link(s)")
    return found


def meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def parse_post(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = meta(soup, "og:title") or (soup.h1.get_text(strip=True) if soup.h1 else None)
    if title:
        title = re.sub(r"\s*[|\-–]\s*kipi\.ai\s*$", "", title, flags=re.I).strip()
    date = parse_date(meta(soup, "article:published_time") or "")
    if not date:
        # first date-looking text near the top of the article body
        main = soup.find("main") or soup.body or soup
        date = parse_date(main.get_text(" ", strip=True)[:4000])
    return {
        "title": title,
        "description": meta(soup, "og:description", "description"),
        "image": meta(soup, "og:image"),
        "date": date,
    }


def slug_title(url: str) -> str:
    return url.rsplit("/", 1)[-1].replace("-", " ").capitalize()


def load() -> dict:
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text())
        return {p["url"]: p for p in data.get("posts", [])}
    return {}


def save(posts: dict):
    ordered = sorted(posts.values(), key=lambda p: (p.get("date") or "", p["first_seen"]), reverse=True)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(ordered),
        "categories": list(CATEGORIES.values()),
        "posts": ordered,
    }, indent=1, ensure_ascii=False) + "\n")


def notify_telegram(new_posts: list[dict]):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat and new_posts):
        return
    lines = [f"📰 {len(new_posts)} new kipi.ai post(s):"]
    for p in new_posts[:10]:
        lines.append(f"• {p['title']}\n  {p['url']}")
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": "\n".join(lines),
                            "disable_web_page_preview": True}, timeout=20)
    except requests.RequestException as e:
        print(f"  ! telegram: {e}", file=sys.stderr)


def run():
    posts = load()
    first_run = not posts
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("Crawling main listing…")
    listing = crawl_listing(LISTING)
    cat_map: dict[str, set] = {}
    for slug, name in CATEGORIES.items():
        print(f"Crawling category: {name}")
        for u, d in crawl_listing(CATEGORY_URL.format(slug=slug)).items():
            cat_map.setdefault(u, set()).add(name)
            if u not in listing or (d and not listing[u]):
                listing[u] = d

    if not listing:
        print("No posts found — site layout may have changed. Leaving data untouched.")
        sys.exit(1)

    new_posts = []
    for url, list_date in listing.items():
        cats = sorted(cat_map.get(url, set()))
        if url in posts:
            p = posts[url]
            p["categories"] = sorted(set(p.get("categories", [])) | set(cats))
            if not p.get("date") and list_date:
                p["date"] = list_date
            continue
        print(f"  + {url}")
        detail = parse_post(fetch(url) or "")
        p = {
            "url": url,
            "title": detail["title"] or slug_title(url),
            "description": detail["description"],
            "image": detail["image"],
            "date": list_date or detail["date"],
            "categories": cats,
            "first_seen": now,
        }
        posts[url] = p
        new_posts.append(p)

    save(posts)
    print(f"Done: {len(posts)} posts total, {len(new_posts)} new.")
    if not first_run:  # don't spam 100 posts on the first backfill
        notify_telegram(new_posts)


if __name__ == "__main__":
    run()
