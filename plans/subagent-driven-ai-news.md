# Plan: Subagent-Driven AI News Workflow

## Problem

Current workflow processes 400+ items in a single pass. This limits depth of analysis:
- Too many items to explore thoroughly
- Surface-level synthesis rather than deep investigation
- Repetitive phrasing as patterns get reused

## Solution: Multi-Phase Subagent Architecture

### Current Flow
```
Fetch (parallel) → Single-pass Analysis → Report
```

### New Flow
```
Fetch (parallel) → Explore (parallel subagents) → Consolidate (parallel subagents) → Report
```

---

## Phase 1: Fetch (Unchanged)
Run 8 fetchers in parallel. Returns raw JSON for each source.

---

## Phase 2: Parallel Exploration

Spawn **4 exploration subagents** in parallel. Each analyzes a subset of items.

### Agent: Community Explorer
**Input:** Reddit JSON (377+ posts)
**Task:** Deep dive into community discussions
**Output:**
```json
{
  "hot_topics": [{"topic": "...", "evidence": [...], "sentiment": "..."}],
  "major_debates": [{"title": "...", "positions": [...], "engagement": N}],
  "emerging_interests": ["..."],
  "community_mood": "optimistic|skeptical|mixed",
  "notable_posts": [{"title": "...", "url": "...", "why_notable": "..."}]
}
```

### Agent: Research Explorer
**Input:** HuggingFace papers JSON
**Task:** Analyze research trends and significant papers
**Output:**
```json
{
  "paper_clusters": [{"theme": "...", "papers": [...], "significance": "..."}],
  "breakthrough_papers": [{"title": "...", "arxiv": "...", "why": "..."}],
  "research_directions": ["emerging", "maturing", "declining"],
  "cross_references": [{"paper": "...", "also_discussed_on": ["reddit", "hn"]}]
}
```

### Agent: Industry Explorer
**Input:** TechCrunch + AI News JSON
**Task:** Analyze business/industry landscape
**Output:**
```json
{
  "funding_signals": [{"company": "...", "amount": "...", "signal": "..."}],
  "product_launches": [{"product": "...", "significance": "..."}],
  "policy_developments": [{"policy": "...", "impact": "..."}],
  "market_trends": ["..."]
}
```

### Agent: Expert Explorer
**Input:** The Batch + Simon Willison JSON
**Task:** Extract expert insights and practitioner wisdom
**Output:**
```json
{
  "expert_opinions": [{"source": "...", "opinion": "...", "topic": "..."}],
  "recommended_actions": ["..."],
  "warnings_raised": ["..."],
  "practitioner_insights": [{"insight": "...", "source": "..."}]
}
```

---

## Phase 3: Consolidation

Spawn **3 consolidation subagents** in parallel. Each synthesizes across exploration outputs.

### Agent: Story Synthesizer
**Input:** All 4 exploration outputs
**Task:** Identify top 3-5 stories with cross-source evidence
**Output:**
```json
{
  "top_stories": [
    {
      "title": "...",
      "sources": ["reddit", "techcrunch", "the_batch"],
      "why_matters": "...",
      "expert_take": "...",
      "community_reaction": "...",
      "primary_link": "..."
    }
  ]
}
```

### Agent: Trend Synthesizer
**Input:** All 4 exploration outputs
**Task:** Identify 3 major trends with evidence
**Output:**
```json
{
  "trends": [
    {
      "name": "...",
      "narrative_arc": "emerging|maturing|declining",
      "key_evidence": ["..."],
      "expert_analysis": "...",
      "community_sentiment": "...",
      "implications": "...",
      "what_to_watch": "..."
    }
  ]
}
```

### Agent: Implications Synthesizer
**Input:** All 4 exploration outputs
**Task:** Extract actionable insights for different audiences
**Output:**
```json
{
  "for_practitioners": {
    "opportunities": ["..."],
    "challenges": ["..."],
    "action_items": ["..."],
    "one_thing_to_try": "..."
  },
  "for_business_leaders": {...},
  "for_researchers": {...},
  "bigger_picture": {
    "where_we_are": "...",
    "historical_context": "...",
    "where_heading": "..."
  }
}
```

---

## Phase 4: Report Generation

Main orchestrator (Claude) writes final report using:
- Structured outputs from Phase 3
- Original items for linking
- Report template from SKILL.md

**Benefits:**
- Deeper analysis (subagents explore thoroughly)
- Less repetition (synthesizers have complete picture)
- Richer cross-source insights (consolidation phase connects dots)
- Consistent structure (template + structured inputs)

---

## Implementation Changes

### SKILL.md Updates

1. **New Phase 2: Parallel Exploration**
   - Define 4 explorer agent prompts
   - Specify input/output formats
   - Add to workflow sequence

2. **New Phase 3: Consolidation**
   - Define 3 synthesizer agent prompts
   - Specify how they receive explorer outputs
   - Add to workflow sequence

3. **Update Phase 4 (was Phase 3)**
   - Rename to Report Generation
   - Reference structured consolidation outputs

### Execution Pattern

```python
# Phase 2: Exploration (parallel Task calls)
<Task prompt="Analyze Reddit community..." subagent_type="Explore">
<Task prompt="Analyze research papers..." subagent_type="Explore">
<Task prompt="Analyze industry news..." subagent_type="Explore">
<Task prompt="Analyze expert sources..." subagent_type="Explore">

# Collect outputs, then Phase 3: Consolidation (parallel Task calls)
<Task prompt="Synthesize top stories from: {explorer_outputs}" subagent_type="Explore">
<Task prompt="Synthesize trends from: {explorer_outputs}" subagent_type="Explore">
<Task prompt="Synthesize implications from: {explorer_outputs}" subagent_type="Explore">

# Phase 4: Main Claude writes report using consolidation outputs
```

---

## Tradeoffs

| Aspect | Benefit | Cost |
|--------|---------|------|
| Depth | Much deeper item exploration | More API calls |
| Quality | Richer synthesis, less repetition | Longer execution |
| Structure | Consistent structured outputs | More complex orchestration |
| Token usage | Subagents have focused context | Total tokens may increase |

---

## Pre-Mortem: What Could Go Wrong?

| Risk | Mitigation |
|------|------------|
| Subagent outputs don't match expected format | Provide clear JSON schemas in prompts |
| Too many parallel calls | Limit to 4 explorers + 3 synthesizers |
| Context loss between phases | Pass complete structured outputs |
| Report becomes too long | Keep word count targets in final phase |
| Exploration misses important items | Explorers should flag uncertainty |

---

## Verification

After implementation:
1. Run `/ai-news 2`
2. Verify 4 exploration agents run in parallel
3. Verify 3 consolidation agents run in parallel
4. Check final report uses structured insights
5. Compare depth/quality to previous single-pass reports
