# 003: Project README & Architecture Documentation

**Priority**: Medium
**Complexity**: Low
**Status**: Ready
**Blocked By**: 001, 002

## Description

Write a clean project README.md and optionally a docs/ARCHITECTURE.md that explains the Agent SDK pipeline, how to set up, run, and schedule it. Replaces the old `.claude/skills/ai-news/references/ARCHITECTURE.md`.

## Why

After removing the legacy skill (001) and adding the new scheduling scripts (002), the repo needs documentation that tells someone cloning it exactly how to get started. Currently there's no root README.md at all.

## Scope

### `README.md` (project root)
- One-paragraph description of what the project does
- Quick start: `uv sync`, env vars needed, `uv run python -m ai_news --dry-run`
- Scheduling: `./scripts/setup_schedule.sh` (link to 002)
- Project structure overview (tree of key directories)
- Configuration: env vars, `.env` file, what each var controls
- Development: running tests (`uv run pytest`), adding fetchers

### `docs/ARCHITECTURE.md` (optional, if README gets too long)
- Pipeline flow: Fetch → Analyze (Agent SDK) → Publish
- Fetcher architecture: base class, how to add new sources
- Agent SDK integration: exploration → consolidation → report generation
- Publishing chain: persist → render HTML → upload Cloudflare → send newsletter
- Budget allocation breakdown

### Clean up existing docs/
- `docs/` currently contains the static website files (landing page, archive, CSS)
- Architecture docs should either go in `docs/` clearly separated, or stay in README
- Don't touch the website files

## Affected Files

- `README.md` (new)
- `docs/ARCHITECTURE.md` (new, optional)

## Acceptance Criteria

- [ ] README.md exists with setup, run, and schedule instructions
- [ ] Someone can clone the repo and get running by following the README
- [ ] No references to the old skill-based workflow
- [ ] Architecture overview covers the 3-phase pipeline

## Notes

- Keep it concise — this is a personal project, not an open-source library
- Reference the env vars that `src/ai_news/config.py:PipelineConfig.from_env()` expects
- The `ai-news-signup/` subdirectory is a separate Cloudflare Worker for the newsletter signup — mention briefly but don't document in detail
