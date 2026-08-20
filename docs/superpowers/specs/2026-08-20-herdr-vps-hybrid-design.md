# Herdr VPS Hybrid Design

## Goal

Move new coding-agent execution from Casper's 16 GiB Mac to the existing VPS while keeping Ghostty and Herdr's interactive UI on the Mac. Preserve the current local Herdr session as a fallback and do not interrupt or migrate live panes in place.

## Current state

- The Mac runs Herdr 0.8.2 with seven workspaces and seventeen agent panes.
- The Herdr daemon is small; the pane workloads account for several GiB and substantial CPU during builds.
- The VPS is Ubuntu 24.04 x86_64 with eight vCPUs, 32 GiB RAM, and approximately 19 GiB available at assessment time.
- Herdr is not installed on the VPS. The SSH user has Codex auth state but no coding-agent CLI binaries.
- Existing production services run on the VPS, primarily under the `admin` account. Remote development will run under the less-privileged `user` account.

## Architecture

Ghostty runs the local Herdr 0.8.2 client and attaches with `herdr --remote caspers_vps --session dev`. The VPS runs a matching Herdr 0.8.2 headless server as a persistent systemd user service. Repositories, shells, agents, builds, tests, and remote worktrees live under `/home/user`; Mac-only browser, GUI, Apple-app, and local-file workflows stay in the existing local Herdr session.

The VPS service has no `MemoryMax`, `MemoryHigh`, or `CPUQuota`. All server-owned panes remain in the `herdr-dev.service` cgroup so a watchdog can inspect only that workload. The watchdog never scans or terminates processes outside the cgroup and never terminates the Herdr server PID.

## Leak watchdog

The watchdog samples the Herdr cgroup once per minute and stores only process IDs, process start times, RSS, and sanitized command names. A process is terminated only after three consecutive samples show at least 6 GiB RSS and at least 512 MiB growth. A pressure fallback activates only after three samples where system available memory is below 4 GiB, the Herdr cgroup exceeds 12 GiB aggregate RSS, and the chosen Herdr child has at least 2 GiB RSS plus at least 256 MiB growth.

Termination is SIGTERM followed by SIGKILL only if the exact PID/start-time identity remains alive after ten seconds. Every action is written as a JSON line to the systemd journal and `~/.local/state/herdr-watchdog/actions.jsonl`. Missing cgroup metadata, unreadable `/proc`, or ambiguous process identity fails closed without killing anything. The thresholds are environment-overridable, but the installed defaults above are the source of truth.

## Provisioning and parity

Provisioning downloads the Linux x86_64 asset matching the local Herdr version and verifies the SHA-256 digest published by the official GitHub release before installation. It installs the user service, watchdog, timer, and a minimal remote config. The remote config enables agent resume, pane history, external worktrees, and Kitty graphics without copying Mac-specific plugin commands.

The first pilot installs Codex only because usable Codex auth state already exists on the VPS. Claude, Pi, dcode, Grok, and other integrations are not declared migrated until their CLI, auth, hook, and resume behavior pass independently. Secrets are never copied by the provisioner.

## Repository and browser boundaries

Git is the synchronization boundary. Remote repositories are independent clones; bidirectional filesystem synchronization and SSHFS are out of scope. Browser previews remain in local Chrome and reach remote loopback ports through explicit SSH forwarding. Chrome DevTools endpoints remain bound to loopback and are never exposed through nginx or public HTTPS.

## Rollout and rollback

The current local session stays running. The first remote workspace is an isolated pilot under `/home/user/Projects`; no local pane is closed automatically. Rollback consists of detaching the Mac client and disabling the two new user units after enumerating the remote panes that would stop. Repository data remains recoverable through Git.

## Acceptance criteria

- Local and remote Herdr report version 0.8.2 and protocol compatibility.
- `herdr --remote caspers_vps --session dev` attaches from Ghostty.
- The remote server and its pane processes belong to `herdr-dev.service`.
- The systemd service has no CPU or memory cap.
- Watchdog tests prove sustained-growth gating, cgroup isolation, main-PID protection, and PID-reuse protection.
- The remote watchdog timer is active and a dry run reports healthy without killing a process.
- A remote pilot workspace can run a shell and Codex authentication probe.
- The existing local Herdr session and its seventeen panes remain untouched.
