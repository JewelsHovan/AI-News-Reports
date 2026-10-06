"""One-off: bring existing archive entries up to date with listing metadata
(issue title + number, headline, TL;DR, top stories, tags) and the new title.

Listing fields come from the matching reports/*.md file. Editorial issue titles
for issues published before the report generator wrote them come from
reports/issue_titles.json, which --generate-titles fills using Claude Haiku so
you can review or edit it before applying.

    uv run python scripts/backfill_archive_meta.py --generate-titles  # write issue_titles.json
    uv run python scripts/backfill_archive_meta.py                    # preview
    uv run python scripts/backfill_archive_meta.py --apply            # PATCH live archive
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests
from claude_agent_sdk import ClaudeAgentOptions

from ai_news.analysis.agents import _run_single_query
from ai_news.publishing.cloudflare import _generate_default_title, issue_number_for
from ai_news.publishing.listing import MAX_ISSUE_TITLE_CHARS, extract_listing

REPO_ROOT = Path(__file__).resolve().parent.parent
TITLES_PATH = REPO_ROOT / "reports" / "issue_titles.json"
DEFAULT_API_BASE = "https://ai-news-signup.julienh15.workers.dev"
TITLE_MODEL = "claude-haiku-4-5-20251001"

TITLE_PROMPT = """You write issue titles for "Julien's AI Brief", a twice-weekly AI newsletter.
For each issue below, write one editorial title:
- 4-9 words, sentence case, no trailing period, no quotes, no dates, never "AI News" or the newsletter name.
- Name 1-3 of that issue's biggest stories concretely (companies, models, numbers),
  e.g. "Le Chonk, the agent budget trap and a $40B chip bet".
- Wry or vivid is welcome; clickbait, vague teasers and words like "seismic", "watershed",
  "inflection point", "paradigm shift" are not. Vary the structure across issues.

Return ONLY a JSON object mapping each issue key to its title, no prose, no code fence.

ISSUES:
{issues}"""


def range_key(report: dict) -> str:
    return f"{report['date_range_start']}_to_{report['date_range_end']}"


def md_path_for(report: dict) -> Path:
    return REPO_ROOT / "reports" / f"ai-news_{range_key(report)}.md"


def load_titles() -> dict[str, str]:
    return json.loads(TITLES_PATH.read_text(encoding="utf-8")) if TITLES_PATH.exists() else {}


def issue_context(report: dict, api_base: str) -> str:
    """Short text describing an issue: listing fields if we have the markdown,
    otherwise the start of the archived HTML."""
    md_path = md_path_for(report)
    if md_path.exists():
        listing = extract_listing(md_path.read_text(encoding="utf-8"))
        if listing.issue_title:
            return ""  # already titled by the generator
        if listing.top_stories:
            return f"Summary: {listing.tldr}\nTop stories: " + " | ".join(listing.top_stories)
    resp = requests.get(f"{api_base}/archive/{report['id']}", timeout=30)
    resp.raise_for_status()
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", resp.text, flags=re.S | re.I)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()[:1800]


def generate_titles(reports: list[dict], api_base: str) -> int:
    titles = load_titles()
    pending: dict[str, str] = {}
    for report in reports:
        key = range_key(report)
        if key in titles or key in pending:
            continue
        context = issue_context(report, api_base)
        if context:
            pending[key] = context
    if not pending:
        print("All issues already have titles.")
        return 0

    issues = "\n\n".join(f"[{key}]\n{context}" for key, context in sorted(pending.items()))
    options = ClaudeAgentOptions(model=TITLE_MODEL, max_turns=1, max_budget_usd=1.0, permission_mode="bypassPermissions")
    print(f"Asking {TITLE_MODEL} for {len(pending)} titles...")
    raw = asyncio.run(_run_single_query(TITLE_PROMPT.format(issues=issues), options))
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        print(f"Model returned no JSON:\n{raw[:500]}", file=sys.stderr)
        return 1
    generated = json.loads(match.group(0))

    for key in pending:
        title = str(generated.get(key, "")).strip().strip("\"'“”").rstrip(".")
        if title:
            titles[key] = title[:MAX_ISSUE_TITLE_CHARS]
            print(f"  {key}: {titles[key]}")
        else:
            print(f"  {key}: (no title returned)", file=sys.stderr)
    TITLES_PATH.write_text(json.dumps(dict(sorted(titles.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {TITLES_PATH.relative_to(REPO_ROOT)}; review/edit, then run with --apply.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="PATCH the live archive (default: dry run)")
    parser.add_argument("--generate-titles", action="store_true", help=f"Fill {TITLES_PATH.name} for untitled issues, then exit")
    parser.add_argument("--only-missing", action="store_true", help="Skip entries that already have an issue title")
    # Each PATCH rewrites the whole KV index; KV reads can briefly lag writes, so
    # back-to-back PATCHes can overwrite each other. Space them out.
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between PATCHes (default: 3)")
    args = parser.parse_args()

    api_base = os.environ.get("AI_NEWS_API_BASE_URL", DEFAULT_API_BASE).rstrip("/")
    secret = os.environ.get("ADMIN_API_SECRET")
    if args.apply and not secret:
        print("ADMIN_API_SECRET is required with --apply", file=sys.stderr)
        return 1

    resp = requests.get(f"{api_base}/archive", timeout=30)
    resp.raise_for_status()
    all_reports = resp.json()["data"]["reports"]

    if args.generate_titles:
        return generate_titles(all_reports, api_base)

    titles = load_titles()
    reports = [r for r in all_reports if not (args.only_missing and r.get("issue_title"))]

    updated = failed = 0
    for report in reports:
        start, end = report["date_range_start"], report["date_range_end"]
        body: dict = {
            "title": _generate_default_title(start, end),
            "issue_number": issue_number_for(all_reports, start, end),
        }
        md_path = md_path_for(report)
        if md_path.exists():
            listing = extract_listing(md_path.read_text(encoding="utf-8"))
            body.update({k: v for k, v in listing.to_dict().items() if v})
        if "issue_title" not in body and range_key(report) in titles:
            body["issue_title"] = titles[range_key(report)]

        print(f"#{body['issue_number']:<3} {report['id']}  {body.get('issue_title', '(no issue title)')}")

        if not args.apply:
            continue
        patch = requests.patch(
            f"{api_base}/archive/{report['id']}",
            json=body,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=30,
        )
        time.sleep(args.delay)
        if patch.ok:
            updated += 1
        else:
            failed += 1
            print(f"    PATCH failed: HTTP {patch.status_code} {patch.text[:200]}", file=sys.stderr)

    titled = sum(1 for r in reports if range_key(r) in titles or (md_path_for(r).exists() and extract_listing(md_path_for(r).read_text(encoding="utf-8")).issue_title))
    mode = "applied" if args.apply else "dry run"
    print(f"\n{len(reports)} entries ({mode}): {titled} with an issue title"
          + (f"; {updated} updated, {failed} failed" if args.apply else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
