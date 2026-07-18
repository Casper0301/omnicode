omnicode-doctor — 2026-07-18 13:01 — host Caspers-MacBook-Pro

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
[PASS] agy installed (1.1.3) — quota state only visible on use
[PASS] glm launcher + z.ai token present
[PASS] dcode installed + openai_codex auth stored

== fallback router (lane-pick + ladders) ==
[PASS] lane-pick executable
[PASS] ladders.json valid JSON
[PASS] quota group openai contains codex+dcode
[PASS] class code -> grok
[PASS] class correctness -> codex
[PASS] class langchain -> dcode
[PASS] class longcontext -> glm
[PASS] class research -> glm
[PASS] class review -> glm
[PASS] class ui -> claude
[PASS] class architecture -> claude

== lanes runner (tmux + auto-scan integration) ==
[PASS] lanes executable
[PASS] lanes carries the rate-limit auto-scan hook
[PASS] ~/.lanes writable
[PASS] lanes round-trip (start->wait->log) works

== uib browser (UI verification loop) ==
[PASS] uib shim + implementation present
[PASS] playwright installed in ~/.uib
[PASS] uib full round-trip (open->shot->stop) works, offline-safe data: URL

== shared brain + doctrine coherence ==
[PASS] brain file exists (/Users/casperschive/.claude/projects/-Users-casperschive-Projects/memory/MEMORY.md)
[PASS] brain link OK: /Users/casperschive/.codex/AGENTS.md
[PASS] brain link OK: /Users/casperschive/.gemini/GEMINI.md
[PASS] brain link OK: /Users/casperschive/.grok/AGENTS.md
[PASS] all vendor CLIs read the SAME brain
[PASS] doctrine carries fallback + uib sections
[PASS] shared brain mentions lane-pick (lanes will discover the router)

== lane wrapper agents ==
[PASS] agent fable-advisor present
[PASS] agent codex-implementer present
[PASS] agent grok-implementer present
[PASS] agent antigravity-implementer present
[PASS] agent gemini-reviewer present
[PASS] agent glm-longcontext present
[PASS] agent dcode-implementer present
[PASS] codex-implementer carries fallback protocol
[PASS] grok-implementer carries fallback protocol
[PASS] antigravity-implementer carries fallback protocol
[PASS] glm-longcontext carries fallback protocol
[PASS] dcode-implementer carries fallback protocol
[PASS] codex-implementer stdin bug absent

== skills, MCP, workflows ==
[PASS] race-and-judge workflow present
[PASS] rjv skill present
[PASS] agent-harnesses MCP configured

== state hygiene ==
[PASS] health.json valid
agy      COOLDOWN until Thu 04:19 — Google free-tier quota (Individual quota reached, observed 2026-07-17 09:19)
[PASS] ~/.lanes size OK (13MB)
[PASS] no stale lane sessions

== LIVE end-to-end probe (burns a little quota) ==
[PASS] live prompt through grok lane returned correctly

== summary ==
PASS=58 WARN=0 FAIL=0
