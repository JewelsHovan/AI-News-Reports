# AI News Reports

Personal pipeline that fetches AI news from 8 sources, analyzes with Claude Agent SDK, and publishes a digest via email newsletter and web archive.

## How it works

- **Fetch**: 8 async fetchers run concurrently (HuggingFace papers, Reddit, Hacker News, TechCrunch, AI News, The Batch, smol.ai, Simon Willison)
- **Analyze**: Claude Agent SDK (`claude-sonnet-4-5`) — 4 exploration agents, 3 consolidation agents, 1 report generator
- **Publish**: Save `.md` report, render HTML, upload to Cloudflare archive, send newsletter via Microsoft Graph

## Setup

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/), Anthropic API key

```bash
git clone https://github.com/JewelsHovan/AI-News-Reports.git
cd AI-News-Reports
uv sync
```

Copy `email_config.example.json` to `email_config.json` and fill in your Azure AD credentials (only needed for the newsletter).

## Configuration

Set via `.env` file or environment variables:

| Variable | Default | Required | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | -- | Yes | Claude API key |
| `AI_NEWS_DAYS` | `2` | No | Days to look back for news |
| `AI_NEWS_MAX_BUDGET_USD` | `5.0` | No | Max Claude API spend per run (USD) |
| `AI_NEWS_DRY_RUN` | `false` | No | Skip upload and newsletter |
| `ADMIN_API_SECRET` | -- | No | Cloudflare Worker admin secret (enables upload + subscriber fetch) |
| `AI_NEWS_API_BASE_URL` | `https://ai-news-signup.julienh15.workers.dev` | No | Cloudflare Worker base URL |
| `AI_NEWS_EMAIL_CONFIG_PATH` | `email_config.json` | No | Path to email/MSAL config |
| `AI_NEWS_REPORTS_DIR` | `reports/` | No | Report output directory |
| `AI_NEWS_PROJECT_ROOT` | auto-detected | No | Project root override |

## Usage

```
uv run python -m ai_news [options]
```

| Flag | Description |
|---|---|
| `--days N` | Days to look back (default: 2) |
| `--dry-run` | Skip upload and newsletter |
| `--skip-newsletter` | Skip newsletter only |
| `--skip-upload` | Skip Cloudflare upload only |
| `--verbose`, `-v` | Debug logging |

## Scheduling (macOS)

```bash
./scripts/setup_schedule.sh      # Install launchd job (Mon + Thu, 08:00)
./scripts/uninstall_schedule.sh  # Remove it
```

## Project structure

```
src/ai_news/
  fetchers/        # 8 source-specific fetchers
  analysis/        # Agent SDK pipeline (exploration -> consolidation -> report)
  publishing/      # persist -> render HTML -> upload -> send newsletter
  config.py        # PipelineConfig, env var loading
  pipeline.py      # Main orchestrator
scripts/           # Scheduling scripts (launchd)
tests/             # pytest suite
reports/           # Generated reports + manifest.jsonl
docs/              # Static website (landing page, archive)
ai-news-signup/    # Cloudflare Worker for subscriber management (TypeScript)
```

## Development

```bash
uv run pytest
```

88 tests covering fetchers, analysis, publishing, and pipeline orchestration.
