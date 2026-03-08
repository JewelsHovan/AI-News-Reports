# AI News Reports - Project Notes

## Current State

- **Architecture**: Agent SDK pipeline (`src/ai_news/`) with 8 fetchers, Agent SDK analysis, and publishing
- **Entry point**: `python -m ai_news --days 2 [--dry-run] [--skip-newsletter] [--skip-upload]`
- **Tests**: 88 passing tests in `tests/`
- **Config**: `email_config.json` at project root (gitignored), `recipients.json` at project root (gitignored)

## Key Decisions

- Migrated from Claude Code skill-based workflow to standalone Agent SDK app (2026-03-06)
- Legacy skill removed (2026-03-07, ticket #001)
- Uses `uv` for Python dependency management
- Agent SDK uses `claude-sonnet-4-5` for subagents

## Frequently Referenced

- `src/ai_news/pipeline.py` - Main orchestrator
- `src/ai_news/analysis/agents.py` - Agent SDK integration
- `src/ai_news/config.py` - PipelineConfig
- `email_config.example.json` - Template for email configuration
