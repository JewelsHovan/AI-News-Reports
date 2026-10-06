"""Extract archive-listing metadata (headline, TL;DR, top stories, tags) from a report.

The archive page shows each issue as a card. Rather than spend another model
call, this parses the structure the report generator already emits:
"## Executive Summary" for the TL;DR, "### N. Title" under "## Top Stories"
for the headlines, and keyword matching over those for topic tags.
"""

import re
from dataclasses import asdict, dataclass, field

MAX_TOP_STORIES = 5
MAX_TAGS = 3
TLDR_TARGET_CHARS = 220
TLDR_MAX_CHARS = 340

# Tag -> regex alternatives, matched case-insensitively on word boundaries.
TAG_KEYWORDS: dict[str, list[str]] = {
    "Agents": [r"agents?", r"agentic", r"multi-agent", r"autonomous", r"computer[- ]use", r"tool[- ]use"],
    "Safety": [
        r"safety", r"alignment", r"deceiv\w*", r"deception", r"jailbreak\w*", r"misuse",
        r"rogue", r"oversight", r"collu\w+", r"cheat\w*", r"hack\w*", r"security",
        r"red[- ]team\w*", r"risks?",
    ],
    "Research": [
        r"papers?", r"research\w*", r"benchmarks?", r"distillation", r"reasoning",
        r"architectures?", r"study", r"breakthrough", r"paradigm",
    ],
    "Infra": [
        r"gpus?", r"nvidia", r"compute", r"chips?", r"inference", r"data ?cent(?:er|re)s?",
        r"quantization", r"kv cache", r"energy", r"infrastructure", r"serving", r"hardware",
    ],
    "Funding": [
        r"rais\w+", r"funding", r"valuations?", r"\$\d[\d.,]*\s?[bm]\b", r"billion",
        r"acqui\w+", r"ipo", r"investors?", r"mega-round", r"round",
    ],
    "Policy": [
        r"policy", r"regulat\w+", r"laws?", r"copyright", r"government", r"congress",
        r"eu", r"courts?", r"lawsuits?", r"ban\w*", r"senate", r"white house",
    ],
    "Robotics": [r"robot\w*", r"humanoids?", r"embodied"],
    "Open models": [r"open[- ]source", r"open[- ]weights?", r"llama", r"qwen", r"deepseek", r"mistral"],
    "Products": [r"launch\w*", r"releas\w+", r"devday", r"chatgpt", r"apps?", r"products?"],
}

_TAG_PATTERNS = {
    tag: re.compile(r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])", re.IGNORECASE)
    for tag, alts in TAG_KEYWORDS.items()
}

# Sentence break after . ! or ? (optionally followed by a closing quote).
_SENTENCE_END = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"”’']))\s+(?=[A-Z\"“'(])")
_STORY_HEADING = re.compile(r"^###\s+(?:Story\s+)?\d+[.:)]\s*(.+?)\s*$")
_ISSUE_TITLE_LINE = re.compile(r"^\*\*Issue title:\*\*[ \t]*(.*?)[ \t]*$\n?", re.IGNORECASE | re.MULTILINE)
MAX_ISSUE_TITLE_CHARS = 120


@dataclass
class ReportListing:
    issue_title: str | None = None
    headline: str | None = None
    tldr: str | None = None
    top_stories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _clean_inline(text: str) -> str:
    """Strip inline markdown (links, emphasis, code) down to plain text."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\*\*|__|\*|`)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_issue_title(markdown: str) -> str | None:
    """Return the editorial title from the '**Issue title:**' line, if any."""
    match = _ISSUE_TITLE_LINE.search(markdown)
    if not match:
        return None
    title = _clean_inline(match.group(1)).strip("\"'“”‘’ ").rstrip(".")
    if not title or title.startswith("["):  # empty or unfilled template placeholder
        return None
    return title[:MAX_ISSUE_TITLE_CHARS]


def strip_issue_title(markdown: str) -> str:
    """Remove the '**Issue title:**' line so it doesn't render in the body."""
    return _ISSUE_TITLE_LINE.sub("", markdown, count=1)


def _section(lines: list[str], heading_prefix: str) -> list[str]:
    """Return the lines under the first '## ' heading starting with heading_prefix."""
    start = None
    for i, line in enumerate(lines):
        if start is None:
            if line.startswith("## ") and line[3:].strip().lower().startswith(heading_prefix.lower()):
                start = i + 1
        elif line.startswith("## "):
            return lines[start:i]
    return lines[start:] if start is not None else []


def _first_paragraph(lines: list[str]) -> str | None:
    para: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("#"):
            if para:
                break
            continue
        if stripped.startswith(("- ", "* ", "**Key Takeaways")):
            if para:
                break
            continue
        para.append(stripped)
    return _clean_inline(" ".join(para)) if para else None


def _shorten(paragraph: str) -> str:
    """Keep whole sentences up to roughly TLDR_TARGET_CHARS, hard-capped at TLDR_MAX_CHARS."""
    out = ""
    for sentence in _SENTENCE_END.split(paragraph):
        candidate = f"{out} {sentence}".strip()
        if out and len(candidate) > TLDR_MAX_CHARS:
            break
        out = candidate
        if len(out) >= TLDR_TARGET_CHARS:
            break
    if len(out) > TLDR_MAX_CHARS:
        out = out[: TLDR_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return out


def _top_stories(lines: list[str]) -> list[str]:
    stories = []
    for line in _section(lines, "Top Stories"):
        match = _STORY_HEADING.match(line)
        if match:
            stories.append(_clean_inline(match.group(1)))
            if len(stories) == MAX_TOP_STORIES:
                break
    return stories


def _tags(stories: list[str], tldr: str | None) -> list[str]:
    """Score tags: headline hits count double, TL;DR hits once; keep tags scoring >= 2."""
    scores: dict[str, int] = {}
    for tag, pattern in _TAG_PATTERNS.items():
        score = sum(2 for s in stories if pattern.search(s))
        if tldr:
            score += min(len(pattern.findall(tldr)), 2)
        if score >= 2:
            scores[tag] = score
    order = list(TAG_KEYWORDS)
    ranked = sorted(scores, key=lambda t: (-scores[t], order.index(t)))
    return ranked[:MAX_TAGS]


def extract_listing(markdown: str) -> ReportListing:
    """Build the archive listing for a report. Missing sections yield empty fields."""
    lines = markdown.splitlines()
    summary = _first_paragraph(_section(lines, "Executive Summary"))
    tldr = _shorten(summary) if summary else None
    stories = _top_stories(lines)
    return ReportListing(
        issue_title=extract_issue_title(markdown),
        headline=stories[0] if stories else None,
        tldr=tldr,
        top_stories=stories,
        tags=_tags(stories, tldr),
    )
