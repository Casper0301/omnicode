#!/usr/bin/env bash
# pull.sh — sync the LIVE omnicode system into this repo (live → repo).
# Run after changing anything on the machine directly. Ends with a secret scan;
# commit only when the scan is clean.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
H="$HOME"

echo "== pull: live system -> $REPO"

# Executables (owned layer)
cp "$H/.local/bin/lanes"      "$REPO/bin/lanes"
cp "$H/.local/bin/lane-pick"  "$REPO/bin/lane-pick"
cp "$H/.local/bin/uib"        "$REPO/bin/uib"
if [ "$H/.local/bin/goal" -nt "$REPO/bin/goal" ] 2>/dev/null; then
  cp "$H/.local/bin/goal" "$REPO/bin/goal"
fi
# omnicode-doctor is authored IN the repo; only pull it back if the live copy is newer
if [ "$H/.local/bin/omnicode-doctor" -nt "$REPO/bin/omnicode-doctor" ] 2>/dev/null; then
  cp "$H/.local/bin/omnicode-doctor" "$REPO/bin/omnicode-doctor"
fi

# uib implementation
cp "$H/.uib/uib.mjs"       "$REPO/uib/uib.mjs"
cp "$H/.uib/package.json"  "$REPO/uib/package.json"
[ -f "$H/.uib/README.md" ] && cp "$H/.uib/README.md" "$REPO/uib/README.md"

# Config
cp "$H/.claude/omnicode/ladders.json" "$REPO/config/ladders.json"
[ -f "$H/.claude/omnicode/models.json" ] && \
  cp "$H/.claude/omnicode/models.json" "$REPO/config/models.json"

# Active lane wrapper agents. Gemini/Antigravity lanes are retired by policy.
for a in fable-advisor codex-implementer grok-implementer glm-longcontext \
         dcode-implementer; do
  cp "$H/.claude/agents/$a.md" "$REPO/agents/$a.md"
done
rm -f "$REPO/agents/antigravity-implementer.md" \
      "$REPO/agents/gemini-reviewer.md"

# Workflow + companion skill
cp "$H/.claude/workflows/race-and-judge.mjs" "$REPO/workflows/race-and-judge.mjs"
[ -f "$H/.claude/skills/rjv/SKILL.md" ] && \
  cp "$H/.claude/skills/rjv/SKILL.md" "$REPO/skills/rjv/SKILL.md"

# Doctrine — VERSIONED COPY ONLY. Source of truth stays ~/.ai-memory (memory system);
# apply.sh deliberately never writes this back.
{
  echo "<!-- VERSIONED COPY — source of truth: ~/.ai-memory/multi-model-orchestration.md"
  echo "     Edit there (it is the shared brain's doctrine); pull.sh refreshes this copy. -->"
  cat "$H/.ai-memory/multi-model-orchestration.md"
} > "$REPO/doctrine/multi-model-orchestration.md"

# Latest doctor verdict, if one is recorded
[ -f "$H/.omnicode/doctor-last.txt" ] && cp "$H/.omnicode/doctor-last.txt" "$REPO/STATUS.md"

echo "== secret scan"
PATTERNS='sk-[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xoxb-[0-9A-Za-z-]+|-----BEGIN [A-Z ]*PRIVATE KEY|eyJhbGciOi[A-Za-z0-9._-]{40,}'
if HITS=$(grep -rInE "$PATTERNS" "$REPO" --exclude-dir=.git --exclude-dir=node_modules 2>/dev/null); then
  echo "SECRET SCAN FAILED — do NOT commit:"
  echo "$HITS"
  exit 1
fi
echo "clean. Next: git add -A && git commit && git push"
