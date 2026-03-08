# 002: Create Scheduling Script for Agent SDK Pipeline

**Priority**: High
**Complexity**: Medium
**Status**: Ready
**Blocked By**: 001

## Description

Create a portable scheduling setup that runs the Agent SDK pipeline (`python -m ai_news`) on a weekly schedule (once or twice a week). The setup should be easy to install on any macOS machine after cloning the repo.

## Why

The current scheduling uses a launchd plist that calls `run_full_pipeline.sh`, which in turn invokes `claude -p "/ai-news 2"` (the old skill-based approach). This is broken now that the pipeline is an Agent SDK app. We need a new script that runs `uv run python -m ai_news` directly, plus a simple setup command to install the schedule on any machine.

## Scope

### New files to create

**`scripts/run_pipeline.sh`** — Main runner script
- Runs `uv run python -m ai_news --days 3` (covers gaps for weekly cadence)
- Handles logging to `logs/pipeline_YYYYMMDD_HHMMSS.log`
- Loads env vars from `.env` (dotenv)
- Optional: git add + commit + push `reports/manifest.jsonl` for archive updates
- Exit codes: 0 success, 1 failure
- Should work regardless of where the repo is cloned (use `cd "$(dirname "$0")/.."` pattern)

**`scripts/setup_schedule.sh`** — One-command schedule installer
- Generates a launchd plist from template with correct paths (based on where repo is cloned)
- Schedule: **Mondays and Thursdays at 8:00 AM** local time (two `StartCalendarInterval` entries)
- Installs plist to `~/Library/LaunchAgents/com.ainews.pipeline.plist`
- Runs `launchctl load` to activate
- Prints confirmation with next run time
- Idempotent: unloads existing plist before reinstalling

**`scripts/uninstall_schedule.sh`** — Clean uninstall
- `launchctl unload` + remove plist
- Confirmation message

### Schedule details
- **Frequency**: Monday + Thursday at 8:00 AM local time
- **Days lookback**: 3 days (covers Mon→Thu and Thu→Mon gaps)
- Configurable via env var `AI_NEWS_DAYS` (default: 3)
- Configurable schedule in `setup_schedule.sh` with sensible defaults

### Logging
- Pipeline stdout/stderr → `logs/pipeline_YYYYMMDD_HHMMSS.log`
- Launchd stdout → `logs/launchd.out.log`
- Launchd stderr → `logs/launchd.err.log`
- Keep existing `logs/.gitignore` pattern

## Affected Files

- `scripts/run_pipeline.sh` (new)
- `scripts/setup_schedule.sh` (new)
- `scripts/uninstall_schedule.sh` (new)
- `logs/` (existing, no changes)

## Acceptance Criteria

- [ ] `./scripts/run_pipeline.sh` runs the Agent SDK pipeline end-to-end
- [ ] `./scripts/setup_schedule.sh` installs launchd schedule with correct paths
- [ ] `./scripts/uninstall_schedule.sh` cleanly removes the schedule
- [ ] Works after fresh `git clone` + `uv sync` on any macOS machine
- [ ] Schedule fires on Mondays and Thursdays at 8 AM
- [ ] Logs are written to `logs/`
- [ ] Scripts are portable (no hardcoded `/Users/julien.hovan/...` paths)

## Notes

- The old plist at `.claude/skills/ai-news/config/com.ainews.pipeline.plist` has hardcoded paths — the new setup should derive paths from repo location
- Consider adding a `scripts/README.md` with quick-start instructions
- `uv` must be installed on the target machine — `setup_schedule.sh` should check for it
- The `.env` file is gitignored, so new machine setup needs env var documentation
