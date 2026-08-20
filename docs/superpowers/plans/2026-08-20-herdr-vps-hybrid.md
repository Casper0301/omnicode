# Herdr VPS Hybrid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run new Herdr coding-agent workloads on Casper's VPS while the Mac remains the thin UI client and a targeted watchdog removes sustained memory leaks.

**Architecture:** A local wrapper attaches to a named remote Herdr session. A repository-owned provisioner installs a version-matched, checksum-verified Linux binary plus a systemd user service and timer. The server has no resource cap; the watchdog operates only inside the service cgroup and fails closed.

**Tech Stack:** Bash, Python 3 standard library, systemd user services, SSH, Herdr 0.8.2, unittest.

**Spec:** `docs/superpowers/specs/2026-08-20-herdr-vps-hybrid-design.md`

## Global Constraints

- Do not stop, restart, close, or modify the existing local Herdr session.
- Do not configure `MemoryMax`, `MemoryHigh`, `CPUQuota`, or an equivalent hard resource cap on the VPS.
- Never inspect, print, copy, or commit credential contents.
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

### Task 3: Provision and validate the remote pilot

**Files:**
- Modify remotely: `/home/user/.local/bin/herdr`
- Modify remotely: `/home/user/.local/bin/herdr-vps-watchdog`
- Modify remotely: `/home/user/.config/herdr/config.toml`
- Modify remotely: `/home/user/.config/systemd/user/herdr-dev.service`
- Modify remotely: `/home/user/.config/systemd/user/herdr-vps-watchdog.service`
- Modify remotely: `/home/user/.config/systemd/user/herdr-vps-watchdog.timer`

**Interfaces:**
- Consumes: Task 2 provisioner and the existing SSH route.
- Produces: persistent compatible remote Herdr server with active monitoring.

- [ ] **Step 1: Run the provisioner**

Run: `scripts/provision-herdr-vps.sh`

Expected: version and digest verification succeed; both units become active.

- [ ] **Step 2: Verify absence of hard caps**

Run remote `systemctl --user show herdr-dev.service -p MemoryMax -p MemoryHigh -p CPUQuotaPerSecUSec`.

Expected: infinity for every property.

- [ ] **Step 3: Verify cgroup and watchdog isolation**

Run the watchdog with `HERDR_WATCHDOG_DRY_RUN=1`, inspect the unit control group, and verify the Herdr main PID is excluded from candidates.

- [ ] **Step 4: Install and validate Codex without exposing auth**

Install the current Codex CLI for the `user` account, then run `codex login status`. Stop if the existing auth file is rejected; do not print or replace it.

- [ ] **Step 5: Create an isolated pilot repository**

Clone `Casper0301/omnicode` into `/home/user/Projects/omnicode` only if GitHub auth succeeds. Otherwise create `/home/user/Projects/herdr-pilot` with no customer or production data and validate a shell there.

### Task 4: End-to-end verification and delivery

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
