#!/usr/bin/env python3
"""Free DuckDuckGo search CLI for the duckduckgo-search optional skill.

Usage:
    search.py "query" [--type text|news|images|videos] [--max N] [--json]

Requires the `ddgs` package. Install with: uv pip install ddgs
"""
from __future__ import annotations

import argparse
import json
import sys


def run(query: str, kind: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        sys.exit("ddgs not installed. Run: uv pip install ddgs")

    with DDGS() as ddgs:
        method = {
            "text": ddgs.text,
            "news": ddgs.news,
            "images": ddgs.images,
            "videos": ddgs.videos,
        }[kind]
        return list(method(query, max_results=max_results))


def main() -> None:
    parser = argparse.ArgumentParser(description="Free DuckDuckGo search.")
    parser.add_argument("query")
    parser.add_argument(
        "--type", dest="kind", default="text",
        choices=["text", "news", "images", "videos"],
    )
    parser.add_argument("--max", dest="max_results", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit raw JSON.")
    args = parser.parse_args()

    results = run(args.query, args.kind, args.max_results)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    for i, r in enumerate(results, 1):
        title = r.get("title") or r.get("source") or "(no title)"
        url = r.get("href") or r.get("url") or r.get("image") or ""
        snippet = r.get("body") or r.get("excerpt") or ""
        print(f"{i}. {title}\n   {url}")
        if snippet:
            print(f"   {snippet[:200]}")


if __name__ == "__main__":
    main()
