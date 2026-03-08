#!/usr/bin/env bash
set -euo pipefail

# Uninstall the AI News pipeline launchd schedule

PLIST_LABEL="com.ainews.pipeline"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

# Unload and remove pipeline plist
if [[ -f "${PLIST_PATH}" ]]; then
    echo "Unloading ${PLIST_LABEL}..."
    launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || true
    rm -f "${PLIST_PATH}"
    echo "Removed ${PLIST_PATH}"
else
    echo "No plist found at ${PLIST_PATH}"
fi

# Clean up old newsletter plist if present
OLD_PLIST_LABEL="com.ainews.newsletter"
OLD_PLIST_PATH="${HOME}/Library/LaunchAgents/${OLD_PLIST_LABEL}.plist"
if [[ -f "${OLD_PLIST_PATH}" ]]; then
    echo "Cleaning up old newsletter plist..."
    launchctl bootout "gui/$(id -u)" "${OLD_PLIST_PATH}" 2>/dev/null || true
    rm -f "${OLD_PLIST_PATH}"
    echo "Removed ${OLD_PLIST_PATH}"
fi

# Verify removal
if launchctl list 2>/dev/null | grep -q "${PLIST_LABEL}"; then
    echo "WARNING: ${PLIST_LABEL} still appears in launchctl list"
    exit 1
else
    echo "Successfully uninstalled AI News pipeline schedule"
fi
