#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Create logs directory
mkdir -p "${REPO_ROOT}/logs"

# Timestamped log file
LOG_FILE="${REPO_ROOT}/logs/pipeline_$(date '+%Y%m%d_%H%M%S').log"

# Redirect all output to log file and stdout
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "=== AI News Pipeline ==="
echo "Started: $(date)"
echo "Repo root: ${REPO_ROOT}"

# Source .env if present
if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a
    source "${REPO_ROOT}/.env"
    set +a
    echo "Loaded .env"
fi

# Check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv is not installed or not on PATH"
    exit 1
fi

# Check ANTHROPIC_API_KEY is set
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set"
    exit 1
fi

# Lockfile guard — prevent concurrent runs
LOCK_DIR="${REPO_ROOT}/.pipeline.lock"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
    echo "ERROR: Pipeline is already running (lock dir exists: ${LOCK_DIR})"
    exit 1
fi
trap "rmdir '${LOCK_DIR}'" EXIT

echo "Running pipeline..."

# Run the pipeline, capturing exit code without set -e interfering
if uv run python -m ai_news --days "${AI_NEWS_DAYS:-3}"; then
    EXIT_CODE=0
    echo "Pipeline completed successfully"
else
    EXIT_CODE=$?
    echo "Pipeline FAILED with exit code ${EXIT_CODE}"
    # macOS notification on failure
    osascript -e 'display notification "AI News pipeline FAILED — check logs" with title "AI News"' 2>/dev/null || true
fi

# Log rotation — keep only the 30 most recent pipeline log files
cd "${REPO_ROOT}/logs"
# shellcheck disable=SC2012
ls -1t pipeline_*.log 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true
cd "${REPO_ROOT}"

# # Git commit block (uncomment to enable auto-commit of reports)
# if [[ ${EXIT_CODE} -eq 0 ]]; then
#     cd "${REPO_ROOT}"
#     if git diff --quiet reports/ 2>/dev/null; then
#         echo "No new reports to commit"
#     else
#         git add reports/
#         git commit -m "chore: add AI news report $(date '+%Y-%m-%d')"
#         echo "Committed new report"
#     fi
# fi

echo "Finished: $(date)"
exit ${EXIT_CODE}
