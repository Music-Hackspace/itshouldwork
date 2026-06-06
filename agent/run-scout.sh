#!/bin/bash
# Daily Photo Scout runner (local, scheduled via launchd).
# Runs Claude Code headless to pick + publish today's photo for itshouldwork.org.
set -uo pipefail

export PATH="/Users/jb/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="/Users/jb/Docs/itshouldwork"
LOG="$HOME/Library/Logs/itshouldwork-scout.log"
TODAY="$(date -u +%F)"

cd "$REPO" || { echo "$(date) ERROR: repo not found" >> "$LOG"; exit 1; }

echo "" >> "$LOG"
echo "========== scout run start $(date) (UTC date $TODAY) ==========" >> "$LOG"

# Sync with remote first (protect any local edits).
git pull --rebase --autostash origin main >> "$LOG" 2>&1 || echo "$(date) WARN: git pull failed, continuing" >> "$LOG"

claude -p "Read the file agent/scout-prompt.md in this repository and follow its instructions exactly to publish today's photo of the day. Today's UTC date is ${TODAY}. You are running unattended via a scheduled job: do NOT ask any questions, make the best judgment call yourself, and complete every step end to end — including downloading the image, updating photo.json, and committing and pushing to origin/main so GitHub Pages redeploys. Never publish anything depicting harm to people." \
  --model opus \
  --allowedTools "Bash Read Write Edit Glob Grep WebSearch WebFetch" \
  --dangerously-skip-permissions >> "$LOG" 2>&1

STATUS=$?
echo "========== scout run end $(date) (exit $STATUS) ==========" >> "$LOG"
exit $STATUS
