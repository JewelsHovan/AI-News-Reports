# 001: Remove Legacy Skill & Clean Up Project Structure

**Priority**: High
**Complexity**: Medium
**Status**: Completed
**Completed**: 2026-03-07
**Files Changed**: 2 new, 4 modified, 28 deleted

## Description

Remove the superseded Claude Code skill-based workflow and clean up the project root so the repo is clear and self-explanatory. After this, the only way to run the pipeline is via the Agent SDK app (`python -m ai_news`).

## Why

The legacy `.claude/skills/ai-news/` directory contains ~20 files (scripts, configs, sent logs, architecture docs) that duplicate functionality now in `src/ai_news/`. This creates confusion about which is the "real" pipeline and bloats the repo. The project should be clean enough that cloning it on a new machine is immediately understandable.

## Scope

### Delete entirely
- `.claude/skills/ai-news/` — all scripts, SKILL.md, references/, config/ (see migration notes below)
- `run.sh` — references the old skill, replaced by `uv run python -m ai_news`
- `plans/` — old planning docs (`ai-news-report-improvements.md`, `archive-feature.md`, `subagent-driven-ai-news.md`), superseded by `.claude-plans/`
- `.claude-plans/agent-sdk-conversion.md` — completed migration plan, no longer needed

### Clean up root clutter
- Remove `ai_news_report_*.md` pattern (generated copies that belong in `reports/`)
- Remove `sent_log_*.txt` at root level
- Remove `email_config.json` at root level (duplicate of the one in skills)
- Remove `src/ai_news.egg-info/` directory (build artifact)

### Migrate before deleting (investigate first)
- `.claude/skills/ai-news/config/email_config.json` → check if `src/ai_news/config.py` already handles this via env vars or a different path. If a config file is still needed, move to project root or `config/` dir.
- `.claude/skills/ai-news/config/recipients.json` → same investigation
- `.claude/skills/ai-news/config/com.ainews.pipeline.plist` → will be replaced by ticket 002

### Update .gitignore
- Remove references to `.claude/skills/ai-news/config/sent_log_*.txt` and `.claude/skills/ai-news/config/email_config.json`
- Keep patterns for root-level `sent_log_*.txt` and `email_config.json`
- Add `.tdd/` if not already ignored (or keep tracked — team preference)

## Affected Files

- `.claude/skills/ai-news/**` (delete)
- `run.sh` (delete)
- `plans/` (delete)
- `.claude-plans/` (delete completed plans)
- `.gitignore` (update)
- `pyproject.toml` (no changes expected)

## Acceptance Criteria

- [x] `.claude/skills/ai-news/` directory is gone
- [x] `run.sh` and `plans/` are gone
- [x] No orphaned config files at project root
- [x] `.gitignore` is clean and accurate
- [x] `uv run python -m ai_news --dry-run` still works
- [x] All 88 tests still pass
- [x] Repo structure is self-explanatory for someone cloning fresh

## Notes

- Check `src/ai_news/config.py` and `src/ai_news/publishing/newsletter.py` for any hardcoded paths referencing `.claude/skills/ai-news/`
- The `logs/` directory can stay as-is for now (low priority cleanup)
- Blocked by: nothing
- Blocks: 002 (scheduling script needs clean structure)

## Implementation Plan

### Pre-deletion migration
1. Copy `.claude/skills/ai-news/config/recipients.json` → project root (modern pipeline resolves it at `email_config_path.parent / "recipients.json"` = project root)
2. Copy `.claude/skills/ai-news/config/email_config.json` → `email_config.example.json` at project root (sanitized template for onboarding — strip secrets, keep structure)
3. Update `.gitignore` BEFORE step 1 completes: add `recipients.json` entry so the file is never tracked

### Launchd cleanup
4. Check if `com.ainews.pipeline` plist is loaded (`launchctl list | grep ainews`), unload if so

### Deletions (use `rm -rf` for directories with untracked files like `__pycache__/`)
5. Delete `.claude/skills/ai-news/` — entire directory (zero references from `src/ai_news/`)
6. Delete `run.sh` — references old skill, replaced by `uv run python -m ai_news`
7. `git rm -r plans/` — 3 historical planning docs, tracked in git
8. Delete `.claude-plans/agent-sdk-conversion.md` — filesystem only (gitignored)
9. Delete root-level `ai_news_report_2026-03-07.md` — filesystem only (gitignored)
10. Delete root-level `sent_log_2026-03-07.txt` — filesystem only (gitignored)
11. Delete `src/ai_news.egg-info/` if present — build artifact

### .gitignore cleanup (edit by content, not line numbers)
12. Remove entry `.claude/skills/ai-news/config/sent_log_*.txt` — path no longer exists
13. Remove entry `.claude/skills/ai-news/config/email_config.json` — path no longer exists
14. Add `recipients.json` to gitignore (contains PII — email addresses)

### Collateral cleanup
15. Remove stale `Skill(ai-news)` entries from `.claude/settings.local.json`
16. Update `.tdd/NOTES.md` — remove legacy path references, mark skill as removed
17. Add comment to `.github/workflows/publish-archive.yml` noting legacy scripts were removed

### Verify
18. Run `uv run python -m ai_news --dry-run` — confirm pipeline still works
19. Run `uv run pytest` — confirm all 88 tests pass

## AI Review Summary

**Reviewers**: Pre-Mortem Analyst, Blindspot Detector
**Confidence**: Medium → High (after mitigations applied)

### MUST-FIX (both reviewers flagged)
- `recipients.json` ordering: gitignore BEFORE copying to prevent accidental commit of PII

### SHOULD-FIX (applied)
- Check/unload launchd plist before deleting skill directory
- Use content-matching for gitignore edits (not line numbers)
- Clean up stale `Skill(ai-news)` permission in `.claude/settings.local.json`
- Update `.tdd/NOTES.md` to remove legacy references
- Copy `email_config.example.json` to root for onboarding
- Add comment to disabled workflow noting script removal
- Use `rm -rf` for directories with untracked `__pycache__/` files

### EVALUATE (noted, not applied)
- Move `recipients.json` resolution to explicit config key (future improvement)
- Add dedicated log directory for `sent_log_*.txt` (future improvement)
