"""One-off: add listing metadata (headline, TL;DR, top stories, tags) and the new
title to existing archive entries, parsed from the matching reports/*.md file.

Dry run by default; pass --apply to PATCH the live archive.

    uv run python scripts/backfill_archive_meta.py           # preview
    uv run python scripts/backfill_archive_meta.py --apply   # write
"""

import argparse
import os
import sys
from pathlib import Path

import requests

from ai_news.publishing.cloudflare import _generate_default_title
from ai_news.publishing.listing import extract_listing

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_BASE = "https://ai-news-signup.julienh15.workers.dev"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="PATCH the live archive (default: dry run)")
    args = parser.parse_args()

    api_base = os.environ.get("AI_NEWS_API_BASE_URL", DEFAULT_API_BASE).rstrip("/")
    secret = os.environ.get("ADMIN_API_SECRET")
    if args.apply and not secret:
        print("ADMIN_API_SECRET is required with --apply", file=sys.stderr)
        return 1

    resp = requests.get(f"{api_base}/archive", timeout=30)
    resp.raise_for_status()
    reports = resp.json()["data"]["reports"]

    updated = skipped = failed = 0
    for report in reports:
        start, end = report["date_range_start"], report["date_range_end"]
        md_path = REPO_ROOT / "reports" / f"ai-news_{start}_to_{end}.md"
        body: dict = {"title": _generate_default_title(start, end)}

        if md_path.exists():
            listing = extract_listing(md_path.read_text(encoding="utf-8"))
            body.update({k: v for k, v in listing.to_dict().items() if v})
        has_listing = "headline" in body

        label = f"{report['id']}  {start}..{end}"
        print(f"{'+' if has_listing else '-'} {label}  {body.get('headline', '(title only: no report markdown)')}")
        if body.get("tags"):
            print(f"    tags: {', '.join(body['tags'])}")
        if not has_listing:
            skipped += 1

        if not args.apply:
            continue
        patch = requests.patch(
            f"{api_base}/archive/{report['id']}",
            json=body,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=30,
        )
        if patch.ok:
            updated += 1
        else:
            failed += 1
            print(f"    PATCH failed: HTTP {patch.status_code} {patch.text[:200]}", file=sys.stderr)

    mode = "applied" if args.apply else "dry run"
    print(f"\n{len(reports)} entries ({mode}): {len(reports) - skipped} with listing, {skipped} title-only"
          + (f"; {updated} updated, {failed} failed" if args.apply else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
