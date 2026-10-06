"""Tests for ai_news.publishing.listing."""
from ai_news.publishing.listing import extract_issue_title, extract_listing, strip_issue_title

REPORT = """# AI News Report: 2026-09-29 to 2026-10-01

## Executive Summary

Agents now succeed 35% of the time on long tasks, OpenAI said at [DevDay](https://example.com). The admission arrived with **live demo failures** and research on "co-cheating." Meanwhile, ElevenLabs raised at a $22B valuation.

**Key Takeaways:**
- **Agent reliability gap**: deployments hit friction

---

## Top Stories This Period

### 1. OpenAI DevDay Reveals Agent Reliability Crisis
**Bottom Line:** Agents improved.

### 2. ElevenLabs Doubles to $22B as Voice AI Commands Premium Valuations

### 3. On-Policy Self-Distillation Emerges as Dominant Research Paradigm

### 4. Google and OpenAI Launch Competing Model Tiers

### 5. Reddit Closes Public API

### 6. Should Be Ignored

## Trend Deep Dives

### 1. Not A Top Story
"""


def test_top_stories_and_headline():
    listing = extract_listing(REPORT)
    assert listing.headline == "OpenAI DevDay Reveals Agent Reliability Crisis"
    assert len(listing.top_stories) == 5
    assert "Not A Top Story" not in listing.top_stories
    assert "Should Be Ignored" not in listing.top_stories


def test_tldr_strips_markdown_and_keeps_whole_sentences():
    listing = extract_listing(REPORT)
    assert listing.tldr.startswith("Agents now succeed 35% of the time on long tasks, OpenAI said at DevDay.")
    assert "**" not in listing.tldr and "](" not in listing.tldr
    assert "Key Takeaways" not in listing.tldr
    # Short sentences are combined until the target length; a sentence ending
    # inside a closing quote still counts as a sentence break.
    assert 'research on "co-cheating." Meanwhile' in listing.tldr
    assert listing.tldr.endswith("$22B valuation.")


def test_tags_from_headlines():
    listing = extract_listing(REPORT)
    assert set(listing.tags) == {"Agents", "Funding", "Products"}
    assert len(listing.tags) <= 3


def test_tag_matching_respects_word_boundaries():
    report = REPORT.replace("ElevenLabs Doubles to $22B as Voice AI Commands Premium Valuations", "Neural Euphoria")
    listing = extract_listing(report)
    # "eu" inside "Neural"/"Euphoria" must not trigger Policy.
    assert "Policy" not in listing.tags


def test_long_single_sentence_is_capped():
    long = "word " * 120
    listing = extract_listing(f"## Executive Summary\n\n{long}.\n")
    assert len(listing.tldr) <= 340
    assert listing.tldr.endswith("…")


def test_missing_sections_yield_empty_listing():
    listing = extract_listing("# Some other document\n\nNo structure here.\n")
    assert listing.headline is None
    assert listing.tldr is None
    assert listing.top_stories == []
    assert listing.tags == []
    assert listing.issue_title is None
    assert listing.to_dict() == {"issue_title": None, "headline": None, "tldr": None, "top_stories": [], "tags": []}


def test_issue_title_extracted_and_cleaned():
    md = REPORT.replace(
        "# AI News Report: 2026-09-29 to 2026-10-01\n",
        "# AI News Report: 2026-09-29 to 2026-10-01\n**Issue title:** \"Le Chonk, the **agent budget trap** and a $40B chip bet.\"\n",
    )
    assert extract_listing(md).issue_title == "Le Chonk, the agent budget trap and a $40B chip bet"


def test_unfilled_issue_title_placeholder_is_ignored():
    md = "# AI News Report: x\n**Issue title:** [4-9 word editorial title; see ISSUE TITLE RULES]\n"
    assert extract_issue_title(md) is None


def test_strip_issue_title_removes_only_that_line():
    md = "# AI News Report: x\n**Issue title:** Big week\n\n## Executive Summary\n\nText.\n"
    stripped = strip_issue_title(md)
    assert "Issue title" not in stripped
    assert stripped.startswith("# AI News Report: x\n\n## Executive Summary")
