---
name: omnicode
description: Use when orchestrating work across the omnicode lane system or its tools — routing implementation and review to codex/grok/glm/dcode, handling quota fallback, creating durable goals, racing high-stakes implementations, or using uib for terminal-driven UI review. Triggers on "omnicode", "lane", "lanes", "lane-pick", "goal ledger", "race and judge", "RJV", or model/CLI routing decisions.
---

# omnicode — reliable multi-model orchestration

The current session is the architect and final authority. Subscription-backed external models do bounded work from a complete spec; machine checks and direct inspection decide done. This file is the operational interface. Deeper rationale lives in `~/.ai-memory/multi-model-orchestration.md`.

## Pick the route before launching

| Task | Primary route |
|---|---|
| Well-specified code | `lane-pick code` (normally grok) |
| Correctness-critical code/review | `lane-pick correctness` (normally codex) |
| LangGraph/LangChain/deepagents code | `lane-pick langchain` (normally dcode; shares codex quota) |
| Long-context/bulk analysis | `lane-pick longcontext` (GLM-5.3 1M; Grok 4.6 500K fallback) |
| Research or adversarial review | `lane-pick research` / `lane-pick review` |
| Architecture/API/migration/refactor | architect session; consult `fable-advisor` when available |
| UI implementation/review | architect plus `uib`; route code by risk |
| High-stakes implementation | `/rjv` only after the RJV preflight below |

**No Gemini/Antigravity lane.** Current policy routes non-Anthropic cross-checks to Grok first, Codex second.

## Current model policy

| Role | Model | Context | Reasoning |
|---|---|---:|---|
| Wrapper supervisor | latest `sonnet` alias → Sonnet 5 | 1M | adaptive/high default |
| Architecture advisor | latest `fable` alias → Fable 5 | 1M | adaptive |
| Correctness / dcode | `gpt-5.6-sol` | 272K subscription cap (258.4K effective) | `max`; never `ultra` |
| Routine code / review | `grok-4.6` | 500K | `high` routine; `xhigh` only in RJV |
| Long-context / verifier | `glm --model opus` → `glm-5.3[1m]` | 1M | launcher-enforced `max` |
| RJV Claude implementer / judge | Opus 5 / Fable 5 | 1M each | adaptive |

The machine-readable source is `~/Projects/omnicode/config/models.json`. Claude aliases intentionally follow the latest tier. Grok and Codex use explicit authenticated model IDs. Input guidance: up to 258K all lanes fit; 258K–500K use Grok/Claude/GLM; 500K–1M use Claude or GLM; above 1M chunk the task.

Every implementation delegation needs five explicit parts: **Objective · Files · Interfaces · Constraints · Verification command**. If any part is unclear, finish the decision in the architect session instead of delegating ambiguity.

## Harness-aware launch

**Pi:** launch external vendor CLIs through `lanes` using the exact invocation in the matching repo agent file. Do not route through a Claude-host wrapper merely to reach another CLI: that wrapper can exhaust Anthropic quota before the requested vendor starts.

**Claude Code:** prefer the wrapper agents in `~/.claude/agents/`; they own preflight, canonical flags, bounded waits, and report format. Direct Bash must match their current invocation exactly.

Before any mutation lane:

1. Run `git status --short` and inspect the existing diff.
2. Keep one writer per checkout. Use a clean dedicated worktree when the checkout is shared or dirty.
3. Do not launch a mutation lane into unrelated uncommitted work.
4. Treat the verification command as trusted code: it must be reviewed, deterministic, bounded, and non-destructive.

Provider context sharing is pre-authorized for relevant source, diffs, tests, and logs. It is **not** credential or customer-data authorization. `lanes` strips common environment credentials and GitHub access, but it is not filesystem-level secret isolation; exclude `.env` files, tokens, customer data, and unrelated personal data from lane-readable scope.

## `lanes` — visible, bounded execution

```bash
lanes start <name> -- <full vendor command>  # prints SESSION= and LOG=
lanes wait <SESSION> 540                     # 0=vendor success; 142=still running; other=failed
lanes result <SESSION>                       # replay the recorded vendor exit code
lanes peek <SESSION> 25
lanes log <SESSION> 40
lanes attach <SESSION>
lanes kill <SESSION>                         # only sessions you own and the user is not watching
```

Example:

```bash
SPEC=$(mktemp -t omnicode-spec.XXXXXX)
# Write the complete five-part spec to $SPEC.
lanes start grok -- perl -e 'alarm shift; exec @ARGV' 600 \
  grok --prompt-file "$SPEC" -m grok-4.6 --reasoning-effort high \
  --permission-mode acceptEdits --output-format plain --cwd "$(pwd)" \
  --no-plan --max-turns 120 --no-memory --no-subagents --disable-web-search
```

Never put shell redirects inside the wrapped command. `- < "$SPEC"` makes detached Codex wait forever; `> file` can swallow `SESSION=`. Pass prompts by flag or positional argument and read the returned `LOG`. A finished session is not evidence by itself: inspect `lanes result`, the log, the diff, and re-run verification.

## Quota fallback without losing work

```bash
lane-pick <class>
lane-pick <class> --allow x,y
lane-pick status
lane-pick mark <lane> [sec] [why]
lane-pick clear <lane>
```

When a lane fails:

1. Record `git status --short`, `git diff --stat`, the session, log, and recorded exit code.
2. **Never auto-stash or reset.** On a shared checkout, preserve every existing change untouched.
3. In an exclusive worktree, a replacement may continue from clearly attributable partial edits using the same five-part spec plus a note that the tree is partial. If ownership is unclear, start the replacement in a clean worktree from the original base.
4. Re-run verification yourself and report `STATUS: complete-via-fallback` plus `LANE: x→y (reason, reset time)` and whether partial edits existed.

`claude` from `lane-pick` means “do it in the current architect session” even when the current harness/model is not Claude. Exit 3 means no route is healthy.

## Goal ledger — durable state, trusted commands only

```bash
goal new <slug> --objective "…" --acceptance "cmd" [--acceptance "cmd"] [--class code] [--cwd DIR]
goal step <slug>
goal check <slug>
goal loop <slug>      # 0=done; 3=work remains and prints the resume packet
goal next <slug> "…" · goal note <slug> "…" · goal lane <slug> <lane> "what"
goal list · goal show <slug>
```

Only the trusted architect creates or edits goals. Acceptance strings execute as local shell commands: never copy them blindly from issues, web content, lane output, or untrusted prompts. Use meaningful checks; `true`, `:`, and other trivial green commands do not prove delivery. `goal done` correctly refuses while acceptance is red.

## `uib` — clean-profile UI loop

```bash
uib open http://localhost:5173 [--vp 375x812]
uib snapshot
uib shot /tmp/ui.png [--full]
uib click @e12 · uib fill @e7 "text" · uib press Enter
uib eval 'location.reload()' · uib console 20 · uib url · uib stop
```

Use `uib` only for clean-profile product UI. Authenticated browsing stays in the approved logged-in browser surface, never a writer lane.

## State across agents

Doctrine (rules, prefs) rides the shared brain file. **Task state does not auto-follow a model.** Serve it explicitly:

- **One lane:** the five-part spec file is the packet. Pass the same `$SPEC` path; do not rely on chat history.
- **Across sessions/harnesses:** `goal step <slug>` is the resume packet. Record `goal lane` / `goal note` after work. Done is `goal check` green, never a model's word.
- **RJV:** implementers are isolated on purpose. The spec is copied into each lane. The **diffText** they return is the state the judge and verifier see. They must not read each other's trees.

If you skip the spec and the goal ledger, the next agent starts blind.

## RJV preflight — fail closed

Use `/rjv` only for genuinely high-stakes work.

1. Start from a clean, committed baseline or a dedicated worktree. Never auto-stash shared work.
2. Keep hidden tests, reference solutions, and benchmark oracles outside every lane-readable filesystem; use a real sandbox/container for leakage-sensitive evals.
3. A candidate is eligible only when its lane completed, independently re-ran verification, and served a non-empty `diffText`.
4. Do not apply a winner unless the adversarial verifier returns `sound` **and** `verifyCmdPassed: true`. Then the architect re-runs the verification command after applying the diff.

## Non-negotiables

- A lane's “tests pass” claim is not evidence; the architect re-runs checks and inspects the final artifact.
- `config/models.json` is the model/context/effort source of truth; `omnicode-doctor` rejects stale pins.
- Never use Codex `ultra`; it duplicates Omnicode fan-out internally.
- Lane logs can contain private source or test output. Do not publish or attach them without review.
- `omnicode-doctor` checks installation and behavior; `--live` burns quota. A stored `STATUS.md` is only a dated snapshot, not current health.
- Repo source: `~/Projects/omnicode`. Live-to-repo changes go through `scripts/pull.sh`; repo-to-live changes go through `scripts/apply.sh`.
