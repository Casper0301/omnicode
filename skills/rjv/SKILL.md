---
name: rjv
description: "Race-Judge-Verify for genuinely hard/high-stakes work. Runs the Omnicode race: Claude Fable 5.1 + GPT-6 Astra max + Grok 4.6 xhigh implement independently, Claude Fable 5.1 judges, and GLM-5.3 max verifies. Triggers on 'RJV', 'race-judge-verify', or 'race and judge'."
---

# RJV — Race-Judge-Verify

Use RJV only when a wrong result is expensive: correctness-critical logic, migrations, security-sensitive changes, large refactors, or production hotfixes. Routine work uses one lane: Grok 4.6 high for well-specified code, GPT-6 Astra max for correctness.

## Workflow

1. Confirm the task is genuinely high-stakes.
2. Start from a clean committed baseline or dedicated worktree. Never auto-stash/reset shared work.
3. Write the five-part spec: Objective · Files · Interfaces · Constraints · trusted Verification command.
4. Create a fresh caller-generated `raceRunId` for this invocation (1–80 letters, numbers, `.`, `_`, or `-`; never reuse one), then run:

```text
Workflow({ scriptPath: '~/.claude/workflows/race-and-judge.mjs', args: { spec: '<five-part spec>', verifyCmd: '<trusted proof command>', raceRunId: '<unique-safe-id>' } })
```

5. Three isolated implementations race:
   - Claude Fable 5.1, 1M context, adaptive reasoning
   - GPT-6 Astra, max reasoning, 272K configured context (258.4K effective)
   - Grok 4.6, xhigh reasoning, 500K context
6. Claude Fable 5.1 (1M context) judges each complete `completeArtifactText` and binds its choice to the workflow-computed `artifactSha256` and byte count.
7. GLM-5.3 (1M context, max reasoning) adversarially verifies that same digest-bound artifact and re-runs the trusted verification command.
8. Apply nothing unless `readyToApply: true` and `apply.command` is present. From the clean target repo, run exactly `apply.command`; never reconstruct or manually apply a diff. Inspect the staged result and the helper's verification output.

Implementers do not see each other's work. The spec is the only shared task state during the race. The returned `completeArtifactText`, its workflow-computed digest, and the guarded helper are the apply authority—not model-reported filesystem state.

## Fail closed

- Partial, timed-out, unavailable, unverified, or empty-diff lanes never reach the judge.
- A missing/failed verifier, or `verifyCmdPassed` not true, means no apply instruction.
- Never use Codex `ultra`; it would add internal fan-out inside RJV.
- No Gemini or Antigravity lane.
- Hidden tests/reference solutions must live outside every lane-readable filesystem; leakage-sensitive benchmarks require a real sandbox/container.
- Lane claims are not evidence. The architect owns final verification, commit, push, and release.
