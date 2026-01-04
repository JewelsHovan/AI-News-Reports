# Plan: AI News Report Improvements

## Goal
Improve the AI news skill with:
1. Comprehensive reports as default (longer, more analysis)
2. Replace duplicate date ranges instead of creating new files
3. Properly include arxiv paper links

## Current State
- Reports are 2000-4000 words - too short
- Each run creates new timestamped file (duplicates accumulate)
- Arxiv URLs fetched but template uses HuggingFace links

---

## Task 1: Update write_report.py for Deduplication

**File:** `.claude/skills/ai-news/scripts/write_report.py`

### Changes:
1. **Remove timestamp from filename** (line 56)
   - Before: `ai-news_{start_date}_to_{end_date}_{timestamp}.md`
   - After: `ai-news_{start_date}_to_{end_date}.md`

2. **Check for existing file and delete before writing** (before line 64)
   - If file exists with same date range, delete it first
   - This naturally handles replacement

3. **Update manifest handling** (lines 86-87)
   - Read existing manifest
   - Filter out entries with matching date range
   - Write back with new entry appended

### Why This Approach:
- Simpler than glob searching for patterns
- Canonical naming = automatic replacement
- Manifest stays clean

---

## Task 2: Update SKILL.md Report Template

**File:** `.claude/skills/ai-news/SKILL.md`

### Changes to Phase 5 Report Template:

#### A. Expand Word Count Targets (line ~401)
```markdown
### Report Length
- Executive Summary: 400-600 words
- Each Trend Deep Dive: 600-800 words (EXPANDED)
- Context Engineering section: 400-600 words
- What This All Means: 600-800 words (EXPANDED)
- Total report: 5000-7000 words (WAS 2000-4000)
```

#### B. Add New Sections

**Add "Connecting the Dots" section after Trend Deep Dives:**
```markdown
## Connecting the Dots

### Cross-Trend Analysis
[How do the trends relate to each other? What's the meta-narrative?
Connect research advances to industry moves to community sentiment.
2-3 paragraphs synthesizing the week's developments.]

### Signals vs Noise
[What's genuine progress vs hype this week? Call out overhyped stories
and underappreciated developments. Be direct.]
```

**Add "The Bigger Picture" section before "What This All Means":**
```markdown
## The Bigger Picture

### Where We Are Now
[Current state of the AI field based on this week's evidence.
What phase are we in? What's working, what's not?]

### Historical Context
[How does this week compare to 6 months ago? 1 year ago?
What trajectory are we on? Reference past developments.]

### Where This Is Heading
[Based on this week's signals, where is the field going?
What should we expect in the coming months?]
```

#### C. Expand "What This All Means" Section
Change from bullet points to paragraphs:
```markdown
## What This All Means

### For Practitioners & Engineers
[2-3 paragraphs on: What skills to develop, tools to try,
patterns to adopt. Be specific and actionable.
Include "One thing to try this week" recommendation.]

### For Business Leaders
[2-3 paragraphs on: Strategic implications, investment signals,
competitive dynamics. What decisions should be influenced by this week's news?]

### For Researchers
[2-3 paragraphs on: Research directions worth pursuing,
gaps in current work, collaboration opportunities.
What papers to read, what problems to tackle.]
```

#### D. Enhance Research Highlights
```markdown
## Research Highlights

### Papers of the Week
[For each top paper from HuggingFace:]

#### [Paper Title]
- **Arxiv:** [arxiv.org link - USE ARXIV URL]
- **HuggingFace:** [HF discussion link]
- **TL;DR:** [2-3 sentence summary explaining the contribution]
- **Why Notable:** [What makes this significant for the field]
- **Practical Impact:** [How could this affect practitioners?]

### Research Themes Analysis
[2-3 paragraphs grouping papers by theme and explaining
what the research community is focused on and why]
```

---

## Task 3: Update Arxiv Link Guidance

**File:** `.claude/skills/ai-news/SKILL.md`

### Changes:
1. In Research Highlights template, explicitly use `arxiv_url` field
2. Add note in Phase 4 about preserving arxiv URLs
3. Update the paper template to show BOTH links (arxiv for paper, HF for discussion)

---

## Implementation Order

1. **write_report.py** - Deduplication (independent)
2. **SKILL.md** - Report template expansion (independent)
3. **SKILL.md** - Arxiv link guidance (can combine with #2)

## Files to Modify

| File | Changes |
|------|---------|
| `.claude/skills/ai-news/scripts/write_report.py` | Remove timestamp, add manifest cleanup |
| `.claude/skills/ai-news/SKILL.md` | Expand template, add sections, update word counts |

## Verification

After implementation:
1. Run `/ai-news 2` twice - second run should replace first report
2. Check reports/ folder has no duplicates for same date range
3. Verify manifest.jsonl has single entry per date range
4. Confirm report is longer with new sections
5. Confirm arxiv links appear in Research section

---

## Pre-Mortem: What Could Go Wrong?

| Risk | Mitigation |
|------|------------|
| Old manifest format breaks | Keep backward-compatible JSONL format |
| Report too long for context | Keep sections modular, can trim if needed |
| Arxiv links break | Keep HuggingFace as fallback |
| Existing reports get deleted accidentally | Only delete matching date ranges |
