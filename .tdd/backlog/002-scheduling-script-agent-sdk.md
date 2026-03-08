# 002: Create Scheduling Script for Agent SDK Pipeline

**Priority**: High
**Complexity**: Medium
**Status**: Completed
**Completed**: 2026-03-07
**Files Changed**: 3 new, 1 modified
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

- [x] `./scripts/run_pipeline.sh` runs the Agent SDK pipeline end-to-end
- [x] `./scripts/setup_schedule.sh` installs launchd schedule with correct paths
- [x] `./scripts/uninstall_schedule.sh` cleanly removes the schedule
- [x] Works after fresh `git clone` + `uv sync` on any macOS machine
- [x] Schedule fires on Mondays and Thursdays at 8 AM
- [x] Logs are written to `logs/`
- [x] Scripts are portable (no hardcoded `/Users/julien.hovan/...` paths)

## Notes

- The old plist at `.claude/skills/ai-news/config/com.ainews.pipeline.plist` has hardcoded paths — the new setup should derive paths from repo location
- Consider adding a `scripts/README.md` with quick-start instructions
- `uv` must be installed on the target machine — `setup_schedule.sh` should check for it
- The `.env` file is gitignored, so new machine setup needs env var documentation

## Implementation Plan

### File 1: `scripts/run_pipeline.sh` — Main runner
- `set -euo pipefail`, resolves repo root via `SCRIPT_DIR/../`
- Logs to `logs/pipeline_YYYYMMDD_HHMMSS.log` via `exec > >(tee -a)` redirect
- Sources `.env` using `set -a / set +a` pattern if present
- Checks `uv` is available before running
- Runs `uv run python -m ai_news --days ${AI_NEWS_DAYS:-3}`
- Captures exit code; git commit block present but commented out
- Exit 0 on success, 1 on failure

### File 2: `scripts/setup_schedule.sh` — Launchd installer
- Generates plist dynamically using current repo path (no hardcoded paths)
- Idempotent: `launchctl bootout` before reinstall, `|| true` on bootout failure
- Cleans up stale old plists (`com.ainews.newsletter.plist`)
- PATH in plist: `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`
- HOME set explicitly in plist env vars
- Uses modern `launchctl bootstrap/bootout gui/$(id -u)` (not deprecated load/unload)
- StartCalendarInterval: array of 2 dicts — Weekday 1 (Monday), Weekday 4 (Thursday), Hour 8, Minute 0
- Verifies runner script exists, checks uv, chmod +x runner

### File 3: `scripts/uninstall_schedule.sh` — Clean uninstall
- `launchctl bootout` + remove plist
- Also cleans up old `com.ainews.newsletter.plist` if present
- Confirmation message

### Testing
1. `bash -n` syntax check all 3 scripts
2. Manual `run_pipeline.sh` invocation, verify log created
3. `setup_schedule.sh` twice (idempotency)
4. Verify plist content + `launchctl list | grep ainews`
5. `uninstall_schedule.sh` + confirm cleanup
6. chmod +x all scripts before commit

Full plan details: `.claude-plans/ticket-002-scheduling-scripts.md`

## AI Review Summary

**Reviewers**: Pre-Mortem Analyst, Blindspot Detector
**Confidence**: Medium → High (after mitigations)

### MUST-FIX (both flagged)
1. **uv PATH detection**: Detect actual `uv` location at setup time, prepend its directory to plist PATH
2. **Working directory**: Already in plan — confirmed correct (plist WorkingDirectory + explicit cd)

### SHOULD-FIX (critical severity or both flagged)
1. **ANTHROPIC_API_KEY check**: Fail fast in run_pipeline.sh before invoking pipeline
2. **Lockfile guard**: Prevent concurrent runs via `mkdir` lockfile + trap cleanup
3. **Failure notification**: `osascript` desktop notification on pipeline failure
4. **Log rotation**: Keep last 30 log files, delete older ones in run_pipeline.sh

### EVALUATE (noted, not applied)
- `--dry-run` env var passthrough (LOW — users can edit script or run manually)
- Smoke test in setup_schedule.sh (LOW — useful but not critical)
- Keychain headless documentation (LOW — comment in setup script)
