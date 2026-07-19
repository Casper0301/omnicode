#!/usr/bin/env bash
# queue-factory-goals — enqueue the factory phase-2 work as omnicode goals.
#
# Run ON THE OPERATOR MAC (needs ~/.local/bin/goal and the live layout).
# Idempotent: goals that already exist are left untouched. Each goal carries
# machine-checkable acceptance; any harness picks work up with `goal step`.
# Context for every item: casper-ai-runtime/docs/portability-and-reliability-2026-07-19.md
set -euo pipefail

GOAL="${GOAL_BIN:-$HOME/.local/bin/goal}"
RUNTIME="$HOME/Projects/casper-ai-runtime"
HQ="$HOME/Projects/openclaw-hq"

have(){ "$GOAL" list 2>/dev/null | awk '{print $2}' | grep -qx "$1"; }

queue(){
  local slug="$1"; shift
  if have "$slug"; then
    printf 'skip (exists): %s\n' "$slug"
    return 0
  fi
  "$GOAL" new "$slug" "$@"
}

queue autoradar-generic-migration \
  --class architecture --cwd "$RUNTIME" \
  --objective "Migrate autoradar off tools/autonomy/supervisor.mjs onto the generic openclaw-dev controller: write the reviewed manifest per docs/onboarding-a-project.md, run openclaw-project-onboard, canary one episode to a draft PR, then disable the v1 supervisor launchd job. Casper reviews the manifest and merges the canary." \
  --acceptance "test -f $HOME/.config/openclaw-dev/reviewed/autoradar.json" \
  --acceptance "$HOME/.local/bin/openclaw-dev-remote 'project autoradar status' | grep -q '\"state\"'" \
  --acceptance "! launchctl list 2>/dev/null | grep -q autoradar-autonomy-supervisor"

queue second-project-canary \
  --class architecture --cwd "$RUNTIME" \
  --objective "Onboard a second project (some-os or noteforge) onto the generic controller as the multi-project canary, per docs/onboarding-a-project.md. Proves 'works on any project'." \
  --acceptance "$HOME/.local/bin/openclaw-dev-remote projects | python3 -c 'import json,sys;d=json.load(sys.stdin);assert len(d[\"projects\"])>=2, d'"

queue hq-generic-supervisor \
  --class code --cwd "$HQ" \
  --objective "Collapse mac/bin/autoradar-autonomy-supervisor, autoradar-incident-triage, and autoradar-resume-watch into slug-parameterized openclaw-* scripts driven by the project registry (no 'Casper0301/autoradar' literals); mac/apply.sh installs one launchd per registered project." \
  --acceptance "test -x $HQ/mac/bin/openclaw-autonomy-supervisor" \
  --acceptance "! grep -q 'Casper0301/autoradar' $HQ/mac/bin/openclaw-autonomy-supervisor"

queue hq-agent-model-fallbacks \
  --class code --cwd "$HQ" \
  --objective "Give every OpenClaw agent a non-empty model fallbacks list in the live gateway config (autoradar agents currently have \"fallbacks\": [] — a pulled model kills them, as the Fable-5 removal proved), then scripts/pull.sh so the sanitized mirror reflects it." \
  --acceptance "! grep -q '\"fallbacks\": \\[\\]' $HQ/config/openclaw.sanitized.json5"

queue hq-cron-snapshot \
  --class code --cwd "$HQ" \
  --objective "cron/jobs.sanitized.json is an empty {} while three live cron jobs exist — fix scripts/pull.sh sanitization so the mirror captures them." \
  --acceptance "python3 -c 'import json;d=json.load(open(\"$HQ/cron/jobs.sanitized.json\"));assert d, \"cron snapshot is empty\"'"

queue monitor-hardening \
  --class code --cwd "$RUNTIME" \
  --objective "Harden project-monitor.sh per the 2026-07-19 reliability review: bounded with_timeout on every controller call (a hung gh call currently stalls all monitoring under the flock), split read-only status from GitHub-mutating reconciliation, and fix the attempting-receipt crash window that reports successful starts as failures." \
  --acceptance "grep -q with_timeout $RUNTIME/controllers/openclaw-dev-control/project-monitor.sh" \
  --acceptance "cd $RUNTIME/controllers/openclaw-dev-control && node --test >/dev/null 2>&1"

printf 'queued. next: goal list && goal step <slug>\n'
