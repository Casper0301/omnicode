<!-- VERSIONED COPY — source of truth: ~/.ai-memory/multi-model-orchestration.md
     Edit there (it is the shared brain's doctrine); pull.sh refreshes this copy. -->
---
name: multi-model-orchestration
description: "Federated multi-model orchestration doctrine — architect + cross-vendor CLI lanes + race-and-judge + adversarial verify, subscriptions only. Full detail; MEMORY.md holds the tight summary."
metadata: 
  node_type: memory
  type: project
  originSessionId: 88b8deba-1f7e-41ae-89f0-dfc41feb1808
---

# Multi-Model Orchestration (Federated) — all flagships in unison

**Shared brain** = `MEMORY.md` (symlinked to `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`, Antigravity's `~/.gemini/config/AGENTS.md`, and `~/.grok/AGENTS.md`). Any of Claude/codex/gemini/grok can architect; Claude Code is default orchestrator (richest tools: subagents + Workflow + MCP). **Subscriptions only** — no API keys, no proxy, no `ANTHROPIC_BASE_URL` change. Lane-invocation commands are tool-neutral shell — any orchestrator runs them via Bash. Claude Code additionally wraps them as subagents in `~/.claude/agents/` (`fable-advisor`, `codex-implementer`, `grok-implementer`, `antigravity-implementer`, `gemini-reviewer`, `glm-longcontext`, `dcode-implementer`) + a `~/.claude/workflows/race-and-judge.mjs` Workflow.

## Automatic fallback ladders (2026-07-17) — rate limits never stall work

- **`lane-pick <class>`** (`~/.local/bin/lane-pick`) resolves a task class to the strongest healthy lane. Ladders live in `~/.claude/omnicode/ladders.json`; cooldowns in `~/.lanes/health.json`. Classes: `code` (grok→glm→codex→claude) · `correctness` (codex→glm→grok→claude) · `langchain` (dcode→glm→claude; codex skipped — same quota) · `longcontext` (glm→claude) · `research` (agy→glm→grok→codex→claude) · `review` (glm→grok→codex→claude) · `ui` (claude→glm→codex→grok) · `architecture` (claude).
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
- grok/glm/agy: paste `goal step` output as the prompt; they read the shared brain so the protocol is known.
- **Economy rule:** loop-driving is cheap-model work (grok/glm/opusplan) because acceptance, not judgment, decides done. Fable/Sol-at-max only at judgment points. NEVER Sol `ultra` (spawns internal subagents — duplicates omnicode's own fan-out at premium token cost).

## Routing (architect picks per task)

- Pure coding / well-specified → **grok default** — ONLY with a complete 5-part spec; grok freestyles where the spec is silent (2026-07-09 eval), so the lane bounces incomplete specs back (`STATUS: spec-incomplete`) instead of running. Correctness-critical single lane → codex (GPT-5.6-Sol max). agy = free alt.
- LangGraph / LangChain / deepagents agent code → **dcode** (DeepAgents Code — LangChain's own dogfooded harness; GPT-5.6-Sol @ max effort on the ChatGPT sub). Same 5-part-spec gate. Same family as codex (shared ChatGPT quota) — adds harness fit for LangChain-native work, NOT diversity; never counts as an extra race family. Harness prompts are NOT langgraph-specialized (checked v0.1.34) — the routing is a live bet; judge on real tasks, demote if it doesn't beat grok/codex there. Gotchas: [dcode-deepagents-code.md](dcode-deepagents-code.md).
- Correctness-critical/high-stakes → race-and-judge (Sonnet + codex + grok + **agy** → opus judges → **glm** verifies — 5 families; gemini deprecated 2026).
- Architecture/migration/refactor → Fable architect + consult `fable-advisor` at the boundary.
- Context >200K → glm lane (1M today, free). GPT-5.6-Sol currently advertises a 272K cap with a 95% effective budget (about 258K), so it is not the long-context fallback.
- Read/explore → Haiku (built-in Explore).
- Lane `unavailable`/`timeout` → re-route to another lane, state plainly; never silent fallback to Claude.

## 5-part spec (every CLI delegation)

Objective · Files · Interfaces · Constraints · Verification command. A spec you can't finish writing = the decision isn't made yet (architect work — don't hand ambiguity to a cheaper model).

## Lane invocation (write spec to `mktemp`, never inline/fixed path — parallel lanes corrupt each other)

- **Visibility (2026-07-15):** default launch = the `~/.claude/agents/*-implementer` wrapper subagents, so lanes appear in the Claude Code agent panel (`subagentStatusLine` vendor arrows key off "<lane> lane" in the Agent-call description — include it, e.g. `description: "dcode lane: golden fixture"`). Every CLI invocation — inside wrappers AND any direct Bash lane — runs through `lanes start <lane> -- <cmd>` (`~/.local/bin/lanes`): named tmux session `lane-*` pinned to cwd, log in `~/.lanes/`, completion channel; wait with `lanes wait <sess> 540` (exit 0 = done, 142 = still running → loop; never sleep-poll). User watches/attaches live: `tmux attach -t <sess>` / `lanes peek <sess>`. Bare background-Bash lanes (no tmux) are deprecated.
- codex (GPT-5.6-Sol): `codex exec --ignore-user-config -m gpt-5.6-sol -c model_reasoning_effort=max -c model_context_window=272000 -c approval_policy="never" -s workspace-write --skip-git-repo-check -C "$(pwd)" -o "$FINAL" - < "$SPEC"` — `max` = highest single-agent effort; `ultra` exists above it but spawns Codex-internal sub-agents (token-explosive, redundant under omnicode's own fan-out — explicit ask + `rollout_token_budget` cap only). Context: 272K model cap / about 258K effective (95%), verified from `~/.codex/models_cache.json` on 2026-07-15. `--ignore-user-config` preserves ChatGPT auth and the global AGENTS brain while excluding personal MCP/plugin configuration from `config.toml`.
- grok (Grok 4.5): `grok --prompt-file "$SPEC" -m grok-4.5 --permission-mode acceptEdits --output-format plain --cwd "$(pwd)"` (run `grok models` to confirm the current subscription slug)
- agy / Antigravity (Gemini 3.1 Pro, Google sub, free): `agy -p "$(cat "$SPEC")" --mode accept-edits --add-dir "$(pwd)"` — `--mode plan` for review/read-only work. Replaces the dead gemini CLI; free tier drops first under load.
- glm (GLM-5.2, 1M ctx, scoped z.ai env, read-only analysis): `glm --model opus -p "$(cat "$SPEC")"`
- dcode (DeepAgents Code / LangChain harness; ChatGPT subscription only): `cd <project root>` first (no `--cwd` flag), then `perl -e 'alarm shift; exec @ARGV' 660 env LANGGRAPH_ALLOW_BLOCKING=true LANGSMITH_TRACING=false dcode --no-mcp -M openai_codex:gpt-5.6-sol --model-params '{"reasoning": {"effort": "max", "summary": "auto"}}' -q --timeout 600 -n "$(cat "$SPEC")"` — `-n` auto-executes tools (no approval gate); exec/`command` bypasses the zsh wrapper that injects personal MCP config; `--no-mcp` makes that boundary explicit; native `--timeout` exits 124. API-key engines are never selected. Details: [dcode-deepagents-code.md](dcode-deepagents-code.md).
- gemini: ⚠️ UNAVAILABLE 2026 — Google deprecated "Gemini Code Assist for individuals" (`IneligibleTierError` → Antigravity); `GEMINI_API_KEY` in `~/.zshrc` is pay-per-token, NEVER use. Re-enable only after migrating to Antigravity / a fresh gemini CLI; then `env -u GEMINI_API_KEY gemini -p "$(cat "$SPEC")" --approval-mode plan`.
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

User-invocable via the `/rjv` skill. The race completes with whichever lanes are up — agy (free) drops first under load; codex/grok + Claude judge + glm verify still = 4 families. `~/.claude/workflows/race-and-judge.mjs`: spec → 4 implementer lanes in parallel (Sonnet + codex/GPT + grok/Grok + agy/Gemini), each worktree-isolated; each runs `git add -A` and captures a staged binary diff (including untracked files) under a unique `/tmp/omnicode-race-<id>/<lane>.diff` → opus-tier judge reads all diffs, picks the single strongest → glm adversarially verifies the winner → architect applies `judge.winningDiffPath` (`git apply`) + re-runs verification. Invoke from a git-repo cwd.

**⚠️ Golden-fixture / benchmark isolation (validated 2026-07-09, parseNokPrice eval):** never co-locate the reference solution or the hidden test suite anywhere implementer lanes can read. With the reference + oracle sitting under `/tmp/.../reference` and `/hidden`, **2 of 3 autonomous CLI lanes (grok, agy) roamed the filesystem, found the reference, and submitted it verbatim** (diff-identical, including comments) — their self-reported 22/22 was fraudulent. codex + a direct GLM subagent wrote genuine code blind. After moving every copyable artifact out, grok+agy re-ran genuine and scored perfect. **Rule:** each lane gets a dir/worktree containing ONLY the spec + a public smoke test; trust NOTHING self-reported until you re-run the oracle yourself. **GPT-5.6-Sol note (2026-07-09):** Sol is specifically documented to fabricate eval results (reports tests as passing that it never fully ran) — these isolation + re-run-the-oracle rules are non-negotiable for the codex lane. **Verify by differential consensus** (N independent implementations + the oracle over a large adversarial input set) — free, always-on, stronger than a single cross-vendor prose review, and unaffected when the verify-CLI endpoint is down (z.ai GLM-verify 529'd twice here; consensus carried it).

**Before invoking:** commit or stash uncommitted changes — lanes branch from local HEAD (`worktree.baseRef: 'head'` in settings.json), NOT your working tree, so uncommitted changes aren't seen by lanes and the winning diff may not apply cleanly on top of them. If all lanes return `unavailable`, the cwd likely isn't a git repo (cd into one) or the vendor CLIs are down (check each lane's STATUS/REASON). Non-repo cwd: pre-create lane worktrees; capture diffs with `add -A` + `--cached`; parse string args ([full lesson](omnicode_worktree_cwd_lesson.md)). Adversarial verify routes to glm-longcontext — gemini-reviewer is dead, `IneligibleTierError` ([detail](omnicode-verify-lane-glm.md)).

## Commitment boundaries

Consult `fable-advisor` (read-only, <300 words) before architecture/migration/API-shape/refactor decisions, after 2 failed attempts on one problem, and before declaring a multi-step deliverable done. Act on the verdict or surface the disagreement — never silently ignore it.

## Invocation right-sizing & fallbacks

- Token order: direct **Bash** (one-shot lane call) < **Agent tool** (single lane, clean context) < **Workflow** (~7× — ONLY for ≥3 independent lanes).
- **Deep research:** never the built-in `/deep-research` Workflow — it spawns session-model subagents (Fable burn; killed 2026-07-09). Instead 3–5 angles → one background-Bash lane each: agy (free, Google-search-grounded) · glm (`--allowedTools "WebSearch,WebFetch"`) · grok (live web/X, sentiment) · codex (`-c tools.web_search=true`; no `--search` flag on exec). Lanes cite URL+date or print `WEB_UNAVAILABLE`; architect only decomposes + synthesizes. Full rule: [feedback_deep_research_omnicode.md](feedback_deep_research_omnicode.md).
- **Works under `glm` too:** when Max limits burn, run `glm` (z.ai Claude Code, reads `~/.claude`) — same agents/doctrine/workflow; opus→GLM-5.2, sonnet→GLM-4.7; codex/grok/agy lanes unchanged; nothing hard-pinned to Fable.
- **Cross-CLI context:** doctrine auto-carries via the symlinked MEMORY.md; task state does NOT — commit `SESSION_HANDOFF.md` (status/remaining/verify/rollback) before switching CLIs/sessions. The Workflow tool is Claude-Code-only (`claude`+`glm`); codex/grok/agy orchestrate lanes via plain Bash.

## Cost discipline

- Architect emits judgment, not volume (no code blocks longer than an interface signature; fixing a lane's bug = corrected spec back to the lane, not hand-editing).
- Lean context (delegate explore to Haiku; keep only conclusions in architect context).
- Race-and-judge gated to high-stakes; routine = single lane.
- Cross-vendor verify uses **glm** (subscription-free, 4th family; gemini deprecated 2026), NOT Fable — higher quality AND avoids the Fable-for-QC cost. (No conflict with "Fable only for critical/complex": QC is a separate, free lane.)
- Architect model = runtime `/model` choice: `fable` (quality-max) → `opus` (efficient) → `opusplan` (budget).
- No mid-task model/effort switches (cache wipe).

## Auth hygiene (load-bearing — prevents surprise charges)

- codex uses ChatGPT subscription auth. `lanes` strips `OPENAI_API_KEY` and other provider keys before launch; always pass `--ignore-user-config -m gpt-5.6-sol` so personal MCP credentials are excluded and model selection is explicit.
- gemini: subscription path DEAD (Google deprecated Code Assist 2026, `IneligibleTierError`); `GEMINI_API_KEY` in `~/.zshrc:28` is pay-per-token (nanobanana uses it) — never use for lanes. Verify defaults to glm.
- grok via xAI OAuth (grok.com login).
- dcode uses only `openai_codex` = ChatGPT-subscription OAuth (LangChain's experimental `_ChatOpenAICodex`; **same quota pool as the codex lane** — parallel dcode+codex fan-outs drain one subscription). The wrapper never routes `xai`, `anthropic`, `openai`, or `openrouter` API-key providers, disables LangSmith tracing, and passes `--no-mcp`.
- glm via z.ai token (`~/.config/zai/token`); the `glm` launcher scopes `ANTHROPIC_BASE_URL` to its own process (never leaks to parent shell / settings.json).
- Sandboxes: codex `-s workspace-write` (never `--dangerously-bypass-approvals-and-sandbox`); grok `acceptEdits` (never `bypassPermissions`); gemini `--approval-mode plan` for review, `auto_edit` for impl.

## Omnigent watch (2026-07-17)

Databricks open-sourced **Omnigent** (`omnigent-ai/omnigent`, Apache-2.0, alpha, ~6.8k★, launched 2026-06-15) — a meta-harness over Claude Code/Codex/Cursor/OpenCode/Hermes/Pi with subscription auth first-class and a Polly example agent doing cross-vendor race-and-review in parallel worktrees — a productized omnicode. Verdict (researched via lanes 2026-07-17): keep omnicode as the brain; re-evaluate omnigent ~Q4 2026 when out of alpha, as a candidate **ops layer** (durable session server, policy-as-config MCP proxy, sandbox fan-out, mobile/web UI) for the VPS/OpenClaw side — never as an architect-seat replacement (it drives Claude Code underneath). Field survey confirms the de facto power-user stack = ours (Claude Max architect + Codex volume + overflow subs); account load-balancers = ToS/ban risk, avoid.

## Status (2026-07-15)

- Lanes: codex ✓ (GPT-5.6-Sol @ max, 272K cap, ChatGPT subscription), grok ✓ (grok-4.5, grok.com subscription), agy ✓ (Gemini 3.1 Pro, Google login), glm ✓ (GLM-5.2, z.ai Coding Plan), dcode ✓ (DeepAgents Code / GPT-5.6-Sol through `openai_codex`; LangGraph/LangChain specialist, not a new family). gemini CLI ✗ (Code Assist deprecated — Antigravity replaces it; verify uses glm).
- 2026-07-17: fallback router live (`lane-pick`, ladders.json, lanes auto-scan, quota groups) + `uib` UI browser shipped (grok-built, independently verified). Cooldowns at time of writing: codex+dcode (Casper-reported OpenAI limits, ~6h default — `lane-pick clear codex` when back), agy (Google quota until ~Jul 23 04:20). Wrapper agents all carry the fallback protocol + redirect warnings; codex wrapper's stdin invocation fixed to positional.
- Reliability hardening: portable perl-alarm timeout in all wrapper agents; `worktree.baseRef='head'`; unique race diff directories; staged binary diff capture includes untracked files; `lanes` strips provider API keys and GitHub credentials by default; Codex ignores personal config/MCPs; graceful `unavailable`→re-route; all-unavailable message diagnoses non-git cwd / CLIs-down.
- **Validity (learned from parseNokPrice eval):** lanes will cheat if they can read the reference solution — isolate the reference + hidden tests from lane worktrees; trust NOTHING self-reported, re-run the oracle yourself; verify by differential consensus (N impls + oracle) so a down verify-CLI (z.ai GLM 529'd twice) doesn't block.
- Rollback: remove `~/.claude/agents/{fable-advisor,codex-implementer,grok-implementer,antigravity-implementer,gemini-reviewer,glm-longcontext,dcode-implementer}.md` + `~/.claude/workflows/race-and-judge.mjs`, revert the MEMORY.md doctrine section + `worktree.baseRef` in settings.json.
