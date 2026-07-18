#!/usr/bin/env bash
# apply.sh — install this repo onto the LIVE machine (repo → live).
# Idempotent. Doctrine is NOT applied (source of truth: ~/.ai-memory — edit there).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
H="$HOME"
SKILL_LINK="$H/.claude/skills/omnicode"

if [[ -e "$SKILL_LINK" && ! -L "$SKILL_LINK" ]]; then
  echo "refusing to replace existing non-symlink skill content: $SKILL_LINK" >&2
  exit 1
fi

echo "== apply: $REPO -> live system"

install -m 755 "$REPO/bin/lanes"            "$H/.local/bin/lanes"
install -m 755 "$REPO/bin/lane-pick"        "$H/.local/bin/lane-pick"
install -m 755 "$REPO/bin/uib"              "$H/.local/bin/uib"
install -m 755 "$REPO/bin/omnicode-doctor"  "$H/.local/bin/omnicode-doctor"

mkdir -p "$H/.uib" "$H/.claude/omnicode" "$H/.claude/agents" "$H/.claude/workflows" "$H/.claude/skills" "$H/.omnicode"
cp "$REPO/uib/uib.mjs"      "$H/.uib/uib.mjs"
cp "$REPO/uib/package.json" "$H/.uib/package.json"
[ -f "$REPO/uib/README.md" ] && cp "$REPO/uib/README.md" "$H/.uib/README.md"
if [ ! -d "$H/.uib/node_modules/playwright" ]; then
  echo "-- installing playwright into ~/.uib (one-time)"
  (cd "$H/.uib" && npm i --silent)
fi

cp "$REPO/config/ladders.json" "$H/.claude/omnicode/ladders.json"

for a in "$REPO"/agents/*.md; do
  cp "$a" "$H/.claude/agents/$(basename "$a")"
done

cp "$REPO/workflows/race-and-judge.mjs" "$H/.claude/workflows/race-and-judge.mjs"

# Skill: symlink so the repo stays source of truth (~/.claude/skills is real fs — probed 2026-07-18)
ln -sfn "$REPO/skill" "$SKILL_LINK"

# Daily doctor (silent monitor): launchd 08:45, records to ~/.omnicode/
cp "$REPO/launchd/com.casper.omnicode-doctor.plist" "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"
launchctl unload "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist" 2>/dev/null || true
launchctl load  "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"

echo "== applied. Doctrine NOT touched (source of truth: ~/.ai-memory/multi-model-orchestration.md)."
echo "Run: omnicode-doctor"
