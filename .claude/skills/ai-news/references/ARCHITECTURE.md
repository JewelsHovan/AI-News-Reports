# AI News Aggregator - Multi-Agent Architecture

## Overview

The `/ai-news <days>` command triggers a multi-agent workflow to aggregate, verify, and analyze AI news from the past N days.

## Workflow Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           /ai-news <days>                                    │
│                         (e.g., /ai-news 3)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: PLANNING                                    │
│─────────────────────────────────────────────────────────────────────────────│
│  Main Claude orchestrates the workflow:                                      │
│  • Calculate date range (today - N days)                                    │
│  • Determine which sources to query                                         │
│  • Define search parameters per source                                      │
│  • Spawn parallel executor agents                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: PARALLEL EXECUTION                               │
│─────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Smol.ai    │  │  HuggingFace │  │ Hacker News  │  │   AI-News    │    │
│  │   Agent      │  │    Agent     │  │    Agent     │  │    Agent     │    │
│  │              │  │              │  │              │  │              │    │
│  │ RSS Feed     │  │ /papers/date │  │ Search API   │  │ WebFetch     │    │
│  │ /rss.xml     │  │ /YYYY-MM-DD  │  │ Algolia      │  │ + filter     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                 │                 │                 │             │
│         └─────────────────┴─────────────────┴─────────────────┘             │
│                                    │                                         │
│                        Raw articles/papers                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 3: VERIFICATION                                    │
│─────────────────────────────────────────────────────────────────────────────│
│  Verification Agent checks:                                                  │
│  • Each item falls within requested date range                              │
│  • Remove duplicates (same story across sources)                            │
│  • Validate links are accessible                                            │
│  • Filter non-AI content from Hacker News                                   │
│  • Tag items by topic/category                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 4: CONSOLIDATION & ANALYSIS                         │
│─────────────────────────────────────────────────────────────────────────────│
│  Analysis Agent:                                                             │
│  • Group items by theme/topic                                               │
│  • Identify major trends and narratives                                     │
│  • Connect related stories across sources                                   │
│  • Assess significance and impact                                           │
│  • Extract key takeaways                                                    │
│  • Analyze: "What does this mean for the AI field?"                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 5: REPORT GENERATION                              │
│─────────────────────────────────────────────────────────────────────────────│
│  Format into structured report:                                              │
│  • Executive Summary                                                         │
│  • Key Trends & Themes                                                       │
│  • Notable Papers (HuggingFace)                                             │
│  • Industry News Highlights                                                  │
│  • Community Discussions (HN)                                               │
│  • Analysis & Implications                                                   │
│  • Source Links & References                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 5.1: PERSIST REPORT                                │
│─────────────────────────────────────────────────────────────────────────────│
│  Save report artifacts:                                                     │
│  • Write markdown to reports/ with timestamped filename                     │
│  • Append reports/manifest.jsonl                                            │
│  • Update reports/latest.md                                                 │
│  • Return JSON metadata (filepath, bytes, generated_at)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 5.1: Persist Report
- Write the report to `reports/` with a UTC timestamped filename
- Append metadata to `reports/manifest.jsonl`
- Copy the newest report to `reports/latest.md`
- Emit JSON metadata (including `filepath`) for verification

## News Sources Configuration

### 1. Smol.ai News (https://news.smol.ai/)
- **Type**: AI Newsletter/Digest
- **Access Method**: RSS Feed at `/rss.xml`
- **Date Format**: `MMM DD` (e.g., "Dec 22")
- **URL Pattern**: `/issues/YY-MM-DD-slug`
- **Strengths**: Curated, summarized AI news
- **Script**: `scripts/fetch_smol_news.py`

### 2. HuggingFace Papers (https://huggingface.co/papers)
- **Type**: Research Papers
- **Access Method**: Date-based URL `/papers/date/YYYY-MM-DD`
- **Date Format**: ISO date in URL
- **Data Points**: Title, upvotes, comments, paper ID, organizations
- **Strengths**: Trending research, community votes
- **Script**: `scripts/fetch_hf_papers.py`

### 3. Hacker News (https://news.ycombinator.com/)
- **Type**: Tech Community Discussion
- **Access Method**: Official API (https://hacker-news.firebaseio.com/v0/)
- **Search**: Algolia API (https://hn.algolia.com/api/v1/search)
- **Date Format**: Unix timestamp
- **Filtering**: Search for AI-related keywords
- **Strengths**: Community sentiment, discussions
- **Script**: `scripts/fetch_hn_ai.py`

### 4. Artificial Intelligence News (https://www.artificialintelligence-news.com/)
- **Type**: Industry News
- **Access Method**: WebFetch + parse
- **Date Format**: "Month Day, Year" (e.g., "December 23, 2025")
- **Structure**: WordPress site with `.e-loop-item` selectors
- **Strengths**: Business/enterprise AI coverage
- **Script**: `scripts/fetch_ai_news.py`

## Agent Responsibilities

### Main Orchestrator (Claude Code)
- Parse command arguments
- Calculate date range
- Dispatch parallel agents
- Coordinate workflow phases
- Present final report to user

### Executor Agents (Parallel)
- Run source-specific scripts
- Handle rate limiting and errors
- Return structured JSON data
- Report fetch status

### Verification Agent
- Validate date ranges
- Deduplicate content
- Filter relevance
- Quality control

### Analysis Agent
- Theme extraction
- Trend identification
- Cross-source correlation
- Impact assessment

## Data Schema

Each news item should conform to:

```json
{
  "title": "string",
  "url": "string",
  "source": "smol.ai|huggingface|hackernews|ai-news",
  "date": "YYYY-MM-DD",
  "summary": "string (optional)",
  "score": "number (optional - upvotes/points)",
  "tags": ["string"],
  "authors": ["string (optional)"],
  "discussion_url": "string (optional)"
}
```

## Error Handling

- If a source fails, continue with others
- Report partial results with source status
- Cache successful fetches to avoid re-fetching on retry
- Implement exponential backoff for rate limits

## Output Format

The final report will be structured markdown with:
1. Date range header
2. Executive summary (2-3 paragraphs)
3. Themed sections with linked items
4. Analysis section
5. Full item list with metadata
