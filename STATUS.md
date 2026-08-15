omnicode-doctor — 2026-08-16 01:03 — host Caspers-MacBook-Pro

== core binaries ==
[PASS] tmux on PATH
[PASS] node on PATH
[PASS] python3 on PATH
[PASS] npx on PATH
[PASS] uvx on PATH
[PASS] gh on PATH
[PASS] git on PATH
[PASS] claude on PATH

== lane CLIs + subscription auth (token-free probes) ==
[PASS] codex installed + ChatGPT auth OK
[PASS] grok installed + xAI auth OK
[PASS] glm launcher + z.ai token present
[PASS] dcode installed + openai_codex auth stored

== fallback router (lane-pick + ladders) ==
[PASS] lane-pick executable
[PASS] ladders.json valid JSON
[PASS] quota group openai contains codex+dcode
[PASS] models.json matches the latest model/context/effort policy
[PASS] class code -> grok
[PASS] class correctness -> codex
[PASS] class langchain -> dcode
[PASS] class longcontext -> glm
[PASS] class research -> grok
[PASS] class review -> grok
[PASS] class ui -> claude
[PASS] class architecture -> claude

== lanes runner (tmux + auto-scan integration) ==
[PASS] lanes executable
[PASS] lanes carries the rate-limit auto-scan hook
[PASS] ~/.lanes writable
[PASS] lanes success round-trip (start->wait->log) works
[PASS] lanes propagates and persists vendor failure exit codes

== uib browser (UI verification loop) ==
[PASS] uib shim + implementation present
[PASS] playwright installed in ~/.uib
[PASS] uib full round-trip (open->shot->stop) works, offline-safe data: URL

== shared brain + doctrine coherence ==
[PASS] brain file exists (/Users/casperschive/.claude/projects/-Users-casperschive-Projects/memory/MEMORY.md)
[PASS] brain link OK: /Users/casperschive/.codex/AGENTS.md
[PASS] brain link OK: /Users/casperschive/.grok/AGENTS.md
[PASS] all vendor CLIs read the SAME brain
[PASS] doctrine carries fallback + uib sections
[PASS] shared brain mentions lane-pick (lanes will discover the router)

== lane wrapper agents ==
[PASS] agent fable-advisor present
[PASS] agent codex-implementer present
[PASS] agent grok-implementer present
[PASS] agent glm-longcontext present
[PASS] agent dcode-implementer present
[PASS] codex-implementer carries fallback protocol
[PASS] grok-implementer carries fallback protocol
[PASS] glm-longcontext carries fallback protocol
[PASS] dcode-implementer carries fallback protocol
[PASS] retired Gemini/Antigravity wrappers absent
[PASS] codex-implementer stdin bug absent
[PASS] Grok wrapper pins 4.6 with high reasoning
[PASS] Fable advisor is pinned to the latest Fable alias

== skills, MCP, workflows ==
[PASS] race-and-judge workflow present
[PASS] race-and-judge Codex prompt is positional
[PASS] race-and-judge has no Gemini/Antigravity lane
[PASS] RJV uses Grok 4.6 xhigh and a Fable judge
[PASS] omnicode skill bans destructive fallback cleanup
[PASS] shared agent skills root safely points to Claude skills
[PASS] omnicode skill symlinked into shared + Claude roots
[PASS] rjv skill present
[PASS] rjv skill matches the current model policy
[PASS] authenticated Grok catalog defaults to 4.6
[PASS] Grok local defaults are pinned to 4.6
[PASS] GLM launcher maps the 1M flagship and max reasoning budget
[PASS] authenticated Codex catalog confirms GPT-5.6-Sol / 272K / max
[PASS] agent-harnesses MCP configured

== goal ledger (durable cross-harness goals) ==
[PASS] goal CLI executable
[PASS] goal round-trip (new->loop->DONE on green acceptance) works
[PASS] all goal files parse
       open goals: 3

== repo self-tests ==
[PASS] omnicode unit tests pass

== state hygiene ==
[PASS] health.json valid
[PASS] ~/.lanes size OK (46MB)
[PASS] no stale lane sessions

== LIVE end-to-end probe (burns a little quota) ==
[PASS] live prompt through grok lane returned correctly

== summary ==
PASS=73 WARN=0 FAIL=0
