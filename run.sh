#!/bin/bash
# AI News Manual Runner - Generate report and optionally send newsletter
# Usage: ./run.sh [days] [--send]
#   days: Number of days to look back (default: 2)
#   --send: Also send the newsletter after generating

set -e
cd "$(dirname "$0")"

DAYS=2
SEND_NEWSLETTER=false

# Parse args
for arg in "$@"; do
  case $arg in
    --send) SEND_NEWSLETTER=true ;;
    *[0-9]*)
      if [[ "$arg" =~ ^[0-9]+$ ]]; then
        DAYS=$arg
      fi
      ;;
  esac
done

echo "=== AI News Pipeline ==="
echo "Looking back: $DAYS days"
echo "Send newsletter: $SEND_NEWSLETTER"
echo ""

# Phase 1: Generate report with Claude
echo "[1/2] Generating report with Claude..."
echo "Running ai-news skill for $DAYS days (this may take 5-10 minutes)..."
echo ""

claude -p "Run the /ai-news skill for $DAYS days. Generate the full report and save it." --dangerously-skip-permissions

echo ""
echo "[1/2] Report generation complete!"

# Check if report was created
if [ -f "reports/latest.html" ]; then
  echo "Report found: reports/latest.html"
else
  echo "Warning: reports/latest.html not found!"
fi
echo ""

# Phase 2: Send newsletter (optional)
if [ "$SEND_NEWSLETTER" = true ]; then
  echo "[2/2] Sending newsletter..."

  # Check if API credentials are set
  if [ -n "$AI_NEWS_API_SECRET" ]; then
    uv run python .claude/skills/ai-news/scripts/send_newsletter.py \
      --api-url "https://ai-news-signup.julienh15.workers.dev/api/subscribers" \
      --api-secret "$AI_NEWS_API_SECRET" \
      --verbose
  else
    echo "Warning: AI_NEWS_API_SECRET not set, using file-based recipients"
    uv run python .claude/skills/ai-news/scripts/send_newsletter.py --verbose
  fi

  echo "[2/2] Newsletter sent!"
else
  echo "[2/2] Skipping newsletter (use --send to send)"
fi

echo ""
echo "=== Done ==="
