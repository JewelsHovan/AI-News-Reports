# Cloudflare Archive System - Implementation Plan

## Goal
Replace the git-based `manifest.jsonl` archive system with Cloudflare R2 + KV, plus a management UI on GitHub Pages.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────┐
│ Report Pipeline │     │        Cloudflare                │
│ (Claude + Py)   │────▶│  ┌─────────┐    ┌─────────────┐  │
└─────────────────┘     │  │   R2    │    │     KV      │  │
                        │  │ (HTML   │    │ (JSON index)│  │
                        │  │ reports)│    │             │  │
                        │  └────▲────┘    └──────▲──────┘  │
                        │       │                │         │
                        │  ┌────┴────────────────┴──────┐  │
                        │  │      Worker API            │  │
                        │  │  (CRUD + public read)      │  │
                        │  └────────────▲───────────────┘  │
                        └───────────────┼──────────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │       GitHub Pages            │
                        │  ┌─────────────────────────┐  │
                        │  │   Archive Viewer        │  │
                        │  │   (public, read-only)   │  │
                        │  ├─────────────────────────┤  │
                        │  │   Admin Panel           │  │
                        │  │   (edit/delete reports) │  │
                        │  └─────────────────────────┘  │
                        └───────────────────────────────┘
```

## Data Structures

### KV Index (key: `archive-index`)
```json
{
  "reports": [
    {
      "id": "2026-01-02_20260102T081220Z",
      "date_range_start": "2025-12-31",
      "date_range_end": "2026-01-02",
      "generated_at": "2026-01-02T08:12:20Z",
      "title": "AI News Digest: Dec 31 - Jan 2",
      "summary": "Key developments in...",
      "r2_key": "reports/2026-01-02_20260102T081220Z.html",
      "days": 2,
      "total_items": 74
    }
  ],
  "updated_at": "2026-01-02T08:15:00Z"
}
```

### R2 Structure
```
reports/
  └── {id}.html          # Full HTML report (web mode)
```

---

## Implementation Tasks

### Task 1: Cloudflare Worker API (extend existing `ai-news-signup`)

Extend the existing worker at `ai-news-signup/` to add archive endpoints:

**New Routes:**
| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| `GET` | `/archive` | Public | Get index from KV |
| `GET` | `/archive/:id` | Public | Get report HTML from R2 |
| `POST` | `/archive` | Admin | Add new report (upload HTML + update index) |
| `PATCH` | `/archive/:id` | Admin | Update report metadata |
| `DELETE` | `/archive/:id` | Admin | Remove report from R2 + index |

**Wrangler Config Additions:**
```toml
[[kv_namespaces]]
binding = "ARCHIVE_KV"
id = "<to-be-created>"

[[r2_buckets]]
binding = "ARCHIVE_R2"
bucket_name = "ai-news-archive"
```

**Files to create/modify:**
- `ai-news-signup/src/index.ts` - Add archive routes
- `ai-news-signup/src/archive.ts` - Archive handlers (new)
- `ai-news-signup/wrangler.toml` - Add KV + R2 bindings

---

### Task 2: GitHub Pages Admin Interface

Create a simple admin panel at `docs/admin/`:

**Features:**
- View all reports in a table
- Edit metadata (title, summary) inline
- Delete reports with confirmation
- Responsive design matching existing glassmorphism style

**Auth Approach:**
- Simple token-based auth (reuse `AI_NEWS_API_SECRET`)
- Token stored in localStorage after initial entry
- Admin routes on Worker validate token

**Files to create:**
- `docs/admin/index.html` - Admin panel SPA
- `docs/admin/admin.js` - CRUD operations
- `docs/admin/admin.css` - Styles (or reuse styles.css)

---

### Task 3: Update Archive Viewer

Modify `docs/archive/index.html` to fetch from Cloudflare instead of being statically generated:

**Changes:**
- Remove static HTML generation from `generate_archive_index.py`
- Make `docs/archive/index.html` a dynamic page that fetches from Worker
- Reports load on-demand from R2 via Worker

**Files to modify:**
- `docs/archive/index.html` - Convert to dynamic fetch

---

### Task 4: Update Pipeline Integration

Modify `write_report.py` or create new script to upload to Cloudflare:

**Option A:** New `upload_to_archive.py` script
- Takes rendered HTML as input
- Uploads to R2 via Worker API
- Updates KV index

**Option B:** Modify `generate_archive_index.py`
- Instead of writing to `docs/archive/`, upload to Cloudflare
- Can be run manually to migrate existing reports

**Files to create/modify:**
- `.claude/skills/ai-news/scripts/upload_to_archive.py` (new)
- Update SKILL.md to include upload step

---

### Task 5: Migration

Migrate existing reports from `docs/archive/` to Cloudflare:

1. Read existing `manifest.jsonl`
2. For each report, render HTML and upload to R2
3. Build KV index from manifest data
4. Verify all reports accessible via Worker

---

## Implementation Order

1. **Task 1** - Worker API (foundation for everything else)
2. **Task 3** - Archive viewer (can test with empty/mock data)
3. **Task 2** - Admin panel (needs Worker API)
4. **Task 5** - Migration (populate with real data)
5. **Task 4** - Pipeline integration (final step)

---

## Cloudflare Resources to Create

```bash
# Create KV namespace
wrangler kv:namespace create ARCHIVE_KV

# Create R2 bucket
wrangler r2 bucket create ai-news-archive

# Update wrangler.toml with IDs, then deploy
wrangler deploy
```

---

## Security Considerations

- Admin routes protected by `AI_NEWS_API_SECRET` header
- Public routes are read-only
- CORS configured for GitHub Pages domain only
- No sensitive data in reports (public news summaries)

---

## Rollback Plan

- Keep `manifest.jsonl` and `generate_archive_index.py` intact
- Can revert to static generation if Cloudflare has issues
- GitHub Action workflow remains but disabled

---

## Success Criteria

1. Reports viewable at `docs/archive/` fetching from Cloudflare
2. Admin can edit metadata and delete reports via UI
3. Pipeline can upload new reports without git commits
4. Existing reports migrated successfully
