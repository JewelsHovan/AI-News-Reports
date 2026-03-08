#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUNNER="${REPO_ROOT}/scripts/run_pipeline.sh"

# Check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv is not installed or not on PATH"
    exit 1
fi

# Detect uv directory for PATH in plist
UV_DIR="$(dirname "$(command -v uv)")"
PLIST_PATH_ENV="${UV_DIR}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Check runner script exists and make executable
if [[ ! -f "${RUNNER}" ]]; then
    echo "ERROR: Runner script not found: ${RUNNER}"
    exit 1
fi
chmod +x "${RUNNER}"

PLIST_LABEL="com.ainews.pipeline"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

# Idempotent: unload existing job if present
if launchctl list 2>/dev/null | grep -q "${PLIST_LABEL}"; then
    echo "Unloading existing ${PLIST_LABEL}..."
    launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || true
fi

# Clean up old newsletter plist if present
OLD_PLIST_LABEL="com.ainews.newsletter"
OLD_PLIST_PATH="${HOME}/Library/LaunchAgents/${OLD_PLIST_LABEL}.plist"
if [[ -f "${OLD_PLIST_PATH}" ]]; then
    echo "Cleaning up old newsletter plist..."
    launchctl bootout "gui/$(id -u)" "${OLD_PLIST_PATH}" 2>/dev/null || true
    rm -f "${OLD_PLIST_PATH}"
fi

# Create logs directory
mkdir -p "${REPO_ROOT}/logs"

# Generate launchd plist
cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${RUNNER}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${REPO_ROOT}</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>${REPO_ROOT}/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>${REPO_ROOT}/logs/launchd.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${PLIST_PATH_ENV}</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
</dict>
</plist>
EOF

echo "Generated plist: ${PLIST_PATH}"

# Load the job
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"

# Verify
if launchctl list 2>/dev/null | grep -q "${PLIST_LABEL}"; then
    echo "Successfully installed and loaded ${PLIST_LABEL}"
    echo ""
    echo "Schedule:"
    echo "  - Monday at 08:00"
    echo "  - Thursday at 08:00"
    echo ""
    echo "Runner: ${RUNNER}"
    echo "Logs:   ${REPO_ROOT}/logs/"
else
    echo "ERROR: Failed to load ${PLIST_LABEL}"
    exit 1
fi
