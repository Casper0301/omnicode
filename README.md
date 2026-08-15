# omnicode

Casper's owned multi-model orchestration layer: one trusted architect session routes bounded work to subscription-backed Codex, Grok, GLM, and dcode lanes, then independently verifies the result. It provides visible tmux execution, quota-aware fallback, a durable goal ledger, isolated high-stakes race-and-judge, and a clean-profile UI loop.

**Current lane policy:** no Gemini or Antigravity lane. Non-Anthropic cross-checks route to Grok first and Codex second.

Configured providers may receive the private repository context needed for an assigned task: relevant source, diffs, tests, and logs. That is not credential or customer-data authorization. Common API-key and GitHub environment variables are stripped, but the runner is not filesystem-level secret isolation; do not expose `.env` files, tokens, customer data, or unrelated personal data.

The repo versions the system. `scripts/pull.sh` syncs live → repo with a secret-scan gate. `scripts/apply.sh` installs repo → live. The doctrine copy under `doctrine/` is generated from `~/.ai-memory/multi-model-orchestration.md`; edit the memory source, then pull.

## Layout

| Path | Purpose |
|---|---|
| `bin/lanes` | Watchable tmux lane runner with logs, durable exit codes, and rate-limit auto-scan |
| `bin/lane-pick` | Task class → strongest configured healthy lane; cooldowns in `~/.lanes/health.json` |
| `bin/goal` | Durable cross-harness goals with machine-checkable acceptance |
| `bin/uib` + `uib/` | Clean-profile Playwright UI review CLI |
| `bin/omnicode-doctor` | Functional installation and behavior checks |
| `config/ladders.json` | Ordered fallback ladders and shared quota groups |
| `agents/` | Active Claude Code wrapper agents: Fable advisor, Codex, Grok, GLM, dcode |
| `workflows/race-and-judge.mjs` | High-stakes race: Opus/Codex/Grok implement, Opus judges, GLM verifies |
| `skill/SKILL.md` | Harness-aware operational interface discovered by Pi and Claude Code |
| `doctrine/` | Versioned copy of the external doctrine source |
| `STATUS.md` | Dated doctor snapshot, not live health |

## Core usage

```bash
lane-pick code
lanes start <name> -- <vendor command...>
lanes wait <SESSION> 540   # 0=vendor success; 142=still running; other=failed
lanes result <SESSION>
omnicode-doctor
goal list
```

In Pi, launch external vendor CLIs through `lanes`; Claude-host wrapper subagents can fail on Anthropic quota before the requested vendor starts. In Claude Code, prefer the wrapper agents in `~/.claude/agents/`.

## Monitoring

`omnicode-doctor` runs token-free functional checks by default:

- required binaries and subscription-auth probes
- router classes, quota groups, and credential state
- real `lanes` success/failure round-trips and exit-code propagation
- `uib` clean-profile browser round-trip
- shared-brain links and doctrine coherence
- active wrappers and retired-lane absence
- skill/workflow safety regressions
- goal-ledger round-trip
- repository unit tests and state hygiene

Flags: `--fast` skips slower auth/browser probes. `--live` sends one tiny prompt through the top healthy code lane and burns quota. `--record` updates `~/.omnicode/doctor-last.txt` and history.

Launchd runs `omnicode-doctor --record` daily at 08:45. `STATUS.md` changes only after `scripts/pull.sh`; always check its timestamp and rerun the doctor for current truth.

## Sync

```bash
# Live changed first
./scripts/pull.sh

# Repo changed first
./scripts/apply.sh
omnicode-doctor
```

Doctrine is never applied from this repo. Update `~/.ai-memory/multi-model-orchestration.md`, then use `scripts/pull.sh` to refresh the versioned copy.
