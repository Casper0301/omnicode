---
name: rjv
description: "Race-Judge-Verify for genuinely hard/high-stakes work. Runs the Omnicode race: Claude Opus 5 + GPT-5.6-Sol max + Grok 4.6 xhigh implement independently, Claude Fable 5 judges, and GLM-5.3 max verifies. Triggers on 'RJV', 'race-judge-verify', or 'race and judge'."
---

# RJV — Race-Judge-Verify

Use RJV only when a wrong result is expensive: correctness-critical logic, migrations, security-sensitive changes, large refactors, or production hotfixes. Routine work uses one lane: Grok 4.6 high for well-specified code, GPT-5.6-Sol max for correctness.

## Workflow

1. Confirm the task is genuinely high-stakes.
2. Start from a clean committed baseline or dedicated worktree. Never auto-stash/reset shared work.
3. Write the five-part spec: Objective · Files · Interfaces · Constraints · trusted Verification command.
4. Run:

```text
Workflow({ scriptPath: '~/.claude/workflows/race-and-judge.mjs', args: { spec: '<five-part spec>', verifyCmd: '<trusted proof command>' } })
```

5. Three isolated implementations race:
   - Claude Opus 5, 1M context, adaptive reasoning
   - GPT-5.6-Sol, max reasoning, 272K subscription context (258.4K effective)
   - Grok 4.6, xhigh reasoning, 500K context
6. Claude Fable 5 (1M context) judges only complete, independently verified candidates.
7. GLM-5.3 (1M context, max reasoning) adversarially verifies the normalized winner.
8. Apply nothing unless `readyToApply: true`. The architect then applies the known diff, inspects it, and re-runs the verification command.

## Fail closed

- Partial, timed-out, unavailable, or unverified lanes never reach the judge.
- A missing/failed verifier means no apply instruction.
- Never use Codex `ultra`; it would add internal fan-out inside RJV.
- No Gemini or Antigravity lane.
- Hidden tests/reference solutions must live outside every lane-readable filesystem; leakage-sensitive benchmarks require a real sandbox/container.
- Lane claims are not evidence. The architect owns final verification, commit, push, and release.
