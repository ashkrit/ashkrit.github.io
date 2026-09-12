#!/usr/bin/env python3
"""Regenerate data/posts.json and data/repos.json from Blogger and GitHub.

Standard library only, so the workflow needs no dependency install step.
Run from anywhere: paths resolve relative to the repo root.
"""

import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

BLOG_FEED = "https://ashkrit.blogspot.com/feeds/posts/default"
GITHUB_USER = "ashkrit"
EXCERPT_CHARS = 200
MAX_PAGES = 40  # guard against a misbehaving feed paginating forever

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", "ashkrit.github.io-sync")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def excerpt(content_html):
    """Strip markup from post HTML and truncate on a word boundary."""
    text = TAG_RE.sub(" ", content_html or "")
    text = WS_RE.sub(" ", html.unescape(text)).strip()
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[:EXCERPT_CHARS]
    space = cut.rfind(" ")
    if space > EXCERPT_CHARS // 2:
        cut = cut[:space]
    return cut.rstrip(" .,;:") + "…"


def post_url(entry):
    for link in entry.get("link", []):
        if link.get("rel") == "alternate" and link.get("type") == "text/html":
            return link.get("href")
    return None


def fetch_posts():
    """Page through the Blogger feed.

    Blogger silently caps max-results far below whatever is requested (asking
    for 500 yields ~25), so advance start-index by however many entries each
    page actually returned rather than by a fixed page size.
    """
    posts = []
    start = 1
    total = None
    for _ in range(MAX_PAGES):
        url = f"{BLOG_FEED}?alt=json&max-results=150&start-index={start}"
        feed = fetch_json(url).get("feed", {})
        if total is None:
            try:
                total = int(feed["openSearch$totalResults"]["$t"])
            except (KeyError, ValueError, TypeError):
                total = 0
        entries = feed.get("entry", [])
        if not entries:
            break
        for entry in entries:
            url_ = post_url(entry)
            if not url_:
                continue
            post = {
                "title": entry.get("title", {}).get("$t", "").strip(),
                "url": url_,
                "published": entry.get("published", {}).get("$t", ""),
                "labels": [c["term"] for c in entry.get("category", []) if c.get("term")],
                "excerpt": excerpt(entry.get("content", {}).get("$t", "")),
            }
            thumb = entry.get("media$thumbnail", {}).get("url")
            if thumb:
                post["thumbnail"] = thumb
            posts.append(post)
        start += len(entries)
        if total and len(posts) >= total:
            break

    if not posts:
        raise RuntimeError("blog feed returned no posts")

    posts.sort(key=lambda p: p["published"], reverse=True)

    labels = {}
    for post in posts:
        for label in post["labels"]:
            labels[label] = labels.get(label, 0) + 1

    return {
        "source": "https://ashkrit.blogspot.com",
        "total": len(posts),
        "labels": dict(sorted(labels.items(), key=lambda kv: (-kv[1], kv[0].lower()))),
        "posts": posts,
    }


def fetch_repos():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/users/{GITHUB_USER}/repos?sort=updated&per_page=100"
    raw = fetch_json(url, headers)
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("github api returned no repos")

    repos = [
        {
            "name": r["name"],
            "description": (r.get("description") or "").strip(),
            "url": r["html_url"],
            "language": r.get("language") or "",
            "stars": r.get("stargazers_count", 0),
            "topics": r.get("topics") or [],
            "pushed_at": r.get("pushed_at") or "",
        }
        for r in raw
        if not r.get("fork") and not r.get("archived") and r["name"] != f"{GITHUB_USER}.github.io"
    ]
    # Stable sorts: stars descending, ties broken by most recently pushed.
    repos.sort(key=lambda r: r["pushed_at"], reverse=True)
    repos.sort(key=lambda r: r["stars"], reverse=True)

    return {
        "source": f"https://github.com/{GITHUB_USER}",
        "total": len(repos),
        "repos": repos,
    }


def write(name, payload):
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def main():
    os.makedirs(DATA, exist_ok=True)
    failures = []

    for name, fetcher in (("posts.json", fetch_posts), ("repos.json", fetch_repos)):
        try:
            payload = fetcher()
        except (urllib.error.URLError, json.JSONDecodeError, RuntimeError, KeyError) as exc:
            # Leave the existing file alone; a bad upstream must never blank the site.
            failures.append(f"{name}: {exc}")
            print(f"FAIL  {name}: {exc}", file=sys.stderr)
            continue
        write(name, payload)
        print(f"ok    {name}: {payload['total']} items")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
