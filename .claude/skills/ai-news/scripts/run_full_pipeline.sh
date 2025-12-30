#!/bin/bash
# AI News Full Pipeline - Runs Claude headlessly to generate report and send newsletter
# Scheduled to run daily at 8 AM EST, but only executes on even days

set -e
cd /Users/julien.hovan/ClaudeWorkflows/AI-News-Reports

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/pipeline.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if today is an even day (run every 2 days)
# Use env var if set (for testing), otherwise get from date
DAY_OF_YEAR=${DAY_OF_YEAR:-$(date +%j)}
if [ $((DAY_OF_YEAR % 2)) -ne 0 ]; then
  log "Skipping - odd day ($DAY_OF_YEAR)"
  exit 0
fi

log "Starting AI News pipeline (day $DAY_OF_YEAR)..."

# Phase 1: Run Claude headlessly to generate report (last 2 days)
log "Phase 1: Running Claude to generate report..."
if claude -p "/ai-news 2" --dangerously-skip-permissions \
  >> "$LOG_DIR/claude_$TIMESTAMP.log" 2>&1; then
  log "Phase 1 complete: Report generated"
else
  log "ERROR: Claude failed to generate report"
  exit 1
fi

# Phase 2: Send newsletter (uses reports/latest.html)
log "Phase 2: Sending newsletter..."
if uv run python .claude/skills/ai-news/scripts/send_newsletter.py \
  >> "$LOG_DIR/newsletter_$TIMESTAMP.log" 2>&1; then
  log "Phase 2 complete: Newsletter sent"
else
  log "ERROR: Failed to send newsletter"
  exit 1
fi

log "Pipeline complete"
