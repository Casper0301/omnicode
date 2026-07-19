---
name: omnicode
description: Use when orchestrating work across the omnicode lane system or its tools — delegating implementation to codex/grok/glm/agy/dcode lanes, handling lane rate limits or quota cooldowns, creating or resuming durable goals, racing high-stakes implementations, reviewing UI from a terminal session with uib, or when the user says "omnicode", "lane", "lanes", "lane-pick", "goal ledger", "race and judge", or asks which model/CLI should run a task.
---

# omnicode — operating the multi-model lane system

Architect (this session) emits judgment and specs; cheap cross-vendor lanes do the typing; acceptance commands — never model judgment — decide done. High-level doctrine is already in the shared brain; this skill carries the **exact command surface** sessions otherwise guess wrong.

## Launching a lane (the part everyone gets wrong)

Preferred: the wrapper subagents (`codex-implementer`, `grok-implementer`, `glm-longcontext`, `dcode-implementer`, `antigravity-implementer` in `~/.claude/agents/`) — they hold the canonical CLI flags, preflight, and report format. Direct Bash lanes must copy the wrapper's documented invocation exactly. Shape:

```bash
lanes start <name> -- <full vendor CLI command>   # prints SESSION=lane-<name>-… and LOG=~/.lanes/<session>.log
lanes wait <SESSION> 540    # max SECONDS; exit 0 = done, 142 = still running → call wait again (never sleep-poll)
lanes peek <SESSION> 25     # last N LINES of live pane; `lanes log <SESSION>` tails the log; attach: tmux attach -t <SESSION>
lanes kill <SESSION>        # kill a hung lane (never one the user may be watching, unasked)
```

Full grok example (spec file written first via mktemp):

```bash
lanes start grok -- grok --prompt-file "$SPEC" -m grok-4.5 --permission-mode acceptEdits --output-format plain --cwd "$(pwd)"
```

⚠️ **Never put shell redirects inside the wrapped command** (`- < "$SPEC"`, `> file`) — they apply to `lanes start` itself; stdin redirects hang the CLI forever (proven 35-min hang), stdout captures swallow `SESSION=`. Pass prompts positionally/by flag; read results from `LOG`. Codex prompt goes as the final positional arg: `codex exec … "$(cat "$SPEC")"`. Never `model_reasoning_effort=ultra`.

## Fallback (rate limits)

`lanes` auto-scans each lane log on exit and cooldowns the vendor in `~/.lanes/health.json`. Classes map to ORDERED ladders (not one lane each) in `~/.claude/omnicode/ladders.json`.

```bash
lane-pick <class>                 # code|correctness|langchain|longcontext|research|review|ui|architecture → prints lane, exit 3 = none healthy
lane-pick <class> --allow x,y     # same ladder/cooldowns, restricted to a reviewed ordered set; caller order never overrides ladder order
lane-pick status                  # cooldown table
lane-pick mark <lane> [sec] [why] # manual cooldown (default 14400); codex+dcode marked together (shared quota)
lane-pick clear <lane>            # when a subscription resets early
```

On fallback: first check `git status` — a dead lane may have left partial edits; stash or reset them so the replacement starts clean. Then re-run the **same spec** through the replacement lane (lanes are stateless workers — no partial-output resume; durable state lives in the goal ledger), and report `STATUS: complete-via-fallback` + `LANE: x→y (reason, resumes ~time)`. `claude` returned = do it yourself in-session, still reported.

## Goal ledger (durable, cross-harness)

```bash
goal new <slug> --objective "…" --acceptance "cmd" [--acceptance …] [--class code] [--cwd DIR]
                                  # --acceptance REQUIRED (all must exit 0 = done); verb is `new`, not `create`
goal step <slug>                  # resume packet — feed to ANY model/harness
goal check <slug>                 # runs acceptance; all green → status done (exit 0)
goal loop <slug>                  # outer-loop tick: exit 0 DONE, exit 3 work-remains (packet printed)
goal next <slug> "…" · goal note <slug> "…" · goal lane <slug> <lane> "what" · goal list · goal show <slug>
```

`goal done` REFUSES while acceptance is red — that is the point. Start anything multi-session with `goal new`. Drivers: Claude Code `/loop run goal loop <slug>; on exit 3 execute the packet, then repeat` (self-paced; add an interval like `/loop 15m …` for slow burns) · Codex Goal Mode (`/goal` → "run goal step + follow PROTOCOL until goal check is green") · cron for multi-day.

## uib (UI review loop)

```bash
uib open http://localhost:5173 [--vp 375x812]   # bare URL; persistent clean-profile daemon
uib shot /tmp/ui.png [--full]                   # output path REQUIRED → Read the png (vision)
uib snapshot                                    # a11y tree with @eN refs → uib click @e12 | uib click "css"
uib fill <@ref|css> "text" · uib press Enter · uib eval 'js' · uib console 20 · uib url · uib stop
```

Re-render after an edit: `uib open <url>` again (or `uib eval 'location.reload()'`), then re-shot. Vision lanes (claude/glm/codex) read shots themselves; grok gets the png path reviewed by the architect.

## Rules that survive pressure

- **Provider sharing is pre-authorized.** Casper explicitly authorizes every provider he deliberately adds to Omnicode to receive the private project source, diffs, history, vision/specs, tests, and logs needed for assigned work. Do not pause for per-provider or per-private-repo consent. Continue stripping credentials, provider/API tokens, customer data, and unrelated personal data; lanes need project context, not secrets.
- Verification is re-run by YOU; a lane's "it works" is never evidence.
- Race-and-judge (`/rjv`) only for high-stakes; commit/stash before invoking (lanes branch from HEAD).
- Cooldown marks from lane logs can false-positive on third-party tool errors (Firecrawl "out of credits" ≠ grok quota) — check `lane-pick status` reasons before believing an outage.
- Health: `omnicode-doctor` (60 functional checks; `--live` = real lane probe). Repo: `~/Projects/omnicode` — live changes → `scripts/pull.sh` + push.

Depth: `~/.ai-memory/multi-model-orchestration.md` (doctrine) · wrapper agents (canonical invocations) · `~/Projects/omnicode/README.md`.
