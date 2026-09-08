# Omnicode project instructions

This repository owns these project instructions; Claude/Gemini entry files import this source. Use the shared global preferences already in context. If absent and the local `~/.ai-memory/MEMORY.md` exists, read it once; keep personal memory out of this repository.

## Scope and canonical sources

- This repository versions shared lane orchestration, wrappers, RJV workflows, and their tests.
- `config/models.json` owns configured model/role policy; `config/ladders.json` owns fallback and quota groups.
- `skill/SKILL.md` is the operational interface; `skills/rjv/SKILL.md` owns the race workflow's user-facing guidance.
- Doctrine under `doctrine/` is generated from the external memory source. Edit the owning source when authorized, then refresh; do not make this copy authoritative.
- `STATUS.md` is a dated snapshot, not current runtime health.

## Local checks

- Review the changed script/module and matching tests before choosing validation.
- Router tests: `python3 tests/test_lane_pick.py` (used by the doctor).
- Workflow tests: `node --test tests/test_race_and_judge_workflow.mjs`.
- Additional Python tests live under `tests/`; run the relevant file/module for changed VPS/browser behavior.
- `omnicode-doctor --fast` checks installed integration behavior and skips slower probes; it is not a pure static lint.
- `--live` consumes model quota; `--record` writes runtime health history. Use those flags intentionally.

## Boundaries

- Preserve subscription authentication and the configured provider allowlist; routine instruction edits do not authorize model/account changes.
- Only task-relevant source, diffs, tests, and logs go to configured providers; credentials, customer data, and unrelated personal material remain excluded.
- Environment filtering is not filesystem isolation. Do not pass `.env` or credential files to lanes.
- Preserve isolated race workspaces, review/artifact binding, and the real exit status of delegated tools.
- Use goal checks only for actual goal-ledger work; ordinary repository tasks need their own relevant verification.

## Applying changes

- `scripts/pull.sh` copies live installation → repository with a secret-scan gate; it can overwrite repository files.
- `scripts/apply.sh` copies repository → live installation; it is a deployment/configuration mutation, not a test.
- Choose the correct direction based on the authorized source change; preserve unrelated live/repository edits.
- Verify installed behavior after an authorized apply. No Cloudflare website deploy belongs to this tooling repository.
- Exact installation, monitoring, and sync usage is in `README.md`.

## Maintenance

- Update this file when the relevant command, architecture, or boundary changes. Keep long procedures in the referenced docs or owning shared skill.
- Record dated findings in shared session/evidence notes; promote only validated lessons to the owning project, skill, or global memory.
