#!/usr/bin/env python3
"""Download article corpus from a YAML source list.

Extracts main article text and saves markdown files to corpus/raw/ (or a custom
output dir). Change --limit and corpus/sources.yaml to scale from 15 to 50+ articles.

Install deps:
    pip install trafilatura pyyaml requests

Examples:
    python scripts/scrape_corpus.py --limit 15
    python scripts/scrape_corpus.py --limit 50 --config corpus/sources.yaml
    python scripts/scrape_corpus.py --dry-run
    python scripts/scrape_corpus.py --limit 15 --no-skip-existing
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import trafilatura
import yaml

DEFAULT_CONFIG = Path("corpus/sources.yaml")
USER_AGENT = (
    "Mozilla/5.0 (compatible; LLMWikiCorpusBot/1.0; +personal-research-corpus)"
)


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "articles" not in data:
        raise ValueError(f"No 'articles' list found in {config_path}")
    return data


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "article"


def select_articles(
    articles: list[dict[str, Any]],
    *,
    limit: int | None,
    only_enabled: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in articles:
        if only_enabled and not item.get("enabled", True):
            continue
        if not item.get("url"):
            continue
        selected.append(item)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def fetch_article(url: str, timeout: int = 30) -> tuple[str | None, str | None]:
    """Return (title, markdown_body). Either may be None on failure."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None, None

    html = response.text
    metadata = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        with_metadata=True,
        include_links=True,
        include_tables=True,
        favor_precision=True,
    )
    if not metadata:
        return None, None

    meta = trafilatura.extract_metadata(html, default_url=url)
    page_title = meta.title if meta and meta.title else None
    return page_title, metadata.strip()


def build_markdown(
    *,
    title: str,
    url: str,
    category: str,
    slug: str,
    body: str,
) -> str:
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"source_url: {url}\n"
        f"category: {category}\n"
        f"slug: {slug}\n"
        f"scraped_at: {scraped_at}\n"
        "---\n\n"
    )
    header = f"# {title}\n\n> Source: {url}\n\n"
    return frontmatter + header + body + "\n"


def output_path(output_dir: Path, slug: str, fmt: str) -> Path:
    ext = "md" if fmt == "markdown" else "txt"
    return output_dir / f"{slug}.{ext}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape corpus articles from YAML config")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML source list (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of articles to scrape (default: all enabled in config)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: settings.output_dir in YAML or corpus/raw)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds to wait between requests (default: settings.delay_seconds in YAML)",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip files that already exist (default: from YAML settings)",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Also scrape articles with enabled: false",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned downloads without fetching",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()

    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    config = load_config(config_path)
    settings = config.get("settings", {})
    output_dir = Path(args.output or settings.get("output_dir", "corpus/raw"))
    delay = args.delay if args.delay is not None else float(settings.get("delay_seconds", 2.0))
    skip_existing = (
        args.skip_existing
        if args.skip_existing is not None
        else bool(settings.get("skip_existing", True))
    )
    fmt = settings.get("format", "markdown")

    articles = select_articles(
        config["articles"],
        limit=args.limit,
        only_enabled=not args.include_disabled,
    )

    if not articles:
        print("No articles selected. Check enabled flags and --limit.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Config:  {config_path}")
    print(f"Output:  {output_dir.resolve()}")
    print(f"Limit:   {args.limit if args.limit is not None else 'all selected'}")
    print(f"Queued:  {len(articles)} article(s)\n")

    ok, skipped, failed = 0, 0, 0

    for i, item in enumerate(articles, start=1):
        url = item["url"].strip()
        slug = item.get("slug") or slugify(urlparse(url).path.split("/")[-1])
        category = item.get("category", "uncategorized")
        dest = output_path(output_dir, slug, fmt)

        print(f"[{i}/{len(articles)}] {slug}")
        print(f"         {url}")

        if args.dry_run:
            print(f"         -> would save {dest.name}\n")
            continue

        if skip_existing and dest.exists():
            print(f"         skip (exists): {dest.name}\n")
            skipped += 1
            continue

        title, body = fetch_article(url)
        if not body:
            print("         FAILED: could not extract article text\n", file=sys.stderr)
            failed += 1
            if i < len(articles):
                time.sleep(delay)
            continue

        page_title = title or slug.replace("-", " ").title()
        if fmt == "markdown":
            content = build_markdown(
                title=page_title,
                url=url,
                category=category,
                slug=slug,
                body=body,
            )
        else:
            content = f"{page_title}\nSource: {url}\n\n{body}\n"

        dest.write_text(content, encoding="utf-8")
        print(f"         saved: {dest.name} ({len(content):,} chars)\n")
        ok += 1

        if i < len(articles):
            time.sleep(delay)

    if args.dry_run:
        return 0

    print("Done.")
    print(f"  saved:   {ok}")
    print(f"  skipped: {skipped}")
    print(f"  failed:  {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
