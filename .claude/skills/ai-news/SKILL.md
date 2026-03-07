---
name: ai-news
description: >
  Aggregate and analyze AI news from 8 authoritative sources including expert newsletters (Andrew Ng's The Batch),
  research papers (HuggingFace), industry news (TechCrunch, AI News), community discussions (Reddit, Hacker News),
  and context engineering insights (Simon Willison's blog).
  Provides deep trend analysis with expert sentiment and community opinions. This skill should be used when the user
  wants a comprehensive AI news digest, research recent developments, understand community sentiment, or stay updated
  on AI trends. Invoke with `/ai-news <days>` (e.g., `/ai-news 3` for past 3 days).
---

# AI News Aggregator

This skill aggregates AI news from 8 authoritative sources and produces a comprehensive, deeply-analyzed report.
It uses a **subagent-driven workflow** with parallel exploration and consolidation for richer insights.

## Workflow Architecture

```
Phase 1: Planning
    ↓
Phase 2: Parallel Fetching (8 fetchers)
    ↓
Phase 3: Parallel Exploration (4 subagents)
    ├── Community Explorer (Reddit)
    ├── Research Explorer (HuggingFace)
    ├── Industry Explorer (TechCrunch + AI News)
    └── Expert Explorer (The Batch + Simon Willison)
    ↓
Phase 4: Consolidation (3 subagents)
    ├── Story Synthesizer (top stories)
    ├── Trend Synthesizer (major trends)
    └── Implications Synthesizer (actionable insights)
    ↓
Phase 5: Report Generation (main orchestrator)
    ↓
Phase 5.1-5.4: Persist, Render HTML, Upload, Send Newsletter
```

**Why subagents?** With 400+ items from Reddit alone, single-pass analysis produces surface-level insights. Subagents enable:
- **Deeper exploration**: Each agent focuses on one source type
- **Richer synthesis**: Consolidation agents see all exploration outputs
- **Less repetition**: Structured handoffs prevent rehashing the same points

## Usage

```
/ai-news <days>
```

**Arguments:**
- `days` (optional, default: 7) - Number of days to look back from today

**Examples:**
- `/ai-news 3` - Get AI news from the past 3 days
- `/ai-news 7` - Get AI news from the past week
- `/ai-news` - Same as `/ai-news 7`

## News Sources (7 Total)

### Expert & Newsletter Sources
| Source | Type | URL | Value |
|--------|------|-----|-------|
| The Batch | Expert Newsletter | https://www.deeplearning.ai/the-batch/ | Andrew Ng's expert analysis |
| smol.ai | Curated Digest | https://news.smol.ai/ | Daily AI news roundup |

### Research Sources
| Source | Type | URL | Value |
|--------|------|-----|-------|
| HuggingFace Papers | Trending Research | https://huggingface.co/papers | Community-voted papers |

### Industry News
| Source | Type | URL | Value |
|--------|------|-----|-------|
| TechCrunch AI | Startup/Funding | https://techcrunch.com/category/artificial-intelligence/ | VC, launches, M&A |
| AI News | Enterprise | https://www.artificialintelligence-news.com/ | Business adoption |

### Community Sources
| Source | Type | URL | Value |
|--------|------|-----|-------|
| Reddit ML | Community Discussion | r/MachineLearning, r/LocalLLaMA, r/ClaudeAI, r/singularity | Sentiment, hot takes |
| Reddit Prompt Eng | Practitioner Discussion | r/PromptEngineering, r/ChatGPTPromptGenius, r/PromptDesign | Context engineering techniques |
| Hacker News | Dev Discussion | https://news.ycombinator.com/ | Technical discourse |

### Context Engineering Sources
| Source | Type | URL | Value |
|--------|------|-----|-------|
| Simon Willison | Expert Blog | https://simonwillison.net/ | Prompt engineering, agents, MCP, vibe coding |

## Multi-Agent Workflow

Execute this workflow in order:

### Phase 1: Planning (Main Orchestrator)

1. Parse the `<days>` argument (default to 7 if not provided)
2. Calculate the date range: `[today - days, today]`
3. Prepare to spawn 7 parallel executor agents

### Phase 2: Parallel Execution

Spawn agents in parallel using Bash tool, each running one fetcher script:

```bash
# Run all 8 fetchers in parallel (from project root)
uv run python .claude/skills/ai-news/scripts/fetch_smol_news.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_hf_papers.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_hn_ai.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_ai_news.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_techcrunch.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_the_batch.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_reddit_ml.py <days>
uv run python .claude/skills/ai-news/scripts/fetch_simonwillison.py <days>
```

**Key Outputs:**
- Each script returns JSON with items, metadata, and source info
- Reddit script includes `community_sentiment` with hot topics and engagement stats
- The Batch includes expert attribution
- Simon Willison script includes `tags_fetched` and merged categories from multiple tag feeds

### Phase 3: Parallel Exploration (4 Subagents)

After fetching, spawn **4 exploration subagents in parallel** using the Task tool. Each analyzes a specific source type for deep insights.

**IMPORTANT:** Run all 4 Task calls in a single message for parallel execution.

#### Agent 1: Community Explorer
```
<Task subagent_type="Explore" prompt="
You are analyzing Reddit community discussions about AI for a news digest.

INPUT DATA:
{paste Reddit JSON here}

ANALYZE AND RETURN:
1. **Hot Topics** (top 5-7): What topics have highest engagement? Include title, score, subreddit, and why it's generating discussion.

2. **Major Debates**: What are people arguing about? Identify 2-3 key debates with the different positions being taken.

3. **Community Sentiment**: Overall mood (optimistic/skeptical/mixed). What excites people? What concerns them?

4. **Notable Posts**: 5-10 most significant posts with:
   - Title and URL
   - Score and comments
   - Why it matters (1 sentence)
   - Key insight or takeaway

5. **Emerging Interests**: What new topics are gaining traction that weren't hot before?

Return as structured analysis, not raw JSON.
">
```

#### Agent 2: Research Explorer
```
<Task subagent_type="Explore" prompt="
You are analyzing AI research papers from HuggingFace for a news digest.

INPUT DATA:
{paste HuggingFace JSON here}

ANALYZE AND RETURN:
1. **Paper Clusters**: Group papers by theme (e.g., reasoning, multimodal, efficiency, agents). For each cluster:
   - Theme name
   - Papers in cluster (title, arxiv URL)
   - What this research direction is about
   - Why it matters

2. **Breakthrough Papers**: Top 3-5 most significant papers with:
   - Title and arxiv URL
   - TL;DR (2-3 sentences)
   - Why notable for the field
   - Practical impact for practitioners

3. **Research Directions**: Which areas are emerging vs maturing vs declining based on paper volume and novelty?

4. **Cross-References**: Any papers that are also being discussed on Reddit or HN?

Return as structured analysis with clear sections.
">
```

#### Agent 3: Industry Explorer
```
<Task subagent_type="Explore" prompt="
You are analyzing AI industry news from TechCrunch and AI News for a news digest.

INPUT DATA:
TechCrunch: {paste TechCrunch JSON here}
AI News: {paste AI News JSON here}

ANALYZE AND RETURN:
1. **Funding & Acquisitions**: Any funding rounds, M&A, or investment news. For each:
   - Company and amount
   - What it signals about the market
   - Strategic implications

2. **Product Launches**: Notable AI products or features announced. For each:
   - Product name and company
   - What it does
   - Significance and competitive positioning

3. **Enterprise Adoption**: Companies adopting AI, partnerships, deployments
   - Who is adopting what
   - Scale and impact

4. **Policy & Regulation**: Any regulatory news, government actions, policy developments
   - What happened
   - Impact on industry

5. **Market Trends**: What patterns emerge from this week's industry news?

Return as structured analysis.
">
```

#### Agent 4: Expert Explorer
```
<Task subagent_type="Explore" prompt="
You are analyzing expert insights from The Batch (Andrew Ng) and Simon Willison's blog for a news digest.

INPUT DATA:
The Batch: {paste The Batch JSON here}
Simon Willison: {paste Simon Willison JSON here}
smol.ai: {paste smol.ai JSON here}

ANALYZE AND RETURN:
1. **Expert Opinions**: Key opinions and predictions from experts. For each:
   - Source and author
   - The opinion or prediction
   - Topic it relates to

2. **Warnings & Concerns**: Any risks, concerns, or cautions raised by experts

3. **Recommended Actions**: Actionable advice from expert sources

4. **Practitioner Insights** (from Simon Willison):
   - Key posts on prompting, agents, MCP, vibe coding
   - What practitioners should know
   - Tools or techniques highlighted

5. **Context Engineering Patterns**: Any insights about prompt engineering, context management, or AI-assisted development workflows

Return as structured analysis.
">
```

### Phase 4: Consolidation (3 Subagents)

After exploration agents complete, spawn **3 consolidation subagents in parallel**. Each synthesizes across all exploration outputs.

**IMPORTANT:** Pass ALL 4 exploration outputs to each consolidation agent.

#### Agent A: Story Synthesizer
```
<Task subagent_type="Explore" prompt="
You are synthesizing the TOP STORIES from multiple source analyses.

EXPLORATION OUTPUTS:
Community Explorer: {paste output}
Research Explorer: {paste output}
Industry Explorer: {paste output}
Expert Explorer: {paste output}

SYNTHESIZE AND RETURN:
Identify the **top 3-5 stories** of the period. A top story should:
- Appear across multiple sources OR have exceptional engagement
- Have significant implications for the AI field
- Be something readers need to know about

For EACH top story, provide:
1. **Title**: Clear, descriptive headline
2. **Sources**: Which sources covered this (Reddit, TechCrunch, The Batch, etc.)
3. **Why It Matters**: 2-3 sentences on significance
4. **Expert Take**: What do experts say? (from The Batch, Simon Willison)
5. **Community Reaction**: What does Reddit/HN think? Sentiment, debates
6. **Primary Link**: Best URL to learn more

Rank stories by importance. Be selective - only truly significant stories.
">
```

#### Agent B: Trend Synthesizer
```
<Task subagent_type="Explore" prompt="
You are identifying MAJOR TRENDS from multiple source analyses.

EXPLORATION OUTPUTS:
Community Explorer: {paste output}
Research Explorer: {paste output}
Industry Explorer: {paste output}
Expert Explorer: {paste output}

SYNTHESIZE AND RETURN:
Identify **3 major trends** this period. A trend should:
- Span multiple stories or sources
- Represent a meaningful shift or pattern
- Have implications beyond individual news items

For EACH trend, provide:
1. **Trend Name**: Clear, specific name (not generic like "AI advances")
2. **What's Happening**: Detailed explanation (3-4 sentences)
3. **Narrative Arc**: Is this emerging, maturing, or declining?
4. **Key Evidence**: 3-5 specific items (papers, posts, articles) that support this trend
5. **Expert Analysis**: What do experts say about this trend?
6. **Community Sentiment**: How does the community feel? Hot takes, concerns
7. **What This Means**: Implications for practitioners, businesses, researchers
8. **What to Watch**: Future developments to monitor

Each trend should feel distinct - avoid overlap.
">
```

#### Agent C: Implications Synthesizer
```
<Task subagent_type="Explore" prompt="
You are synthesizing ACTIONABLE IMPLICATIONS from multiple source analyses.

EXPLORATION OUTPUTS:
Community Explorer: {paste output}
Research Explorer: {paste output}
Industry Explorer: {paste output}
Expert Explorer: {paste output}

SYNTHESIZE AND RETURN:

### For Practitioners & Engineers
- **Opportunities**: What new capabilities or tools should they explore?
- **Challenges**: What problems or risks should they be aware of?
- **Skills to Develop**: Based on trends, what should they learn?
- **One Thing to Try This Week**: Single concrete, actionable recommendation

### For Business Leaders
- **Strategic Implications**: How do these developments affect strategy?
- **Investment Signals**: What areas are heating up or cooling down?
- **Competitive Dynamics**: How is the landscape shifting?
- **Risk Assessment**: What should they be cautious about?

### For Researchers
- **Research Directions**: What areas need more work?
- **Papers to Read**: Most important papers from this period
- **Gaps & Opportunities**: Where is the field underserving?
- **Collaboration Opportunities**: What interdisciplinary work is emerging?

### The Bigger Picture
- **Where We Are Now**: Current state of AI based on this period's evidence
- **Historical Context**: How does this compare to 6 months ago?
- **Where This Is Heading**: Grounded predictions for coming months
- **Signals vs Noise**: What's real progress vs hype?
">
```

### Phase 5: Report Generation

Using the **consolidation outputs** from Phase 4, generate the final report. The structured insights from Story Synthesizer, Trend Synthesizer, and Implications Synthesizer provide the foundation - weave them into a cohesive narrative.

**Key principle:** Don't repeat analysis - the subagents have done the deep work. Your job is to:
1. Assemble the structured insights into the report template
2. Add transitions and narrative flow
3. Include links from original fetched items
4. Ensure consistent voice and avoid repetition across sections

Generate a **comprehensive, detailed report** with these sections:

```markdown
# AI News Report: [Start Date] to [End Date]

## Executive Summary
[3-4 paragraphs providing a narrative overview of the most important developments.
Start with the single biggest story, then cover 2-3 other major themes.
End with a forward-looking statement about what to watch.]

---

## Top Stories This Period

### 1. [Most Important Story Title]
**Sources:** [list sources covering this]
**Why It Matters:** [2-3 sentences on significance]
**Expert Take:** [Quote or paraphrase from The Batch if available]
**Community Reaction:** [Sentiment from Reddit/HN if available]
[Link to primary source]

### 2. [Second Most Important Story]
[Same structure...]

### 3. [Third Most Important Story]
[Same structure...]

---

## Trend Deep Dives

### Trend 1: [Trend Name]
**What's Happening:** [Detailed explanation of the trend]
**Key Evidence:**
- [Paper/Article 1 with link]
- [Paper/Article 2 with link]
- [Paper/Article 3 with link]

**Expert Analysis:** [What experts are saying - from The Batch, etc.]

**Community Sentiment:** [What Reddit/HN thinks]
- Hot takes: [Notable comments or discussions]
- Concerns raised: [Any skepticism or criticism]

**What This Means:** [Implications for practitioners, businesses, researchers]

**What to Watch:** [Future developments to monitor]

### Trend 2: [Trend Name]
[Same detailed structure...]

### Trend 3: [Trend Name]
[Same detailed structure...]

---

## Connecting the Dots

### Cross-Trend Analysis
[How do the different trends relate to each other? What's the meta-narrative
emerging from this week's developments? Connect research advances to industry
moves to community sentiment. Identify patterns that span multiple stories.
Write 2-3 substantive paragraphs synthesizing the week.]

### Signals vs Noise
[What's genuine progress vs hype this week? Be direct about overhyped stories
and call out underappreciated developments. What should readers pay attention
to vs ignore?]

---

## Research Highlights

### Papers of the Week
[For each top paper from HuggingFace:]

#### [Paper Title]
- **Arxiv:** [https://arxiv.org/abs/PAPER_ID]
- **HuggingFace Discussion:** [https://huggingface.co/papers/PAPER_ID]
- **TL;DR:** [2-3 sentence summary explaining the core contribution]
- **Why Notable:** [What makes this significant for the field]
- **Practical Impact:** [How could this affect practitioners?]

[Repeat for top 5-10 papers]

### Research Themes Analysis
[2-3 paragraphs grouping papers by theme. Explain what the research community
is focused on this week and why. Connect to broader research trajectories.
Identify gaps and opportunities.]

---

## Industry & Business News

### Funding & Acquisitions
[List with brief analysis of what it signals]

### Product Launches
[Notable AI product launches with impact assessment]

### Enterprise Adoption
[Companies adopting AI, partnerships, deployments]

### Policy & Regulation
[Any regulatory news or policy developments]

---

## Community Pulse

### Hot Topics on Reddit
**Top Discussions:**
1. [Title] - [score] points, [comments] comments
   - Key debate: [what people are arguing about]
2. [Title] - [score] points, [comments] comments
   - Key insight: [notable comment or consensus]

**Community Sentiment:**
- Overall mood: [optimistic/skeptical/mixed]
- Hot topics: [list from sentiment analysis]
- Emerging interests: [what's gaining traction]

### Hacker News Highlights
[Notable AI discussions with key points]

---

## Expert Corner: The Batch by Andrew Ng

### This Week's Key Insights
[Summarize main points from The Batch articles]

### Andrew Ng's Take
[Direct quotes or paraphrased expert opinion]

### Recommended Actions
[Any actionable advice from expert sources]

---

## Context Engineering & Vibe Coding

### Practitioner Insights (Simon Willison)
[Key posts from simonwillison.net on prompting, agents, MCP, vibe coding]
- [Post Title](url) - Summary of key insight
- What practitioners should know

### Prompt Engineering Techniques (Reddit)
**Hot discussions from r/PromptEngineering, r/ChatGPTPromptGenius, r/PromptDesign:**
- [Title] - score, subreddit
- Key technique or pattern shared
- Community consensus on what works

### Tools & Workflows
[Notable tools, frameworks, or workflow patterns mentioned across sources]
- New MCP servers or integrations
- Cursor/Aider/Claude Code tips
- Context management strategies

---

## The Bigger Picture

### Where We Are Now
[Current state of the AI field based on this week's evidence. What phase are
we in? What's working, what's not? Ground this in specific examples from the news.]

### Historical Context
[How does this week compare to 6 months ago? 1 year ago? What trajectory are we on?
Reference specific past developments to show progression or regression.]

### Where This Is Heading
[Based on this week's signals, where is the field going? What should we expect
in the coming months? Make specific, grounded predictions based on evidence.]

---

## What This All Means

### For Practitioners & Engineers
[2-3 paragraphs covering: What skills to develop based on this week's trends.
What tools to try or adopt. What patterns are emerging in how work gets done.
Be specific and actionable.]

**One thing to try this week:** [Single concrete recommendation]

### For Business Leaders
[2-3 paragraphs covering: Strategic implications of this week's developments.
Investment signals and competitive dynamics. What decisions should be influenced
by this news. Risk and opportunity assessment.]

### For Researchers
[2-3 paragraphs covering: Research directions worth pursuing based on gaps
identified. What papers to read. What problems to tackle. Collaboration
opportunities. Where the field needs more work.]

---

## Full Item List

### By Date (Most Recent First)
[Complete chronological list with:
- Date
- Title (linked)
- Source
- Brief description if available]

---

## Report Metadata
- **Date Range:** [Start] to [End]
- **Total Items Analyzed:** [count]
- **Sources Consulted:** [list of 7 sources]
- **Generated:** [timestamp]
```

### Phase 5.1: Persist Report

After generating the report markdown, save it to disk:

```bash
cat <<'EOF' | uv run python .claude/skills/ai-news/scripts/write_report.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --days N \
  --sources-ok source1,source2 \
  --sources-failed source3 \
  --total-items COUNT
<REPORT MARKDOWN HERE>
EOF
```

The script will:
- Write the report to `reports/ai-news_START_to_END_TIMESTAMP.md`
- Update `reports/manifest.jsonl`
- Copy to `reports/latest.md`
- Return JSON with filepath and metadata

Verify the JSON response includes `filepath` (and other expected fields) after the command runs.

**Important:** Always run this after displaying the report to the user.

### Phase 5.2: Render HTML

After saving the markdown, generate a self-contained HTML version alongside it:

```bash
uv run python .claude/skills/ai-news/scripts/render_html.py /path/to/report.md
```

The script writes `/path/to/report.html` (same basename) and prints the HTML filepath to stdout. Use the
`filepath` returned from Phase 5.1 as the input path.

### Phase 5.3: Upload to Cloudflare Archive

Upload the HTML report to the Cloudflare archive. The `.env` file contains the required `ADMIN_API_SECRET`:

```bash
source .env && uv run python .claude/skills/ai-news/scripts/upload_to_cloudflare.py \
  /path/to/report.html \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --days N \
  --total-items COUNT
```

The script uploads the HTML to Cloudflare R2 and updates the KV index. The report will be immediately available at:
- Archive listing: https://julienh15.github.io/AI-News-Reports/archive/
- Direct link: https://ai-news-signup.julienh15.workers.dev/archive/{report_id}

### Phase 5.4: Send Newsletter

Send the report to all subscribers via email:

```bash
source .env && uv run python .claude/skills/ai-news/scripts/send_newsletter.py \
  --verbose \
  --api-url "https://ai-news-signup.julienh15.workers.dev/api/subscribers" \
  --api-secret "$ADMIN_API_SECRET"
```

The script will:
- Fetch active subscribers from the Cloudflare Worker API
- Send personalized emails with unsubscribe links via Microsoft Graph
- Log sent emails to avoid duplicates

**Options:**
- `--dry-run` - Preview without sending
- `--test-email user@example.com` - Send only to a test address
- `--force` - Ignore sent log and resend to all

## Scripts Reference

All scripts are in `.claude/skills/ai-news/scripts/` directory:

| Script | Source | API/Method | Special Features |
|--------|--------|------------|------------------|
| `fetch_smol_news.py` | smol.ai | RSS feed | Curated summaries |
| `fetch_hf_papers.py` | HuggingFace | Date-based URL | Upvote counts |
| `fetch_hn_ai.py` | Hacker News | Algolia API | AI keyword filtering |
| `fetch_ai_news.py` | AI News | HTML scraping | Enterprise focus |
| `fetch_techcrunch.py` | TechCrunch | RSS feed | Startup/funding focus |
| `fetch_the_batch.py` | The Batch | HTML parsing | Expert analysis |
| `fetch_reddit_ml.py` | Reddit | JSON API | Sentiment analysis, 11 subreddits |
| `fetch_simonwillison.py` | Simon Willison | Atom feeds | Context engineering, 7 tag feeds |
| `render_html.py` | Markdown | python-markdown | Self-contained HTML output |
| `upload_to_cloudflare.py` | Cloudflare | Worker API | Upload to R2 + KV archive |
| `send_newsletter.py` | Email | Microsoft Graph | Send to subscribers via API |

## Error Handling

- If a source fails, continue with available sources
- Report which sources succeeded/failed in the output
- Minimum viable report requires at least 2 sources

## Quality Guidelines

### Report Length
- Executive Summary: 400-600 words
- Each Trend Deep Dive: 600-800 words
- Connecting the Dots: 400-600 words
- The Bigger Picture: 500-700 words
- What This All Means: 600-800 words (expanded paragraphs, not bullets)
- Total report: 5000-7000 words

### Analysis Depth
- Don't just list items - explain significance and connections
- Connect dots across sources - how do stories relate?
- Provide actionable insights with specific recommendations
- Include both optimistic and critical perspectives
- Ground analysis in specific evidence from the fetched items
- Compare to historical context when relevant
- Make the report valuable enough that readers share it
- Avoid repetitive phrasing - each section should feel fresh and distinct

### Writing Quality
- **Avoid repetition**: Each trend deep dive should have unique framing and language. Don't repeat the same phrases across sections.
- **Synthesize, don't summarize**: Connect ideas rather than restating them. If a story appears in multiple sections, reference it briefly rather than re-explaining.
- **Vary sentence structure**: Mix short punchy sentences with longer analytical ones. Avoid starting multiple paragraphs the same way.
- **Cut boilerplate**: Remove generic phrases like "This is significant because..." or "What's notable is...". Be direct.
- **One insight per paragraph**: Each paragraph should advance a single clear point. Don't pad with filler.

**Anti-patterns to avoid:**
- Repeating the same adjectives (breakthrough, significant, notable) across sections
- Re-explaining the same story in Top Stories, Trends, and other sections
- Using the same "What's Happening / Key Evidence / Expert Analysis" framing verbatim for every trend
- Starting multiple sections with "The" or similar patterns

### Linking
- Every claim should link to a source
- Use markdown hyperlinks consistently
- Include both discussion links and original sources

## Architecture Reference

See `references/ARCHITECTURE.md` for detailed workflow diagrams and technical specifications.
