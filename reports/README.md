# Reports Storage Contract

This directory stores generated AI news reports and related metadata.

## Path format

```
reports/ai-news_YYYY-MM-DD_to_YYYY-MM-DD_YYYYMMDDTHHMMSSZ.md
```

- All dates and timestamps are **UTC**.
- `YYYY-MM-DD` is the date range covered by the report.
- `YYYYMMDDTHHMMSSZ` is the UTC generation timestamp.

## Manifest

```
reports/manifest.jsonl
```

Append-only JSON Lines file with one entry per generated report.

## Manifest Schema

```json
{
  "filepath": "reports/ai-news_2024-12-22_to_2024-12-29_20241229T120000Z.md",
  "date_range_start": "2024-12-22",
  "date_range_end": "2024-12-29",
  "generated_at": "2024-12-29T12:00:00Z",
  "days": 7,
  "sources_ok": ["smol.ai", "huggingface", "hackernews"],
  "sources_failed": [],
  "total_items": 42,
  "bytes_written": 15234
}
```

## Latest pointer

```
reports/latest.md
```

A copy of the most recently generated report for quick access.
