#!/usr/bin/env bash
# Curated one-way copy of portable model auth, memory, skills, and Omnicode state.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="caspers_vps"

fail() {
  echo "sync-herdr-vps-harness: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

for command in file find ssh rsync stat; do
  require_command "$command"
done

required_local_paths=(
  "$HOME/.ai-memory/MEMORY.md"
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$REPO/config/ladders.json"
  "$REPO/config/models.json"
  "$REPO/agents"
  "$REPO/workflows/race-and-judge.mjs"
  "$REPO/bin/lanes"
  "$REPO/bin/lane-pick"
  "$REPO/bin/goal"
  "$REPO/bin/omnicode-doctor"
)
for required_path in "${required_local_paths[@]}"; do
  [[ -e "$required_path" ]] || fail "required allowlisted source not found: $required_path"
done

file_mode() {
  local source="$1"
  local mode=""
  if mode="$(stat -f '%Lp' "$source" 2>/dev/null)"; then
    printf '%s\n' "$mode"
  elif mode="$(stat -c '%a' "$source" 2>/dev/null)"; then
    printf '%s\n' "$mode"
  else
    fail "cannot determine mode for portable auth source: $source"
  fi
}

# A transfer must never briefly materialize a token with permissive mode. -a
# preserves these verified source modes; the remote finalizer enforces 0600 too.
AUTH_SOURCES=(
  "$HOME/.codex/auth.json"
  "$HOME/.pi/agent/auth.json"
  "$HOME/.deepagents/.state/chatgpt-auth.json"
  "$HOME/.grok/auth.json"
  "$HOME/.local/share/opencode/auth.json"
  "$HOME/.config/gh/hosts.yml"
  "$HOME/.config/zai/token"
)
for auth_source in "${AUTH_SOURCES[@]}"; do
  if [[ -f "$auth_source" ]]; then
    [[ ! -L "$auth_source" && "$(file_mode "$auth_source")" == "600" ]] ||
      fail "portable auth source must be mode 0600 and not a symlink: $auth_source"
  fi
done

reject_mac_binaries() {
  local source="$1"
  local candidate=""
  local description=""
  [[ -d "$source" ]] || return 0
  while IFS= read -r -d '' candidate; do
    description="$(file -b "$candidate")"
    case "$description" in
      *Mach-O*) fail "Mac binary in portable tree: $candidate" ;;
    esac
  done < <(
    find -L "$source" \
      \( -name node_modules -o -name .venv -o -name venv -o \
         -name .cache -o -name cache -o -name caches -o \
         -name sessions -o -name history -o -name .git \) -prune -o \
      -type f \( -perm -111 -o -name '*.dylib' -o -name '*.so' -o -name '*.node' \) \
      -print0
  )
}

for portable_tree in \
  "$HOME/.ai-memory" \
  "$HOME/.claude/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.claude/agents" \
  "$HOME/.cursor/rules" \
  "$HOME/.cursor/skills-cursor"; do
  reject_mac_binaries "$portable_tree"
done

# Validate the fixed identity before creating any remote directory or transferring data.
if ! ssh "$SSH_TARGET" bash -s <<'REMOTE_PREFLIGHT'
set -euo pipefail
expected_home="/home/user"
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "$expected_home" ]]
[[ "$(uname -s)" == "Linux" ]]
[[ "$(uname -m)" == "x86_64" ]]
mkdir -p \
  "$expected_home/.ai-memory" \
  "$expected_home/.claude/skills" \
  "$expected_home/.claude/bin" \
  "$expected_home/.claude/agents" \
  "$expected_home/.claude/omnicode" \
  "$expected_home/.claude/workflows" \
  "$expected_home/.codex/skills" \
  "$expected_home/.cursor/rules" \
  "$expected_home/.cursor/skills-cursor" \
  "$expected_home/.agents" \
  "$expected_home/.grok" \
  "$expected_home/.pi/agent" \
  "$expected_home/.deepagents/.state" \
  "$expected_home/.deepagents/agent" \
  "$expected_home/.local/share/opencode" \
  "$expected_home/.local/bin" \
  "$expected_home/.config/opencode" \
  "$expected_home/.config/zai" \
  "$expected_home/.config/gh" \
  "$expected_home/.hermes"
chmod 0700 \
  "$expected_home/.codex" \
  "$expected_home/.pi/agent" \
  "$expected_home/.deepagents/.state" \
  "$expected_home/.grok" \
  "$expected_home/.local/share/opencode" \
  "$expected_home/.config/zai" \
  "$expected_home/.config/gh"
REMOTE_PREFLIGHT
then
  fail "remote identity/platform preflight failed"
fi

# These patterns apply only inside the explicitly approved durable/skill trees.
# They keep live state and platform payloads out while retaining public scripts.
TREE_RSYNC_ARGS=(
  -aL
  --exclude=.env
  '--exclude=.env.*'
  --exclude=.DS_Store
  '--exclude=*.db'
  '--exclude=*.db-*'
  '--exclude=*.sqlite'
  '--exclude=*.sqlite-*'
  '--exclude=*.sqlite3'
  '--exclude=*.sqlite3-*'
  '--exclude=*.dylib'
  --exclude=node_modules/
  --exclude=.venv/
  --exclude=venv/
  --exclude=__pycache__/
  --exclude=.cache/
  --exclude=cache/
  --exclude=caches/
  --exclude=sessions/
  --exclude=session/
  --exclude=history/
  --exclude=logs/
  --exclude=.git/
  --exclude=.mcp/
  --exclude=mcp/
  --exclude=MCP/
  '--exclude=mcp-*/'
  '--exclude=*-mcp/'
  --exclude=mcp-repositories/
  --exclude=mcp-servers/
  --exclude=mcp_servers/
  --exclude=optional-mcps/
)

sync_public_tree() {
  local source="$1"
  local destination="$2"
  if [[ -d "$source" ]]; then
    rsync "${TREE_RSYNC_ARGS[@]}" "$source/" "$SSH_TARGET:$destination/"
  fi
}

sync_public_file() {
  local source="$1"
  local destination="$2"
  if [[ -f "$source" ]]; then
    rsync -a "$source" "$SSH_TARGET:$destination"
  fi
}

sync_executable() {
  local source="$1"
  local destination="$2"
  if [[ -f "$source" ]]; then
    rsync -a "$source" "$SSH_TARGET:$destination"
  fi
}

sync_auth() {
  local label="$1"
  local source="$2"
  local destination="$3"
  if [[ -f "$source" ]]; then
    rsync -a "$source" "$SSH_TARGET:$destination"
    printf 'SYNCED %s auth\n' "$label"
  else
    printf 'INCOMPLETE %s auth: local portable auth not found\n' "$label"
  fi
}

# Durable public trees. -L intentionally materializes only these approved roots;
# their Mac-absolute plugin-cache symlinks would otherwise be broken on Linux.
sync_public_tree "$HOME/.ai-memory" "/home/user/.ai-memory"
sync_public_tree "$HOME/.claude/skills" "/home/user/.claude/skills"
sync_public_tree "$HOME/.codex/skills" "/home/user/.codex/skills"
sync_public_tree "$HOME/.claude/agents" "/home/user/.claude/agents"
sync_public_tree "$HOME/.cursor/rules" "/home/user/.cursor/rules"
sync_public_tree "$HOME/.cursor/skills-cursor" "/home/user/.cursor/skills-cursor"

# Portable, non-secret provider configuration.
sync_public_file "$HOME/.pi/agent/settings.json" "/home/user/.pi/agent/settings.json"
sync_public_file "$HOME/.deepagents/config.toml" "/home/user/.deepagents/config.toml"
sync_public_file "$HOME/.deepagents/agent/AGENTS.md" "/home/user/.deepagents/agent/AGENTS.md"
sync_public_file "$HOME/.grok/config.toml" "/home/user/.grok/config.toml"
sync_public_file "$HOME/.config/opencode/tui.jsonc" "/home/user/.config/opencode/tui.jsonc"
sync_public_file "$HOME/.hermes/SOUL.md" "/home/user/.hermes/SOUL.md"
sync_public_file "$HOME/.hermes/SOUL.persona.md" "/home/user/.hermes/SOUL.persona.md"

# Explicit portable auth allowlist. No provider .env, generic key pool, broker,
# transcript, database, cache, or device-bound credential is considered here.
sync_auth codex "$HOME/.codex/auth.json" "/home/user/.codex/auth.json"
sync_auth pi "$HOME/.pi/agent/auth.json" "/home/user/.pi/agent/auth.json"
sync_auth dcode "$HOME/.deepagents/.state/chatgpt-auth.json" "/home/user/.deepagents/.state/chatgpt-auth.json"
sync_auth grok "$HOME/.grok/auth.json" "/home/user/.grok/auth.json"
sync_auth opencode "$HOME/.local/share/opencode/auth.json" "/home/user/.local/share/opencode/auth.json"
sync_auth github "$HOME/.config/gh/hosts.yml" "/home/user/.config/gh/hosts.yml"
sync_auth zai "$HOME/.config/zai/token" "/home/user/.config/zai/token"

# Omnicode's owned Linux-compatible layer. Do not run apply.sh remotely: it
# contains launchd and other Mac-only integration.
sync_public_file "$REPO/config/ladders.json" "/home/user/.claude/omnicode/ladders.json"
sync_public_file "$REPO/config/models.json" "/home/user/.claude/omnicode/models.json"
sync_public_tree "$REPO/agents" "/home/user/.claude/agents"
sync_public_file "$REPO/workflows/race-and-judge.mjs" "/home/user/.claude/workflows/race-and-judge.mjs"
sync_executable "$REPO/bin/lanes" "/home/user/.local/bin/lanes"
sync_executable "$REPO/bin/lane-pick" "/home/user/.local/bin/lane-pick"
sync_executable "$REPO/bin/goal" "/home/user/.local/bin/goal"
sync_executable "$REPO/bin/omnicode-doctor" "/home/user/.local/bin/omnicode-doctor"

# GLM is a text wrapper plus an individually allowlisted token.
if [[ -f "$HOME/.local/bin/glm" ]]; then
  sync_executable "$HOME/.local/bin/glm" "/home/user/.local/bin/glm"
else
  echo "INCOMPLETE glm wrapper: local allowlisted wrapper not found"
fi

# Keep the custom dcode credential/MCP/socket guards, changing only the native
# executable location from the Mac uv-tool layout to the pinned Linux venv.
if [[ -f "$HOME/.claude/bin/dcode-launcher" ]]; then
  require_command grep
  require_command mktemp
  require_command sed
  dcode_real_lines="$(grep -c '^real=' "$HOME/.claude/bin/dcode-launcher" || true)"
  [[ "$dcode_real_lines" == "1" ]] ||
    fail "dcode launcher must contain exactly one real= assignment"
  [[ "$(sed -n '1p' "$HOME/.claude/bin/dcode-launcher")" == '#!/bin/zsh' ]] ||
    fail "dcode launcher has an unexpected interpreter"
  portable_dcode_launcher="$(mktemp "${TMPDIR:-/tmp}/herdr-dcode-launcher.XXXXXX")"
  trap 'rm -f -- "$portable_dcode_launcher"' EXIT
  # HOME and command_name must expand on the VPS.
  # shellcheck disable=SC2016
  sed 's|^real=.*$|real="$HOME/.local/share/herdr-clis/dcode-0.1.56/bin/$command_name"|' \
    "$HOME/.claude/bin/dcode-launcher" > "$portable_dcode_launcher"
  chmod 0755 "$portable_dcode_launcher"
  sync_executable "$portable_dcode_launcher" "/home/user/.claude/bin/dcode-launcher"
else
  echo "INCOMPLETE dcode bridge: local allowlisted launcher not found"
fi

ssh "$SSH_TARGET" bash -s <<'REMOTE_FINALIZE'
set -euo pipefail
expected_home="/home/user"
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "$expected_home" ]]
[[ "$(uname -s)" == "Linux" ]]
[[ "$(uname -m)" == "x86_64" ]]

for auth_file in \
  "$expected_home/.codex/auth.json" \
  "$expected_home/.pi/agent/auth.json" \
  "$expected_home/.deepagents/.state/chatgpt-auth.json" \
  "$expected_home/.grok/auth.json" \
  "$expected_home/.local/share/opencode/auth.json" \
  "$expected_home/.config/gh/hosts.yml" \
  "$expected_home/.config/zai/token"; do
  if [[ -f "$auth_file" ]]; then
    chmod 0600 "$auth_file"
  fi
done

for executable in \
  "$expected_home/.local/bin/lanes" \
  "$expected_home/.local/bin/lane-pick" \
  "$expected_home/.local/bin/goal" \
  "$expected_home/.local/bin/omnicode-doctor" \
  "$expected_home/.local/bin/glm"; do
  if [[ -f "$executable" ]]; then
    chmod 0755 "$executable"
  fi
done

[[ -f "$expected_home/.ai-memory/MEMORY.md" ]] || {
  echo "sync-herdr-vps-harness(remote): durable memory target is missing" >&2
  exit 1
}
[[ -d "$expected_home/.claude/skills" ]] || {
  echo "sync-herdr-vps-harness(remote): shared skills target is missing" >&2
  exit 1
}

ensure_link() {
  local link_path="$1"
  local target="$2"
  local resolved=""
  local resolved_target=""

  mkdir -p "$(dirname "$link_path")"
  if [[ -L "$link_path" ]]; then
    resolved="$(realpath "$link_path" 2>/dev/null || true)"
    resolved_target="$(realpath "$target" 2>/dev/null || true)"
    [[ -n "$resolved" && "$resolved" == "$resolved_target" ]] || {
      echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
      return 1
    }
    return
  fi
  if [[ -e "$link_path" ]]; then
    echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
    return 1
  fi
  ln -s "$target" "$link_path"
}

memory_target="$expected_home/.ai-memory/MEMORY.md"
ensure_link "$expected_home/.claude/CLAUDE.md" "$memory_target"
ensure_link "$expected_home/.codex/AGENTS.md" "$memory_target"
ensure_link "$expected_home/.cursor/AGENTS.md" "$memory_target"
ensure_link "$expected_home/.grok/AGENTS.md" "$memory_target"
ensure_link "$expected_home/.agents/AGENTS.md" "$memory_target"

skills_target="$expected_home/.claude/skills"
ensure_link "$expected_home/.agents/skills" "$skills_target"
ensure_link "$expected_home/.cursor/skills" "$skills_target"
ensure_link "$expected_home/.grok/skills" "$skills_target"

install_dcode_link() {
  local command_name="$1"
  local link_path="$expected_home/.local/bin/$command_name"
  local launcher="$expected_home/.claude/bin/dcode-launcher"
  local native="$expected_home/.local/share/herdr-clis/dcode-0.1.56/bin/$command_name"
  local current=""

  if [[ -L "$link_path" ]]; then
    current="$(readlink "$link_path")"
    [[ "$current" == "$launcher" || "$current" == "$native" ]] || {
      echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
      return 1
    }
  elif [[ -e "$link_path" ]]; then
    echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
    return 1
  fi
  ln -sfn "$launcher" "$link_path"
}

dcode_launcher="$expected_home/.claude/bin/dcode-launcher"
dcode_native="$expected_home/.local/share/herdr-clis/dcode-0.1.56/bin"
if [[ -f "$dcode_launcher" && -x /bin/zsh && -x "$dcode_native/dcode" &&
      -x "$dcode_native/deepagents-code" ]]; then
  chmod 0755 "$dcode_launcher"
  install_dcode_link dcode
  install_dcode_link deepagents-code
  if ! dcode_version="$("$expected_home/.local/bin/dcode" --version </dev/null 2>&1)" ||
    ! printf '%s\n' "$dcode_version" | grep -Eq '(^|[^0-9A-Za-z])0\.1\.56([^0-9A-Za-z]|$)'; then
    echo "sync-herdr-vps-harness(remote): dcode bridge does not report 0.1.56" >&2
    exit 1
  fi
  echo "READY dcode bridge 0.1.56"
else
  echo "INCOMPLETE dcode bridge: launcher, /bin/zsh, or pinned Linux venv is missing"
fi
REMOTE_FINALIZE

echo "Harness sync complete; missing auth/device logins remain explicitly INCOMPLETE above."
