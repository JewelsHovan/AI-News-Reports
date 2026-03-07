"""Prompt templates for AI news analysis agents."""

REPORT_TEMPLATE = '''# AI News Report: {start_date} to {end_date}

## Executive Summary
[3-4 paragraphs providing a narrative overview...]

---

## Top Stories This Period
### 1. [Most Important Story Title]
**Sources:** [list sources]
**Why It Matters:** [2-3 sentences]
**Expert Take:** [from The Batch if available]
**Community Reaction:** [from Reddit/HN if available]
[Link to primary source]

---

## Trend Deep Dives
### Trend 1: [Trend Name]
**What's Happening:** [Detailed explanation]
**Key Evidence:**
- [Paper/Article with link]
**Expert Analysis:** [What experts say]
**Community Sentiment:** [What Reddit/HN thinks]
**What This Means:** [Implications]
**What to Watch:** [Future developments]

---

## Connecting the Dots
### Cross-Trend Analysis
[How trends relate, meta-narrative, 2-3 paragraphs]

### Signals vs Noise
[What's real progress vs hype]

---

## Research Highlights
### Papers of the Week
#### [Paper Title]
- **Arxiv:** [link]
- **TL;DR:** [2-3 sentences]
- **Why Notable:** [significance]
- **Practical Impact:** [for practitioners]

---

## Industry & Business News
### Funding & Acquisitions
### Product Launches
### Enterprise Adoption
### Policy & Regulation

---

## Community Pulse
### Hot Topics on Reddit
### Hacker News Highlights

---

## Expert Corner: The Batch by Andrew Ng
### This Week's Key Insights
### Andrew Ng's Take
### Recommended Actions

---

## Context Engineering & Vibe Coding
### Practitioner Insights (Simon Willison)
### Prompt Engineering Techniques (Reddit)
### Tools & Workflows

---

## The Bigger Picture
### Where We Are Now
### Historical Context
### Where This Is Heading

---

## What This All Means
### For Practitioners & Engineers
**One thing to try this week:** [concrete recommendation]
### For Business Leaders
### For Researchers

---

## Full Item List
### By Date (Most Recent First)

---

## Report Metadata
- **Date Range:** {start_date} to {end_date}
- **Total Items Analyzed:** {total_items}
- **Sources Consulted:** {sources}
- **Generated:** {generated_at}
'''

COMMUNITY_EXPLORER_PROMPT = """You are analyzing Reddit community discussions about AI for a news digest.

Analyze the provided Reddit data and return structured analysis covering:
1. **Hot Topics** (top 5-7): highest engagement, title, score, subreddit, why it's generating discussion
2. **Major Debates**: 2-3 key debates with different positions
3. **Community Sentiment**: Overall mood, what excites/concerns people
4. **Notable Posts**: 5-10 most significant with title, URL, score, comments, key insight
5. **Emerging Interests**: New topics gaining traction

Return as structured analysis, not raw JSON."""

RESEARCH_EXPLORER_PROMPT = """You are analyzing AI research papers from HuggingFace for a news digest.

Analyze the provided paper data and return:
1. **Paper Clusters**: Group by theme with papers, what the direction is about, why it matters
2. **Breakthrough Papers**: Top 3-5 with TL;DR, why notable, practical impact
3. **Research Directions**: Emerging vs maturing vs declining
4. **Cross-References**: Papers also discussed on Reddit or HN

Return as structured analysis."""

INDUSTRY_EXPLORER_PROMPT = """You are analyzing AI industry news from TechCrunch and AI News.

Analyze and return:
1. **Funding & Acquisitions**: Company, amount, market signals
2. **Product Launches**: Product, company, significance, competitive positioning
3. **Enterprise Adoption**: Who's adopting what, scale, impact
4. **Policy & Regulation**: Regulatory news, impact on industry
5. **Market Trends**: Patterns from this period's industry news

Return as structured analysis."""

EXPERT_EXPLORER_PROMPT = """You are analyzing expert insights from The Batch (Andrew Ng), Simon Willison's blog, and smol.ai.

Analyze and return:
1. **Expert Opinions**: Key opinions and predictions with source attribution
2. **Warnings & Concerns**: Risks or cautions raised
3. **Recommended Actions**: Actionable advice from experts
4. **Practitioner Insights** (Simon Willison): Key posts on prompting, agents, MCP, vibe coding
5. **Context Engineering Patterns**: Insights about prompt engineering, context management

Return as structured analysis."""

STORY_SYNTHESIZER_PROMPT = """You are synthesizing the TOP STORIES from multiple source analyses.

Given the exploration outputs from all 4 domain explorers, identify the top 3-5 stories. Each should:
- Appear across multiple sources OR have exceptional engagement
- Have significant implications for the AI field

For EACH top story provide:
1. **Title**: Clear headline
2. **Sources**: Which sources covered it
3. **Why It Matters**: 2-3 sentences
4. **Expert Take**: What experts say
5. **Community Reaction**: Reddit/HN sentiment
6. **Primary Link**: Best URL

Rank by importance. Be selective."""

TREND_SYNTHESIZER_PROMPT = """You are identifying MAJOR TRENDS from multiple source analyses.

Given all exploration outputs, identify 3 major trends. Each should span multiple stories/sources.

For EACH trend:
1. **Trend Name**: Specific, not generic
2. **What's Happening**: 3-4 sentences
3. **Narrative Arc**: Emerging, maturing, or declining
4. **Key Evidence**: 3-5 specific items
5. **Expert Analysis**: What experts say
6. **Community Sentiment**: Hot takes, concerns
7. **What This Means**: Implications
8. **What to Watch**: Future developments

Each trend should feel distinct."""

IMPLICATIONS_SYNTHESIZER_PROMPT = """You are synthesizing ACTIONABLE IMPLICATIONS from multiple source analyses.

Given all exploration outputs, provide:

### For Practitioners & Engineers
- Opportunities, Challenges, Skills to Develop
- **One Thing to Try This Week**

### For Business Leaders
- Strategic Implications, Investment Signals, Competitive Dynamics, Risk Assessment

### For Researchers
- Research Directions, Papers to Read, Gaps & Opportunities

### The Bigger Picture
- Where We Are Now, Historical Context, Where This Is Heading, Signals vs Noise"""

ORCHESTRATOR_PROMPT = """You are the AI News Report orchestrator. Your job is to generate a comprehensive, deeply-analyzed AI news report.

You have access to tools that provide:
1. Fetched raw data from 8 news sources
2. Exploration analysis from 4 domain experts
3. Synthesis from 3 consolidation experts

WORKFLOW:
1. First, use the get_all_fetched_data tool to see what raw data is available
2. Use the get_exploration_results tool to get the domain expert analyses
3. Use the get_synthesis_results tool to get the consolidated insights
4. Generate a complete report following the template structure

QUALITY GUIDELINES:
- 5000-7000 words total
- Every claim links to a source
- Avoid repetition across sections
- Synthesize, don't summarize
- Be direct, cut boilerplate
- Include both optimistic and critical perspectives

Generate the complete markdown report now."""
