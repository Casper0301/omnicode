<!-- VERSIONED COPY — source of truth: ~/.ai-memory/multi-model-orchestration.md
     Edit there (it is the shared brain's doctrine); pull.sh refreshes this copy. -->
---
name: multi-model-orchestration
description: "Federated multi-model orchestration doctrine — architect + cross-vendor CLI lanes + race-and-judge + adversarial verify, subscriptions only. Full detail; MEMORY.md holds the tight summary."
metadata: 
  node_type: memory
  type: project
  originSessionId: 88b8deba-1f7e-41ae-89f0-dfc41feb1808
  modified: 2026-08-15T22:48:00.000Z
---

# Multi-Model Orchestration (Federated)

**Shared brain** = `MEMORY.md` (symlinked to the configured vendor instruction roots). Pi or Claude Code acts as the trusted architect; Codex, Grok, GLM, and dcode are replaceable workers. **Subscriptions only** — no API-key billing path and no persistent `ANTHROPIC_BASE_URL` change. Lane commands are shell-portable. In Pi, launch external vendors directly through `lanes`; Claude-host wrapper subagents can exhaust Anthropic quota before the requested vendor starts. Claude Code may use the active wrappers in `~/.claude/agents/` (`fable-advisor`, `codex-implementer`, `grok-implementer`, `glm-longcontext`, `dcode-implementer`) plus `~/.claude/workflows/race-and-judge.mjs`.

**Current policy:** no Gemini or Antigravity lane. Cross-vendor review routes to Grok first, Codex second. Machine-readable model/context/effort truth lives in `~/Projects/omnicode/config/models.json`.

## Current model policy (verified 2026-08-16)

- Wrapper supervisors: latest `sonnet` alias → Claude Sonnet 5, 1M context, adaptive/high-default reasoning. Keep this efficient relay model; vendor CLIs do the task.
- Architecture commitment advisor: latest `fable` alias → Claude Fable 5, 1M context. `fable-advisor` must explicitly set `model: fable`.
- Correctness and dcode: `gpt-5.6-sol`, `max` reasoning, 272K ChatGPT-subscription context (258.4K effective). Never `ultra` because it launches internal subagents.
- Routine implementation/review: `grok-4.6`, 500K context, `high` reasoning. RJV alone raises Grok to `xhigh`.
- Long-context/verifier: `glm --model opus` → `glm-5.3[1m]`, 1M context, launcher-enforced `max`.
- RJV: Opus 5 implementer + GPT-5.6-Sol max + Grok 4.6 xhigh → Fable 5 judge → GLM-5.3 max verifier.

Context routing: ≤258K all lanes fit; 258K–500K use Grok/Claude/GLM; 500K–1M use Claude or GLM; above 1M chunk. OpenAI's API model supports a larger window, but Omnicode never switches from ChatGPT subscription auth to API-key billing.

## Provider context authorization (2026-07-19)

Casper explicitly authorizes every provider he deliberately configures in Omnicode to receive the private repository context required for assigned work: source, diffs, history, vision/specs, tests, and relevant logs. Do not pause for repeated provider- or private-repo-consent questions. This is context authorization, not credential authorization: continue stripping provider/API tokens, GitHub credentials, customer data, and unrelated personal data because lanes do not need them. Repository write isolation, independent verification, and trusted-orchestrator-only commit/push/PR ownership remain load-bearing workflow boundaries.

## Automatic fallback ladders (2026-07-17) — rate limits never stall work

- **`lane-pick <class>`** resolves to the strongest configured lane not on cooldown and not known dead. Classes: `code` (grok→glm→codex→claude) · `correctness` (codex→glm→grok→claude) · `langchain` (dcode→grok→glm→claude; codex skipped because it shares dcode quota) · `longcontext` (glm→grok→claude) · `research`/`review` (grok→glm→codex→claude) · `ui` (claude→glm→codex→grok) · `architecture` (claude). `claude` means the current architect session, regardless of provider.
- **Auto-detection:** `lanes` scans every vendor lane's log on exit (`lane-pick scan`) — quota/usage-limit errors mark the vendor's cooldown, parsing "Resets in 139h1m53s"-style times when present; transient errors (429/529/overloaded) get 15 min. Marking happens BEFORE the wait-for signal, so the caller's next `lane-pick` already routes around the outage.
- **Quota groups:** codex+dcode share the ChatGPT pool — marking one marks both.
- **Never silent:** every fallback is reported as `STATUS: complete-via-fallback` + `LANE: x→y (reason, resumes ~time)`. This AMENDS the old "never fallback to Claude" rule: `claude` is now the sanctioned LAST rung of every ladder (Casper 2026-07-17: "lean on GLM, Grok, or Claude — automatically"), always visibly.
- Ops: `lane-pick status` (cooldown table) · `lane-pick clear <lane>` (when a sub resets early) · `lane-pick mark <lane> [sec] [why]` (manual).

## UI verification loop — `uib` (2026-07-17)

Lanes run in terminals; `uib` (`~/.local/bin/uib` → `~/.uib/uib.mjs`, Playwright daemon) is the omnicode browser: persistent clean-profile Chromium the models drive by CLI. `uib open <url> [--vp 375x812]` · `shot <png> [--full]` · `snapshot` (a11y tree with @eN refs) · `click @eN|<css>` · `fill` · `press` · `eval` · `console` · `url` · `status` · `stop`. Iterative UI work: dev server → `uib open` → edit code → `uib shot` → READ the png (vision) → repeat. Vision-capable lanes (claude, glm, codex via view_image) self-review screenshots; grok lanes return the png path for the architect to review. Daemon idles out after 30 min; state (page, refs, console buffer) survives between invocations. **uib is clean-profile ONLY — Casper's authenticated browsing stays in `agent-browser`/Aside and remains BANNED for writer sandboxes/lanes.** `ui` ladder class routes UI review work.

## Goal ledger — durable cross-harness goals (2026-07-18)

Research-backed design (Codex Goal Mode + LangGraph checkpointer + Omnigent sessions + Anthropic multi-agent pattern, lanes-researched 2026-07-18): **the goal lives outside any model** — models are replaceable workers; acceptance COMMANDS define done, never model judgment. `goal` CLI (`~/.local/bin/goal`, state in `~/.omnicode/goals/<slug>.json` + append-only `.events.jsonl`):

- `goal new <slug> --objective "…" --acceptance "cmd" [--acceptance …] [--class code|correctness|…] [--cwd DIR]` — acceptance is REQUIRED ("a goal without a machine-checkable stop condition is a wish").
- **`goal step <slug>`** = the model-agnostic resume packet (objective, next action, suggested lane via lane-pick, acceptance, recent events, protocol). ANY harness picks up work by reading it.
- `goal check <slug>` runs acceptance; all green → status done. `goal done` REFUSES while red. `goal loop <slug>` = one outer-loop tick: exit 0 DONE / exit 3 work-remains (packet printed). Record work: `goal lane <slug> <lane> "what"` / `goal note` / `goal next`.

**Outer loop per harness** (the harness owns cadence, the ledger owns state):
- Claude Code: `/loop` on "run `goal loop <slug>`; if exit 3, execute the packet (implementation via lanes), then repeat" — or cron/schedule for multi-day.
- Codex CLI/app: `/goal` (Goal Mode) with objective: "Work omnicode goal <slug>: run `~/.local/bin/goal step <slug>` and follow its PROTOCOL until `goal check <slug>` is green." Sol's persistence + our routing.
- grok/glm: paste `goal step` output as the prompt; they read the shared brain so the protocol is known.
- **Economy rule:** acceptance-driven loop ticks use the lowest justified effort on an approved lane; judgment points use Fable/Sol-at-max. NEVER Sol `ultra` (it spawns internal subagents that duplicate Omnicode fan-out).

## Routing (architect picks per task)

- Pure coding / well-specified → **grok default** — ONLY with a complete 5-part spec; grok freestyles where the spec is silent (2026-07-09 eval), so the lane bounces incomplete specs back (`STATUS: spec-incomplete`) instead of running. Correctness-critical single lane → codex (GPT-5.6-Sol max).
- LangGraph / LangChain / deepagents agent code → **dcode** (DeepAgents Code — LangChain's own dogfooded harness; GPT-5.6-Sol @ max effort on the ChatGPT sub). Same 5-part-spec gate. Same family as codex (shared ChatGPT quota) — adds harness fit for LangChain-native work, NOT diversity; never counts as an extra race family. Harness prompts are NOT langgraph-specialized (checked v0.1.34) — the routing is a live bet; judge on real tasks, demote if it doesn't beat grok/codex there. Gotchas: [dcode-deepagents-code.md](dcode-deepagents-code.md).
- Correctness-critical/high-stakes → race-and-judge: Opus 5 + GPT-5.6-Sol max + Grok 4.6 xhigh implement independently → Fable 5 judges → GLM-5.3 max verifies. It fails closed unless candidates completed with independent verification and GLM returns `sound`.
- Architecture/migration/refactor → consult the explicitly pinned Fable 5 `fable-advisor` at the boundary.
- Long context → use the verified window table above. `lane-pick longcontext` starts with GLM-5.3 (1M), falls back to Grok 4.6 (500K), then the architect session. Never send >258.4K to subscription Codex or >500K to Grok.
- Read/explore → Haiku (built-in Explore).
- Lane `unavailable`/`timeout` → re-route to another lane, state plainly; never silent fallback to Claude.

## 5-part spec (every CLI delegation)

Objective · Files · Interfaces · Constraints · Verification command. A spec you cannot finish writing means the decision is not made yet; do not delegate ambiguity.

## Lane invocation (write spec to `mktemp`, never inline/fixed path — parallel lanes corrupt each other)

- **Visibility:** every vendor invocation runs through `lanes start <lane> -- <cmd>` (`~/.local/bin/lanes`): named tmux session pinned to cwd, durable log, completion channel, and recorded vendor exit code. `lanes wait <sess> 540`: 0 = vendor success, 142 = still running, other = failed. `lanes result <sess>` replays the recorded exit. Pi launches vendors directly this way. Claude Code may use wrappers, which must still launch through `lanes`.
- codex (GPT-5.6-Sol): `codex exec --ignore-user-config -m gpt-5.6-sol -c model_reasoning_effort=max -c model_context_window=272000 -c approval_policy="never" -s workspace-write --skip-git-repo-check -C "$(pwd)" -o "$FINAL" "$(cat "$SPEC")"` — the prompt is positional. Never use `- < "$SPEC"` under `lanes`; detached stdin hangs. `max` is the highest Omnicode-approved single-agent effort; never `ultra`.
- grok routine (Grok 4.6, 500K): `grok --prompt-file "$SPEC" -m grok-4.6 --reasoning-effort high --permission-mode acceptEdits --output-format plain --cwd "$(pwd)" --no-plan --max-turns 120 --no-memory --no-subagents --disable-web-search`. RJV alone uses `xhigh`. Never omit `-m` or use `bypassPermissions`.
- glm (GLM-5.3, 1M ctx, scoped z.ai env, read-only analysis): `glm --model opus -p "$(cat "$SPEC")"`
- dcode (DeepAgents Code / LangChain harness; ChatGPT subscription only): `cd <project root>` first, then `perl -e 'alarm shift; exec @ARGV' 660 env -u OPENAI_API_KEY -u OPENAI_BASE_URL LANGSMITH_TRACING=false dcode --no-mcp -M openai_codex:gpt-5.6-sol --model-params '{"reasoning": {"effort": "max", "summary": "auto"}}' -q --timeout 600 -n "$(cat "$SPEC")"`. `--no-mcp` is mandatory; only the `openai_codex` subscription engine is allowed.
- Portable timeout (macOS has no `timeout`/`gtimeout` without coreutils): `T=$(command -v gtimeout || command -v timeout || true); ${T:+$T 600} <cmd>`. Or `perl -e 'alarm shift; exec @ARGV' 600 <cmd>`.
- ⚠️ **stdin redirects do NOT survive `lanes start`** (2026-07-17: codex lane hung 35 min, empty log): `lanes start x -- codex exec … - < "$SPEC"` applies the redirect to `lanes start` itself, while codex inside tmux waits forever on a tty stdin. Through lanes, always pass prompts by flag/argument (`--prompt-file`, `-p "$(cat …)"`, positional arg) or wrap the whole redirect: `lanes start x -- bash -c 'codex exec … - < spec.txt'`. Empty lane log after minutes = stdin hang, not thinking.

## Structured report (every lane returns)

```
STATUS: complete | partial | timeout | unavailable
OBJECTIVE: [one line]
CHANGES: file — summary (from actual diff)
VERIFIED: <command you re-ran> — <actual output>
<LANE> SAID: [one-line summary, note disagreement with diff]
GAPS: … | none
```
"CLI said it works" is forbidden as evidence — re-run the verification command yourself.

## Race-and-judge (high-stakes only; ~4× tokens)

User-invocable via `/rjv`. Opus 5 (1M) + GPT-5.6-Sol max (272K) + Grok 4.6 xhigh (500K) implement the same five-part spec in isolated worktrees. Only complete, independently verified candidates reach the Fable 5 judge. The workflow normalizes the winning path from known candidate records; GLM-5.3 max then adversarially verifies. Apply is allowed only when `readyToApply: true`, followed by architect inspection and a fresh verification run.

**⚠️ Golden-fixture / benchmark isolation (validated 2026-07-09, parseNokPrice eval):** never co-locate the reference solution or the hidden test suite anywhere implementer lanes can read. With the reference + oracle sitting under `/tmp/.../reference` and `/hidden`, **2 of 3 autonomous CLI lanes (grok, agy) roamed the filesystem, found the reference, and submitted it verbatim** (diff-identical, including comments) — their self-reported 22/22 was fraudulent. codex + a direct GLM subagent wrote genuine code blind. After moving every copyable artifact out, grok+agy re-ran genuine and scored perfect. **Rule:** each lane gets a dir/worktree containing ONLY the spec + a public smoke test; trust NOTHING self-reported until you re-run the oracle yourself. **GPT-5.6-Sol note (2026-07-09):** Sol is specifically documented to fabricate eval results (reports tests as passing that it never fully ran) — these isolation + re-run-the-oracle rules are non-negotiable for the codex lane. **Verify by differential consensus** (N independent implementations + the oracle over a large adversarial input set) — stronger than a single cross-vendor prose review and resilient when a verifier endpoint is unavailable.

**Before invoking:** use a clean, committed baseline or a dedicated worktree. Never auto-stash or reset shared work. Lanes branch from HEAD, not the working tree. Keep hidden tests and reference solutions outside every lane-readable filesystem; use a real sandbox/container for leakage-sensitive benchmarks. If all lanes are unavailable, stop and diagnose the repo root and CLI health rather than weakening isolation.

## Commitment boundaries

Consult `fable-advisor` (explicit latest `fable` alias, 1M context; read-only, <300 words) before architecture/migration/API-shape/refactor decisions, after two failed attempts, and before declaring a multi-step deliverable done. Act on the verdict or surface disagreement.

## Invocation right-sizing & fallbacks

- Token order: direct **Bash** (one-shot lane call) < **Agent tool** (single lane, clean context) < **Workflow** (~7× — ONLY for ≥3 independent lanes).
- **Deep research:** route Grok 4.6 first, then GLM-5.3 and Codex as distinct angles through `lanes`, with URL+date citations or `WEB_UNAVAILABLE`. Do not add a Gemini lane.
- **Works under `glm` too:** when Anthropic limits burn, the GLM launcher can host compatible Claude Code surfaces; Codex and Grok remain external lanes. Note that an Opus alias under the GLM host is not a distinct Claude-family judge.
- **Cross-CLI context:** doctrine auto-carries via the shared brain; task state does not. Use the goal ledger or an explicit handoff artifact before switching CLIs/sessions. The Workflow tool is Claude-Code-compatible; Codex and Grok orchestrate lanes via shell commands.

## Cost discipline

- Architect emits judgment, not volume (no code blocks longer than an interface signature; fixing a lane's bug = corrected spec back to the lane, not hand-editing).
- Lean context (delegate explore to Haiku; keep only conclusions in architect context).
- Race-and-judge gated to high-stakes; routine = single lane.
- Cross-vendor verify uses **GLM-5.3** as an independent subscription-backed family. Fable remains the architecture commitment advisor when available.
- Architect model = runtime `/model` choice: `fable` (quality-max) → `opus` (efficient) → `opusplan` (budget).
- No mid-task model/effort switches (cache wipe).

## Auth hygiene (load-bearing — prevents surprise charges)

- codex uses ChatGPT subscription auth. `lanes` strips `OPENAI_API_KEY` and other provider keys before launch; always pass `--ignore-user-config -m gpt-5.6-sol` so personal MCP credentials are excluded and model selection is explicit.
- Gemini/Antigravity are not Omnicode lanes. Never route work there; image-specific Gemini credentials remain outside this system.
- grok via xAI OAuth (grok.com login).
- dcode uses only `openai_codex` = ChatGPT-subscription OAuth (LangChain's experimental `_ChatOpenAICodex`; **same quota pool as the codex lane** — parallel dcode+codex fan-outs drain one subscription). The wrapper never routes `xai`, `anthropic`, `openai`, or `openrouter` API-key providers, disables LangSmith tracing, and passes `--no-mcp`.
- glm via z.ai token (`~/.config/zai/token`); the `glm` launcher scopes `ANTHROPIC_BASE_URL` to its own process (never leaks to parent shell / settings.json).
- Sandboxes: codex `-s workspace-write` (never `--dangerously-bypass-approvals-and-sandbox`); grok `acceptEdits` for implementation and `plan` for review (never `bypassPermissions`). `lanes` strips common env credentials and GitHub access but is not filesystem-level secret isolation.

## Omnigent watch (2026-07-17)

Databricks open-sourced **Omnigent** (`omnigent-ai/omnigent`, Apache-2.0, alpha, ~6.8k★, launched 2026-06-15) — a meta-harness over Claude Code/Codex/Cursor/OpenCode/Hermes/Pi with subscription auth first-class and a Polly example agent doing cross-vendor race-and-review in parallel worktrees — a productized omnicode. Verdict (researched via lanes 2026-07-17): keep omnicode as the brain; re-evaluate omnigent ~Q4 2026 when out of alpha, as a candidate **ops layer** (durable session server, policy-as-config MCP proxy, sandbox fan-out, mobile/web UI) for the VPS/OpenClaw side — never as an architect-seat replacement (it drives Claude Code underneath). Field survey confirms the de facto power-user stack = ours (Claude Max architect + Codex volume + overflow subs); account load-balancers = ToS/ban risk, avoid.

## Status (2026-08-16)

- Active lanes: Codex (GPT-5.6-Sol max, 272K subscription context), Grok (Grok 4.6 high/xhigh, 500K), GLM (GLM-5.3 max, 1M), dcode (GPT-5.6-Sol max through `openai_codex`; same quota/family as Codex), Claude supervisors (Sonnet 5), Opus 5 racer, and Fable 5 advisor/judge. Gemini/Antigravity remain retired.
- Fallback router, durable vendor exit codes, quota groups, and the `uib` browser are live. Wrapper agents carry the fallback protocol; Codex prompts are positional under `lanes`.
- Reliability hardening: portable perl-alarm timeout in all wrapper agents; `worktree.baseRef='head'`; unique race diff directories; staged binary diff capture includes untracked files; `lanes` strips provider API keys and GitHub credentials by default; Codex ignores personal config/MCPs; graceful `unavailable`→re-route; all-unavailable message diagnoses non-git cwd / CLIs-down.
- **Validity (learned from parseNokPrice eval):** lanes will cheat if they can read the reference solution — isolate the reference + hidden tests from lane worktrees; trust NOTHING self-reported, re-run the oracle yourself; verify by differential consensus (N impls + oracle) so a down verify-CLI (z.ai GLM 529'd twice) doesn't block.
- Rollback: remove `~/.claude/agents/{fable-advisor,codex-implementer,grok-implementer,glm-longcontext,dcode-implementer}.md` plus `~/.claude/workflows/race-and-judge.mjs`, then restore the prior skill/config through git.
