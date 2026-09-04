#!/usr/bin/env bash
# apply.sh — install this repo onto the LIVE machine (repo → live).
# Idempotent. Doctrine is NOT applied (source of truth: ~/.ai-memory — edit there).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
H="$HOME"
CLAUDE_SKILLS="$H/.claude/skills"
AGENT_SKILLS="$H/.agents/skills"
CURSOR_SKILLS="$H/.cursor/skills"
mkdir -p "$H/.claude" "$H/.agents" "$H/.cursor"
if [[ -L "$CLAUDE_SKILLS" ]] || { [[ -e "$CLAUDE_SKILLS" ]] && [[ ! -d "$CLAUDE_SKILLS" ]]; }; then
  echo "refusing unsafe canonical skills library (must be a real directory): $CLAUDE_SKILLS" >&2
  exit 1
fi
mkdir -p "$CLAUDE_SKILLS"

ensure_empty_generic_root() {
  local root="$1" first_entry
  if [[ -L "$root" ]]; then
    echo "refusing generic skills root symlink: $root; run ~/.claude/bin/skill-tiers.py apply first" >&2
    exit 1
  elif [[ -e "$root" ]]; then
    if [[ ! -d "$root" ]]; then
      echo "refusing unsafe generic skills root (must be a real empty directory): $root" >&2
      exit 1
    fi
    first_entry="$(find "$root" -mindepth 1 -maxdepth 1 -print -quit)"
    if [[ -n "$first_entry" ]]; then
      echo "refusing generic skills root must be empty: $root (found $first_entry)" >&2
      exit 1
    fi
  else
    mkdir -p "$root"
  fi
}

ensure_empty_generic_root "$AGENT_SKILLS"
ensure_empty_generic_root "$CURSOR_SKILLS"

SKILL_LINK="$CLAUDE_SKILLS/omnicode"

if [[ -e "$SKILL_LINK" && ! -L "$SKILL_LINK" ]]; then
  echo "refusing to replace existing non-symlink skill content: $SKILL_LINK" >&2
  exit 1
fi

echo "== apply: $REPO -> live system"

install_bin() {
  local src="$1" dest="$2"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    return 0
  fi
  if [ -e "$dest" ] && [ "$(realpath "$src")" = "$(realpath "$dest")" ]; then
    return 0
  fi
  install -m 755 "$src" "$dest"
}

install_bin "$REPO/bin/lanes"            "$H/.local/bin/lanes"
install_bin "$REPO/bin/lane-pick"        "$H/.local/bin/lane-pick"
install_bin "$REPO/bin/goal"             "$H/.local/bin/goal"
install_bin "$REPO/bin/uib"              "$H/.local/bin/uib"
install_bin "$REPO/bin/omnicode-doctor"  "$H/.local/bin/omnicode-doctor"
install_bin "$REPO/bin/herdr-vps"        "$H/.local/bin/herdr-vps"
install_bin "$REPO/bin/herdr-open-url"   "$H/.local/bin/herdr-open-url"
install_bin "$REPO/bin/apply-race-artifact" "$H/.local/bin/apply-race-artifact"

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

# Skills: the canonical Claude library is the only full skill library. Generic
# discovery roots stay empty, and Omnicode exists only at its canonical path.
ln -sfn "$REPO/skill" "$SKILL_LINK"
mkdir -p "$H/.claude/skills/rjv"
cp "$REPO/skills/rjv/SKILL.md" "$H/.claude/skills/rjv/SKILL.md"

# Daily doctor (silent monitor): launchd 08:45 on macOS; systemd timer on Linux VPS
if [[ "$(uname)" == "Darwin" ]]; then
  cp "$REPO/launchd/com.casper.omnicode-doctor.plist" "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"
  launchctl unload "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist" 2>/dev/null || true
  launchctl load  "$H/Library/LaunchAgents/com.casper.omnicode-doctor.plist"
fi

echo "== applied. Doctrine NOT touched (source of truth: ~/.ai-memory/multi-model-orchestration.md)."
echo "Run: omnicode-doctor"
