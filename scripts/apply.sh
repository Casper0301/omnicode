#!/usr/bin/env bash
# apply.sh — install this repo onto the LIVE machine (repo → live).
# Idempotent. Doctrine is NOT applied (source of truth: ~/.ai-memory — edit there).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
H="$HOME"
CLAUDE_SKILLS="$H/.claude/skills"
AGENT_SKILLS="$H/.agents/skills"
mkdir -p "$CLAUDE_SKILLS" "$H/.agents"
if [[ -e "$AGENT_SKILLS" || -L "$AGENT_SKILLS" ]]; then
  if [[ ! -L "$AGENT_SKILLS" ]] || [[ "$(realpath "$AGENT_SKILLS")" != "$(realpath "$CLAUDE_SKILLS")" ]]; then
    echo "refusing unsafe skills root (must symlink to $CLAUDE_SKILLS): $AGENT_SKILLS" >&2
    exit 1
  fi
else
  ln -s "$CLAUDE_SKILLS" "$AGENT_SKILLS"
fi

SKILL_LINKS=(
  "$AGENT_SKILLS/omnicode"
  "$CLAUDE_SKILLS/omnicode"
)

for skill_link in "${SKILL_LINKS[@]}"; do
  if [[ -e "$skill_link" && ! -L "$skill_link" ]]; then
    echo "refusing to replace existing non-symlink skill content: $skill_link" >&2
    exit 1
  fi
done

echo "== apply: $REPO -> live system"

install -m 755 "$REPO/bin/lanes"            "$H/.local/bin/lanes"
install -m 755 "$REPO/bin/lane-pick"        "$H/.local/bin/lane-pick"
install -m 755 "$REPO/bin/goal"             "$H/.local/bin/goal"
install -m 755 "$REPO/bin/uib"              "$H/.local/bin/uib"
install -m 755 "$REPO/bin/omnicode-doctor"  "$H/.local/bin/omnicode-doctor"

mkdir -p "$H/.uib" "$H/.claude/omnicode" "$H/.claude/agents" "$H/.claude/workflows" "$CLAUDE_SKILLS" "$H/.omnicode"
cp "$REPO/uib/uib.mjs"      "$H/.uib/uib.mjs"
cp "$REPO/uib/package.json" "$H/.uib/package.json"
[ -f "$REPO/uib/README.md" ] && cp "$REPO/uib/README.md" "$H/.uib/README.md"
if [ ! -d "$H/.uib/node_modules/playwright" ]; then
  echo "-- installing playwright into ~/.uib (one-time)"
  (cd "$H/.uib" && npm i --silent)
fi

cp "$REPO/config/ladders.json" "$H/.claude/omnicode/ladders.json"
cp "$REPO/config/models.json"  "$H/.claude/omnicode/models.json"

for a in "$REPO"/agents/*.md; do
  cp "$a" "$H/.claude/agents/$(basename "$a")"
done
# Current policy has no Gemini/Antigravity lane. Remove retired wrappers so
# agent discovery cannot advertise capabilities that must not be routed.
rm -f "$H/.claude/agents/antigravity-implementer.md" \
      "$H/.claude/agents/gemini-reviewer.md"

cp "$REPO/workflows/race-and-judge.mjs" "$H/.claude/workflows/race-and-judge.mjs"

# Skills: Omnicode is symlinked; the small RJV companion is copied so this
# repo remains the source of truth without replacing the shared skills root.
for skill_link in "${SKILL_LINKS[@]}"; do
  ln -sfn "$REPO/skill" "$skill_link"
done
mkdir -p "$H/.claude/skills/rjv"
cp "$REPO/skills/rjv/SKILL.md" "$H/.claude/skills/rjv/SKILL.md"

# Daily doctor (silent monitor): launchd 08:45, records to ~/.omnicode/
cp "$REPO/launchd/com.casper.omnicode-doctor.plist" "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"
launchctl unload "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist" 2>/dev/null || true
launchctl load  "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"

echo "== applied. Doctrine NOT touched (source of truth: ~/.ai-memory/multi-model-orchestration.md)."
echo "Run: omnicode-doctor"
