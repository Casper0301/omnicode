# Herdr VPS Hybrid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run new Herdr coding-agent workloads on Casper's VPS while the Mac remains the thin UI client and a targeted watchdog removes sustained memory leaks.

**Architecture:** A local wrapper attaches to a named remote Herdr session. Repository-owned provisioners install version-matched, checksum-verified Linux runtimes plus a systemd user service and timer; an allowlisted one-way SSH sync transfers portable auth, memory, skills, and harness configuration. The server has no resource cap; the watchdog operates only inside the service cgroup and fails closed.

**Tech Stack:** Bash, Python 3 standard library, systemd user services, SSH/rsync, Herdr 0.8.2, vendor Linux x86_64 CLIs, unittest.

**Spec:** `docs/superpowers/specs/2026-08-20-herdr-vps-hybrid-design.md`

## Global Constraints

- Do not stop, restart, close, or modify the existing local Herdr session.
- Do not configure `MemoryMax`, `MemoryHigh`, `CPUQuota`, or an equivalent hard resource cap on the VPS.
- Never inspect, print, or commit credential contents. The user explicitly authorizes allowlisted file-backed auth transfer over SSH to this VPS, installed mode `0600`.
- Never kill a process outside the `herdr-dev.service` cgroup or the Herdr server main PID.
- Keep browser CDP endpoints on loopback; do not expose them publicly.
- Use the `user` account for remote development; do not move production services from `admin`.

---

### Task 1: Cgroup-scoped leak watchdog

**Files:**
- Create: `bin/herdr-vps-watchdog`
- Create: `tests/test_herdr_vps.py`

**Interfaces:**
- Consumes: Linux `/proc`, cgroup v2, `systemctl --user show herdr-dev.service`.
- Produces: `herdr-vps-watchdog` with `--dry-run`, injected test roots, JSON action logs, and exit status 0 for a healthy sample.

- [ ] **Step 1: Write failing tests**

Create fake proc/cgroup fixtures covering a healthy process, one high sample, three high growing samples, a process outside the cgroup, the protected main PID, and PID reuse with a changed start time.

- [ ] **Step 2: Verify tests fail**

Run: `python3 -m unittest tests.test_herdr_vps -v`

Expected: FAIL because `bin/herdr-vps-watchdog` does not exist.

- [ ] **Step 3: Implement the watchdog**

Use only the Python standard library. Read thresholds from `HERDR_WATCHDOG_*` variables, recursively enumerate `cgroup.procs`, key samples by PID plus `/proc/<pid>/stat` start time, and terminate only after the spec's repeated-sample conditions. Honor `HERDR_WATCHDOG_DRY_RUN=1` and injected `PROC_ROOT`, `CGROUP_ROOT`, `STATE_DIR`, `CONTROL_GROUP`, and `MAIN_PID` inputs.

- [ ] **Step 4: Verify tests pass**

Run: `python3 -m unittest tests.test_herdr_vps -v`

Expected: PASS for all isolation and sustained-growth cases.

- [ ] **Step 5: Commit**

Run: `git add bin/herdr-vps-watchdog tests/test_herdr_vps.py && git commit -m "feat: add Herdr VPS leak watchdog"`

### Task 2: Durable VPS provisioning and local attach wrapper

**Files:**
- Create: `bin/herdr-vps`
- Create: `scripts/provision-herdr-vps.sh`
- Create: `config/herdr-vps/config.toml`
- Create: `config/herdr-vps/herdr-dev.service`
- Create: `config/herdr-vps/herdr-vps-watchdog.service`
- Create: `config/herdr-vps/herdr-vps-watchdog.timer`
- Modify: `scripts/apply.sh`
- Modify: `scripts/pull.sh`
- Modify: `tests/test_herdr_vps.py`

**Interfaces:**
- Consumes: local `herdr`, `gh`, `ssh`, `scp`, SSH alias `caspers_vps`, and Task 1's watchdog.
- Produces: idempotent `provision-herdr-vps.sh` and local `herdr-vps` command.

- [ ] **Step 1: Add failing tests**

Assert that the wrapper uses `--remote caspers_vps --session dev`, the service runs `herdr --session dev server`, none of the unit files contain hard resource caps, and the provisioner requires a release digest before install.

- [ ] **Step 2: Verify tests fail**

Run: `python3 -m unittest tests.test_herdr_vps -v`

Expected: FAIL because the provisioning files do not exist.

- [ ] **Step 3: Implement provisioning**

Resolve the installed local Herdr version, obtain the matching Linux x86_64 release asset digest from GitHub, download on the VPS, verify with `sha256sum`, install under `/home/user/.local/bin`, copy config and units, enable linger, and start `herdr-dev.service` plus the watchdog timer. Do not copy secrets or install agent CLIs in this task.

- [ ] **Step 4: Install the local wrapper through repo sync**

Update `apply.sh` and `pull.sh` so `~/.local/bin/herdr-vps` remains repository-managed without touching unrelated live configuration.

- [ ] **Step 5: Verify tests and shell syntax**

Run: `python3 -m unittest tests.test_herdr_vps -v`

Run: `bash -n scripts/provision-herdr-vps.sh scripts/apply.sh scripts/pull.sh bin/herdr-vps`

Expected: all pass.

- [ ] **Step 6: Commit**

Run: `git add bin/herdr-vps scripts/provision-herdr-vps.sh config/herdr-vps scripts/apply.sh scripts/pull.sh tests/test_herdr_vps.py && git commit -m "feat: provision remote Herdr runtime"`

### Task 3: Full Linux CLI and authenticated harness sync

**Files:**
- Create: `scripts/provision-herdr-vps-clis.sh`
- Create: `scripts/sync-herdr-vps-harness.sh`
- Create: `config/herdr-vps/remote-profile.sh`
- Create: `tests/test_herdr_vps_harness.py`

**Interfaces:**
- Consumes: official vendor installers/releases, local CLI versions, allowlisted auth/config paths, SSH alias `caspers_vps`.
- Produces: idempotent Linux CLI installer and one-way harness/auth/memory/skills sync without token output.

- [ ] **Step 1: Write failing safety and parity tests**

Assert exact version pins for Claude Code 2.1.237, Codex 0.148.0, Pi 0.84.2, OMP 17.3.0, dcode 0.1.56, Grok 1.0.5, OpenCode 1.17.13, Hermes 0.20.4's immutable release commit, and the current pinned Cursor Linux artifact. Assert official digest verification for native assets, no `.env`/session DB/broker/MCP/cache paths, no `rsync --delete`, mode `0600` for auth destinations, and fail-closed symlink creation.

- [ ] **Step 2: Verify tests fail**

Run: `python3 -m unittest tests.test_herdr_vps_harness -v`

Expected: FAIL because the scripts and remote profile do not exist.

- [ ] **Step 3: Implement the Linux CLI installer**

Install under `/home/user/.local` only. Use vendor packages or checksum-verified official Linux x86_64 assets, persist `~/.local/bin` on PATH, and make no auth changes. A matching version is a no-op; a mismatched active executable fails with a clear replacement-required error instead of silently changing live tooling.

- [ ] **Step 4: Implement the curated harness sync**

Transfer only the spec's portable auth/config allowlist, durable memory, shared skills, Omnicode agents/config, and required wrappers. Auth files travel individually and are set to `0600`; public trees retain executable modes. Exclude every `.env`, cache, session/history database, runtime broker token, Mac binary, live Herdr state, and MCP repository. Recreate Linux-local memory and skill symlinks only when the destination is absent or already the expected symlink.

- [ ] **Step 5: Verify implementation**

Run: `python3 -m unittest tests.test_herdr_vps_harness -v`

Run: `bash -n scripts/provision-herdr-vps-clis.sh scripts/sync-herdr-vps-harness.sh`

Run: `shellcheck scripts/provision-herdr-vps-clis.sh scripts/sync-herdr-vps-harness.sh`

Expected: all pass with no token or secret output.

- [ ] **Step 6: Commit**

Run: `git add scripts/provision-herdr-vps-clis.sh scripts/sync-herdr-vps-harness.sh config/herdr-vps/remote-profile.sh tests/test_herdr_vps_harness.py docs/superpowers && git commit -m "feat: mirror authenticated harness to Herdr VPS"`

### Task 4: Provision and validate the remote pilot

**Files:**
- Modify remotely: `/home/user/.local/bin/herdr`
- Modify remotely: `/home/user/.local/bin/herdr-vps-watchdog`
- Modify remotely: `/home/user/.config/herdr/config.toml`
- Modify remotely: `/home/user/.config/systemd/user/herdr-dev.service`
- Modify remotely: `/home/user/.config/systemd/user/herdr-vps-watchdog.service`
- Modify remotely: `/home/user/.config/systemd/user/herdr-vps-watchdog.timer`
- Modify remotely: `/home/user/.local/bin/{claude,codex,pi,omp,dcode,grok,opencode,hermes,agent,glm}`
- Modify remotely: allowlisted auth/config, `/home/user/.ai-memory`, `/home/user/.claude/skills`, and harness symlinks

**Interfaces:**
- Consumes: Task 2 Herdr provisioner, Task 3 CLI/sync scripts, and the existing SSH route.
- Produces: persistent compatible remote Herdr server with active monitoring and the authenticated model harness.

- [ ] **Step 1: Run the provisioner**

Run: `scripts/provision-herdr-vps.sh`

Expected: version and digest verification succeed; both units become active.

- [ ] **Step 2: Verify absence of hard caps**

Run remote `systemctl --user show herdr-dev.service -p MemoryMax -p MemoryHigh -p CPUQuotaPerSecUSec`.

Expected: infinity for every property.

- [ ] **Step 3: Verify cgroup and watchdog isolation**

Run the watchdog with `HERDR_WATCHDOG_DRY_RUN=1`, inspect the unit control group, and verify the Herdr main PID is excluded from candidates.

- [ ] **Step 4: Install and sync the complete harness without exposing auth**

Run `scripts/provision-herdr-vps-clis.sh`, then `scripts/sync-herdr-vps-harness.sh`. Verify versions and portable auth with status-only commands that never print token values. Complete supported device/browser login flows for Claude Code, Cursor Agent, and OMP if their existing device state is unavailable remotely.

- [ ] **Step 5: Install and verify Herdr integrations**

Install integrations for every available remote CLI, including the custom dcode hook bridge, then run `herdr --session dev integration status`. Verify native session references and agent state transitions without prompting a real customer-facing or production action.

- [ ] **Step 6: Clone and validate an isolated pilot repository**

Verify GitHub CLI auth, clone `Casper0301/omnicode` into `/home/user/Projects/omnicode`, and run token-light probes through the configured model lanes. If any provider fails, record it as incomplete and continue validating the independent providers; never downgrade or silently substitute its configured model.

### Task 5: End-to-end verification and delivery

**Files:**
- Modify: `README.md`
- Modify: `bin/omnicode-doctor`

**Interfaces:**
- Consumes: provisioned VPS runtime.
- Produces: documented operator commands and ongoing health checks.

- [ ] **Step 1: Document the split workflow**

Add `herdr-vps` usage, local-versus-remote boundaries, watchdog policy, logs, and the rule that no existing local panes are auto-closed.

- [ ] **Step 2: Add token-free doctor checks**

Check the local wrapper, SSH reachability, remote Herdr version, service state, watchdog timer, infinity resource settings, and loopback-only browser policy without sending a model prompt.

- [ ] **Step 3: Run complete verification**

Run: `python3 -m unittest discover -s tests -v`

Run: `bash -n scripts/*.sh bin/herdr-vps`

Run: `omnicode-doctor --fast`

Run: `herdr-vps` in a TTY, confirm the remote workspace renders, then detach with `ctrl+b q`.

- [ ] **Step 4: Review and secret-scan**

Run the repository review workflow and `scripts/pull.sh`; verify the secret scan is clean and inspect the final diff.

- [ ] **Step 5: Commit and push**

Run `auth-doctor`, commit only the owned files on `main`, and push over SSH to `origin main`.
