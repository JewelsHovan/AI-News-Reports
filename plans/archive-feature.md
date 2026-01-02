# Archive Feature Implementation Plan

## Overview

Add a publicly accessible archive of past AI News reports to GitHub Pages, with human-friendly date formatting (e.g., `dec_2nd_2025`) and automated publishing via GitHub Actions.

## Requirements

1. **All reports archived** - No rolling window
2. **URL structure by date range** - e.g., `dec_2nd_2025_to_dec_4th_2025.html`
3. **GitHub Action for auto-publish** - Commit and push archive updates automatically
4. **New date format** - `dec_2nd_2025` instead of `YYYY-MM-DD` for titles and filenames

---

## Implementation Tasks

### Task 1: Add Date Formatting Utility

**File:** `.claude/skills/ai-news/scripts/date_utils.py` (new)

Create a utility module for the new date format:

```python
def format_date_human(date_str: str) -> str:
    """
    Convert YYYY-MM-DD to human format like 'dec_2nd_2025'.

    Examples:
        2025-12-02 -> dec_2nd_2025
        2025-01-01 -> jan_1st_2025
        2025-03-23 -> mar_23rd_2025
    """
```

Ordinal suffix rules:
- 1, 21, 31 → "st"
- 2, 22 → "nd"
- 3, 23 → "rd"
- Everything else → "th"

---

### Task 2: Update `render_html.py` for Web Mode

**File:** `.claude/skills/ai-news/scripts/render_html.py`

Changes:
1. Add `--mode` argument: `email` (default) or `web`
2. In `web` mode:
   - Remove `UNSUBSCRIBE_FOOTER` from template
   - Use human-readable date format in header
3. Add `--archive-output` argument for web archive path
4. Update `_infer_date_range_from_name()` to also parse new format

**New function:**
```python
def format_date_range_human(start: str, end: str) -> str:
    """Convert date range to 'Dec 2nd, 2025 → Dec 4th, 2025' for display."""
```

---

### Task 3: Update `write_report.py` for Archive

**File:** `.claude/skills/ai-news/scripts/write_report.py`

Changes:
1. Import date formatting utility
2. Add `--archive-dir` argument (default: `docs/archive`)
3. After writing report:
   - Generate web-safe HTML using `render_html.py --mode web`
   - Copy to archive dir with human-formatted filename
4. Update manifest to include archive path

---

### Task 4: Create Archive Index Generator

**File:** `.claude/skills/ai-news/scripts/generate_archive_index.py` (new)

Purpose: Read `manifest.jsonl` and generate `docs/archive/index.html`

Features:
- List all reports in reverse chronological order
- Display date range in human format
- Link to individual report HTML files
- Match signup page styling for consistency
- Include navigation back to signup page

Template structure:
```html
<h1>AI News Archive</h1>
<ul>
  <li><a href="dec_2nd_2025_to_dec_4th_2025.html">Dec 2nd, 2025 → Dec 4th, 2025</a></li>
  ...
</ul>
```

---

### Task 5: Update `.gitignore` Files

**File:** `reports/.gitignore`

Change from:
```gitignore
*.md
*.html
manifest.jsonl
```

To:
```gitignore
*.md
*.html
# Keep manifest for archive index generation
!manifest.jsonl
!README.md
!.gitkeep
!.gitignore
```

Note: We keep HTML gitignored in `reports/` since the archive copies go to `docs/archive/`.

---

### Task 6: Create Archive Directory Structure

```
docs/
├── index.html              # Signup page (existing)
├── styles.css              # Existing
├── archive/
│   ├── index.html          # Generated archive list
│   ├── styles.css          # Archive-specific styles (optional)
│   └── *.html              # Individual report files
```

---

### Task 7: Add Navigation Links

**File:** `docs/index.html`

Add link to archive in signup page footer:
```html
<a href="archive/">View Past Reports</a>
```

**File:** `docs/archive/index.html` (generated)

Add link back to signup:
```html
<a href="../">Subscribe to Newsletter</a>
```

---

### Task 8: Create GitHub Action

**File:** `.github/workflows/publish-archive.yml` (new)

Trigger: Push to `main` branch when `reports/manifest.jsonl` changes

Steps:
1. Checkout repository
2. Setup Python with uv
3. Install dependencies
4. Run `generate_archive_index.py`
5. Commit and push changes to `docs/archive/`

```yaml
name: Publish Archive

on:
  push:
    branches: [main]
    paths:
      - 'reports/manifest.jsonl'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv pip install markdown

      - name: Generate archive
        run: uv run python .claude/skills/ai-news/scripts/generate_archive_index.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/archive/
          git diff --staged --quiet || git commit -m "Update archive index"
          git push
```

---

### Task 9: Update Pipeline Integration

**File:** `.claude/skills/ai-news/SKILL.md`

Add new phase after HTML rendering:
- **Phase 5.3 - Archive Update**: Generate web HTML and update archive index

---

### Task 10: Migrate Existing Reports

One-time migration script to:
1. Read all entries from `manifest.jsonl`
2. Re-render each report with web mode
3. Copy to `docs/archive/` with new filename format
4. Generate initial archive index

---

## File Summary

| File | Action |
|------|--------|
| `.claude/skills/ai-news/scripts/date_utils.py` | Create |
| `.claude/skills/ai-news/scripts/render_html.py` | Modify |
| `.claude/skills/ai-news/scripts/write_report.py` | Modify |
| `.claude/skills/ai-news/scripts/generate_archive_index.py` | Create |
| `reports/.gitignore` | Modify |
| `docs/archive/` | Create directory |
| `docs/index.html` | Modify (add link) |
| `.github/workflows/publish-archive.yml` | Create |
| `.claude/skills/ai-news/SKILL.md` | Modify |

---

## Date Format Examples

| ISO Format | Human Filename | Display Format |
|------------|----------------|----------------|
| `2025-12-02` | `dec_2nd_2025` | Dec 2nd, 2025 |
| `2025-01-01` | `jan_1st_2025` | Jan 1st, 2025 |
| `2025-03-23` | `mar_23rd_2025` | Mar 23rd, 2025 |
| `2025-11-11` | `nov_11th_2025` | Nov 11th, 2025 |

---

## Execution Order

1. Create `date_utils.py`
2. Update `render_html.py` with web mode
3. Create `generate_archive_index.py`
4. Update `reports/.gitignore`
5. Create `docs/archive/` directory
6. Update `docs/index.html` with archive link
7. Create GitHub Action workflow
8. Run migration for existing reports
9. Update SKILL.md
10. Test end-to-end

---

## Testing Checklist

- [ ] `date_utils.py` correctly formats all ordinal cases (1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 22nd, 23rd, 31st)
- [ ] `render_html.py --mode web` removes unsubscribe footer
- [ ] Archive index generates correctly from manifest
- [ ] GitHub Action triggers on manifest change
- [ ] Archive pages display correctly in browser
- [ ] Navigation links work (signup ↔ archive)
- [ ] Existing reports migrate successfully
