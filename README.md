# omnicode

The owned layer of Casper's multi-model orchestration system: one architect CLI
(Claude Code on Claude Max) drives cross-vendor implementer lanes — Codex
(ChatGPT sub), Grok (xAI sub), Antigravity/agy (Google, free), GLM-5.2 (z.ai,
1M ctx), dcode (LangChain harness on the ChatGPT sub) — **subscription auth
only, zero API keys**, with automatic rate-limit fallback and a native browser
loop for UI work.

Same pattern as `openclaw-hq`: this repo versions the system; `scripts/pull.sh`
syncs live → repo (with a secret-scan gate), `scripts/apply.sh` installs
repo → live.

## Layout

| Path | What |
|---|---|
| `bin/lanes` | tmux lane runner (watchable sessions, logs, completion signal, rate-limit auto-scan on exit) |
| `bin/lane-pick` | fallback router: task class → strongest healthy lane; optional `--allow lane,lane` keeps hardened callers inside their reviewed adapter set; cooldowns in `~/.lanes/health.json` |
| `bin/uib` + `uib/` | clean-profile Playwright browser daemon+CLI for iterative UI review (open/shot/snapshot @refs/click/fill/eval/console) |
| `bin/omnicode-doctor` | deep health check — see Monitoring |
| `config/ladders.json` | per-class fallback ladders + quota groups (codex+dcode share ChatGPT quota) |
| `agents/` | the seven lane wrapper subagents (`~/.claude/agents/`) |
| `workflows/race-and-judge.mjs` | high-stakes race: 4 families implement → judge → cross-vendor verify |
| `doctrine/` | versioned COPY of the doctrine — source of truth stays `~/.ai-memory/multi-model-orchestration.md` |
| `launchd/` | daily silent doctor run (08:45) |
| `STATUS.md` | last recorded doctor output |

## Monitoring — "does it actually work?"

`omnicode-doctor` functionally probes every layer, token-free by default:

- **CLIs + auth**: codex/grok/agy/glm/dcode installed and subscription-authed
- **Router**: ladders parse, every class resolves, quota groups intact
- **Lanes**: real tmux round-trip, auto-scan hook present
- **uib**: real browser round-trip on an offline-safe `data:` URL
- **Shared brain**: all vendor symlinks resolve to the SAME file; doctrine carries the fallback + uib sections; brain mentions the router
- **Wrappers**: all seven present, fallback protocol in each lane, known bugs absent
- **Skills/MCP/workflows**: rjv, race-and-judge, agent-harnesses MCP
- **State**: health.json, stale daemons, log bloat, forgotten tmux sessions

Flags: `--fast` (skip slow probes) · `--live` (one real prompt through the top
healthy code lane — burns a little quota, proves end-to-end) · `--record`
(write `~/.omnicode/doctor-last.txt` + history line).

A launchd job runs `omnicode-doctor --record` daily at 08:45, silently.
History: `~/.omnicode/doctor-history.log`. No notifications by design — check
`STATUS.md` after a pull, or run the doctor any time.

## Sync rules

- Changed something live → `scripts/pull.sh` → commit+push (scan must be clean).
- Changed something here → `scripts/apply.sh` (never edits doctrine live).
- Doctrine edits happen in `~/.ai-memory/` (the shared brain), never here.

---
Maintained via Claude Code (omnicode architect sessions). Created 2026-07-18.
