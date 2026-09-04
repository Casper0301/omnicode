#!/usr/bin/env bash
# Curated one-way copy of portable model auth, memory, skills, and Omnicode state.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="caspers_vps"
REMOTE_AUTH_STAGE=""
LOCAL_DCODE_STAGE=""

fail() {
  echo "sync-herdr-vps-harness: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

for command in file find mktemp realpath rsync ssh stat; do
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
  "$REPO/bin/apply-race-artifact"
  "$HOME/.local/bin/glm"
  "$HOME/.claude/bin/dcode-launcher"
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

# Portable auth is staged under mode 0700 remotely, then atomically installed.
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

path_is_within() {
  local candidate="$1"
  local root="$2"
  [[ "$candidate" == "$root" || "$candidate" == "$root/"* ]]
}

APPROVED_LINK_ROOTS=()
local_home_root="$(realpath "$HOME")" || fail "cannot resolve local home"
memory_root="$(realpath "$HOME/.ai-memory")" ||
  fail "cannot resolve durable memory source"
case "$memory_root" in
  "$local_home_root/.claude/projects/"*/memory) ;;
  *) fail "durable memory target is outside the approved project memory root" ;;
esac
APPROVED_LINK_ROOTS+=("$memory_root")
for approved_source in \
  "$HOME/.claude/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.claude/spec-kit-source" \
  "$HOME/.claude/skill-sources" \
  "$REPO/skill"; do
  if [[ -e "$approved_source" ]]; then
    approved_root="$(realpath "$approved_source")" ||
      fail "cannot resolve approved symlink root: $approved_source"
    APPROVED_LINK_ROOTS+=("$approved_root")
  fi
done

validate_portable_file() {
  local source="$1"
  local description=""
  [[ -f "$source" && ! -L "$source" ]] ||
    fail "portable file must be regular and not a symlink: $source"
  if ! description="$(file -b "$source")"; then
    fail "cannot identify portable file: $source"
  fi
  case "$description" in
    *Mach-O*) fail "Mac binary in portable file: $source" ;;
  esac
}

validate_portable_tree() {
  local source="$1"
  local inventory=""
  local candidate=""
  local resolved=""
  local approved_root=""
  local approved=0
  local description=""
  local validation_error=""
  [[ -d "$source" ]] || return 0
  inventory="$(mktemp "${TMPDIR:-/tmp}/herdr-portable-tree.XXXXXX")" ||
    fail "cannot create local validation inventory"
  if ! find -L "$source" \
    \( -name .env -o -name '.env.*' -o -name .DS_Store -o \
       -name '*.db' -o -name '*.db-*' -o -name '*.sqlite' -o \
       -name '*.sqlite-*' -o -name '*.sqlite3' -o -name '*.sqlite3-*' -o \
       -name '*.dylib' -o -name node_modules -o -name .venv -o -name venv -o \
       -name __pycache__ -o -name .cache -o -name cache -o -name caches -o \
       -name sessions -o -name session -o -name history -o -name logs -o \
       -name .git -o -name .mcp -o -name mcp -o -name MCP -o \
       -name 'mcp-*' -o -name '*-mcp' -o \
       -name mcp-repositories -o -name mcp-servers -o -name mcp_servers -o \
       -name optional-mcps \) -prune -o -print0 > "$inventory"; then
    rm -f -- "$inventory"
    fail "failed to enumerate portable tree: $source"
  fi
  while IFS= read -r -d '' candidate; do
    if [[ -L "$candidate" ]]; then
      if [[ ! -e "$candidate" ]]; then
        validation_error="broken symlink in portable tree: $candidate"
        break
      fi
      if ! resolved="$(realpath "$candidate")"; then
        validation_error="cannot resolve symlink in portable tree: $candidate"
        break
      fi
      approved=0
      for approved_root in "${APPROVED_LINK_ROOTS[@]}"; do
        if path_is_within "$resolved" "$approved_root"; then
          approved=1
          break
        fi
      done
      if [[ "$approved" != "1" ]]; then
        validation_error="unapproved symlink target in portable tree: $candidate"
        break
      fi
    fi
    if [[ -f "$candidate" ]]; then
      if ! description="$(file -b "$candidate")"; then
        validation_error="cannot identify portable file: $candidate"
        break
      fi
      case "$description" in
        *Mach-O*)
          validation_error="Mac binary in portable tree: $candidate"
          break
          ;;
      esac
    fi
  done < "$inventory"
  rm -f -- "$inventory"
  [[ -z "$validation_error" ]] || fail "$validation_error"
}

for portable_tree in \
  "$HOME/.ai-memory" \
  "$HOME/.claude/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.claude/agents" \
  "$HOME/.cursor/rules" \
  "$HOME/.cursor/skills-cursor" \
  "$REPO/agents"; do
  validate_portable_tree "$portable_tree"
done

PORTABLE_FILES=(
  "$HOME/.pi/agent/settings.json"
  "$HOME/.deepagents/config.toml"
  "$HOME/.deepagents/agent/AGENTS.md"
  "$HOME/.grok/config.toml"
  "$HOME/.config/opencode/tui.jsonc"
  "$HOME/.hermes/SOUL.md"
  "$HOME/.hermes/SOUL.persona.md"
  "$REPO/config/ladders.json"
  "$REPO/config/models.json"
  "$REPO/workflows/race-and-judge.mjs"
  "$REPO/bin/lanes"
  "$REPO/bin/lane-pick"
  "$REPO/bin/goal"
  "$REPO/bin/omnicode-doctor"
  "$REPO/bin/apply-race-artifact"
  "$HOME/.local/bin/glm"
  "$HOME/.claude/bin/dcode-launcher"
)
PORTABLE_FILES+=("${AUTH_SOURCES[@]}")
for portable_file in "${PORTABLE_FILES[@]}"; do
  if [[ -e "$portable_file" || -L "$portable_file" ]]; then
    validate_portable_file "$portable_file"
  fi
done

cleanup_remote_auth_stage() {
  if [[ -n "$REMOTE_AUTH_STAGE" ]]; then
    ssh "$SSH_TARGET" bash -s -- "$REMOTE_AUTH_STAGE" <<'REMOTE_AUTH_CLEANUP' >/dev/null 2>&1 || true
set -euo pipefail
stage="$1"
[[ "$stage" =~ ^/home/user/\.cache/herdr-auth-stage\.[A-Za-z0-9]+$ ]]
rm -rf -- "$stage"
REMOTE_AUTH_CLEANUP
  fi
}

cleanup_sync() {
  local status=$?
  if [[ -n "$LOCAL_DCODE_STAGE" ]]; then
    rm -f -- "$LOCAL_DCODE_STAGE"
  fi
  cleanup_remote_auth_stage
  return "$status"
}

# The remote audit is read-only until every managed path and final link passes.
if ! REMOTE_AUTH_STAGE="$(ssh "$SSH_TARGET" bash -s <<'REMOTE_PREFLIGHT'
set -euo pipefail
expected_home="/home/user"
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "$expected_home" ]]
[[ "$(uname -s)" == "Linux" ]]
[[ "$(uname -m)" == "x86_64" ]]
command -v python3 >/dev/null 2>&1
command -v find >/dev/null 2>&1
command -v mktemp >/dev/null 2>&1
zsh_path="${HERDR_TEST_ZSH_PATH:-/usr/bin/zsh}"
[[ -x "$zsh_path" ]] || {
  echo "sync-herdr-vps-harness(remote): required /usr/bin/zsh is missing" >&2
  exit 1
}

canonical_path() {
  python3 - "$1" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
}
canonical_home="$(canonical_path "$expected_home")"

assert_under_home() {
  local path="$1"
  local resolved=""
  [[ "$path" == "$expected_home" || "$path" == "$expected_home/"* ]] || {
    echo "sync-herdr-vps-harness(remote): managed path escapes home: $path" >&2
    return 1
  }
  resolved="$(canonical_path "$path")"
  [[ "$resolved" == "$canonical_home" || "$resolved" == "$canonical_home/"* ]] || {
    echo "sync-herdr-vps-harness(remote): canonical path escapes home: $path" >&2
    return 1
  }
}

assert_safe_parent() {
  local path="$1"
  local relative="${path#"$expected_home"/}"
  local current="$expected_home"
  local component=""
  local index=0
  local last=0
  local -a components=()
  assert_under_home "$path"
  [[ ! -L "$expected_home" && -d "$expected_home" ]] || return 1
  IFS='/' read -r -a components <<< "$relative"
  last=$((${#components[@]} - 1))
  while (( index < last )); do
    component="${components[index]}"
    current="$current/$component"
    [[ ! -L "$current" ]] || {
      echo "sync-herdr-vps-harness(remote): symlinked path component: $current" >&2
      return 1
    }
    [[ ! -e "$current" || -d "$current" ]] || return 1
    ((index += 1))
  done
}

assert_directory_destination() {
  local path="$1"
  assert_safe_parent "$path"
  [[ ! -L "$path" ]] || return 1
  [[ ! -e "$path" || -d "$path" ]] || return 1
  assert_under_home "$path"
}

assert_regular_destination() {
  local path="$1"
  assert_safe_parent "$path"
  if [[ -e "$path" || -L "$path" ]]; then
    [[ -f "$path" && ! -L "$path" ]] || {
      echo "sync-herdr-vps-harness(remote): auth or managed file is not regular: $path" >&2
      return 1
    }
  fi
}

assert_link_destination() {
  local link_path="$1"
  local target="$2"
  local alternate="${3:-}"
  local actual=""
  local wanted=""
  local alternate_resolved=""
  assert_safe_parent "$link_path"
  assert_under_home "$target"
  wanted="$(canonical_path "$target")"
  if [[ -n "$alternate" ]]; then
    assert_under_home "$alternate"
    alternate_resolved="$(canonical_path "$alternate")"
  fi
  if [[ -L "$link_path" ]]; then
    actual="$(canonical_path "$link_path")"
    [[ "$actual" == "$wanted" || ( -n "$alternate_resolved" && "$actual" == "$alternate_resolved" ) ]] || {
      echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
      return 1
    }
  elif [[ -e "$link_path" ]]; then
    echo "sync-herdr-vps-harness(remote): refusing to replace unrelated path: $link_path" >&2
    return 1
  fi
}

managed_directories=(
  "$expected_home/.cache"
  "$expected_home/.ai-memory"
  "$expected_home/.claude/skills"
  "$expected_home/.claude/bin"
  "$expected_home/.claude/agents"
  "$expected_home/.claude/omnicode"
  "$expected_home/.claude/workflows"
  "$expected_home/.codex/skills"
  "$expected_home/.cursor/rules"
  "$expected_home/.cursor/skills-cursor"
  "$expected_home/.agents"
  "$expected_home/.grok"
  "$expected_home/.pi/agent"
  "$expected_home/.deepagents/.state"
  "$expected_home/.deepagents/agent"
  "$expected_home/.local/share/opencode"
  "$expected_home/.local/bin"
  "$expected_home/.config/opencode"
  "$expected_home/.config/zai"
  "$expected_home/.config/gh"
  "$expected_home/.hermes"
)
for directory in "${managed_directories[@]}"; do
  assert_directory_destination "$directory"
done

tree_destinations=(
  "$expected_home/.ai-memory"
  "$expected_home/.claude/skills"
  "$expected_home/.codex/skills"
  "$expected_home/.claude/agents"
  "$expected_home/.cursor/rules"
  "$expected_home/.cursor/skills-cursor"
)
for directory in "${tree_destinations[@]}"; do
  if [[ -d "$directory" ]]; then
    symlink="$(find "$directory" -type l -print -quit)" || exit 1
    [[ -z "$symlink" ]] || {
      echo "sync-herdr-vps-harness(remote): symlink inside managed destination: $symlink" >&2
      exit 1
    }
  fi
done

managed_files=(
  "$expected_home/.ai-memory/MEMORY.md"
  "$expected_home/.pi/agent/settings.json"
  "$expected_home/.deepagents/config.toml"
  "$expected_home/.deepagents/agent/AGENTS.md"
  "$expected_home/.grok/config.toml"
  "$expected_home/.config/opencode/tui.jsonc"
  "$expected_home/.hermes/SOUL.md"
  "$expected_home/.hermes/SOUL.persona.md"
  "$expected_home/.codex/auth.json"
  "$expected_home/.pi/agent/auth.json"
  "$expected_home/.deepagents/.state/chatgpt-auth.json"
  "$expected_home/.grok/auth.json"
  "$expected_home/.local/share/opencode/auth.json"
  "$expected_home/.config/gh/hosts.yml"
  "$expected_home/.config/zai/token"
  "$expected_home/.claude/omnicode/ladders.json"
  "$expected_home/.claude/omnicode/models.json"
  "$expected_home/.claude/workflows/race-and-judge.mjs"
  "$expected_home/.local/bin/lanes"
  "$expected_home/.local/bin/lane-pick"
  "$expected_home/.local/bin/goal"
  "$expected_home/.local/bin/omnicode-doctor"
  "$expected_home/.local/bin/apply-race-artifact"
  "$expected_home/.local/bin/glm"
  "$expected_home/.claude/bin/dcode-launcher"
)
for managed_file in "${managed_files[@]}"; do
  assert_regular_destination "$managed_file"
done

memory_target="$expected_home/.ai-memory/MEMORY.md"
for link_path in \
  "$expected_home/.claude/CLAUDE.md" \
  "$expected_home/.codex/AGENTS.md" \
  "$expected_home/.cursor/AGENTS.md" \
  "$expected_home/.grok/AGENTS.md" \
  "$expected_home/.agents/AGENTS.md"; do
  assert_link_destination "$link_path" "$memory_target"
done
skills_target="$expected_home/.claude/skills"
for link_path in \
  "$expected_home/.agents/skills" \
  "$expected_home/.cursor/skills" \
  "$expected_home/.grok/skills"; do
  assert_link_destination "$link_path" "$skills_target"
done
dcode_launcher="$expected_home/.claude/bin/dcode-launcher"
for command_name in dcode deepagents-code; do
  assert_link_destination \
    "$expected_home/.local/bin/$command_name" \
    "$dcode_launcher" \
    "$expected_home/.local/share/herdr-clis/dcode-0.1.56/bin/$command_name"
done

# Only now may the remote filesystem change.
umask 077
for directory in "${managed_directories[@]}"; do
  mkdir -p "$directory"
  [[ -d "$directory" && ! -L "$directory" ]]
  assert_under_home "$directory"
done
chmod 0700 \
  "$expected_home/.codex" \
  "$expected_home/.pi/agent" \
  "$expected_home/.deepagents/.state" \
  "$expected_home/.grok" \
  "$expected_home/.local/share/opencode" \
  "$expected_home/.config/zai" \
  "$expected_home/.config/gh"

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}
for auth_file in \
  "$expected_home/.codex/auth.json" \
  "$expected_home/.pi/agent/auth.json" \
  "$expected_home/.deepagents/.state/chatgpt-auth.json" \
  "$expected_home/.grok/auth.json" \
  "$expected_home/.local/share/opencode/auth.json" \
  "$expected_home/.config/gh/hosts.yml" \
  "$expected_home/.config/zai/token"; do
  if [[ -e "$auth_file" ]]; then
    [[ -f "$auth_file" && ! -L "$auth_file" ]]
    chmod 0600 "$auth_file"
    [[ "$(file_mode "$auth_file")" == "600" ]]
  fi
done
auth_stage="$(mktemp -d "$expected_home/.cache/herdr-auth-stage.XXXXXX")"
chmod 0700 "$auth_stage"
[[ "$(file_mode "$auth_stage")" == "700" ]]
printf '%s\n' "$auth_stage"
REMOTE_PREFLIGHT
)"; then
  fail "remote identity/platform preflight failed"
fi
[[ "$REMOTE_AUTH_STAGE" =~ ^/home/user/\.cache/herdr-auth-stage\.[A-Za-z0-9]+$ ]] || {
  REMOTE_AUTH_STAGE=""
  fail "remote host returned an unsafe auth staging path"
}
trap cleanup_sync EXIT

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
  if [[ -f "$source" ]]; then
    rsync -a "$source" "$SSH_TARGET:$REMOTE_AUTH_STAGE/$label"
    printf 'SYNCED %s auth\n' "$label"
  else
    printf 'INCOMPLETE %s auth: local portable auth not found\n' "$label"
  fi
}

# Credentials go only to the private staging directory, then each is installed
# through a same-filesystem temporary file and verified immediately.
sync_auth codex "$HOME/.codex/auth.json"
sync_auth pi "$HOME/.pi/agent/auth.json"
sync_auth dcode "$HOME/.deepagents/.state/chatgpt-auth.json"
sync_auth grok "$HOME/.grok/auth.json"
sync_auth opencode "$HOME/.local/share/opencode/auth.json"
sync_auth github "$HOME/.config/gh/hosts.yml"
sync_auth zai "$HOME/.config/zai/token"

ssh "$SSH_TARGET" bash -s -- "$REMOTE_AUTH_STAGE" <<'REMOTE_AUTH_INSTALL'
set -euo pipefail
expected_home="/home/user"
stage="$1"
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "$expected_home" ]]
[[ "$stage" == "$expected_home/.cache/herdr-auth-stage."* ]]
[[ -d "$stage" && ! -L "$stage" ]]
umask 077

canonical_path() {
  python3 - "$1" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
}
canonical_home="$(canonical_path "$expected_home")"
file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}
stage_resolved="$(canonical_path "$stage")"
[[ "$stage_resolved" == "$canonical_home/.cache/herdr-auth-stage."* ]]
[[ "$(file_mode "$stage")" == "700" ]]
assert_safe_auth_destination() {
  local destination="$1"
  local parent="${destination%/*}"
  local resolved_parent=""
  [[ "$destination" == "$expected_home/"* ]]
  resolved_parent="$(canonical_path "$parent")"
  [[ "$resolved_parent" == "$canonical_home" || "$resolved_parent" == "$canonical_home/"* ]]
  [[ -d "$parent" && ! -L "$parent" ]]
  if [[ -e "$destination" || -L "$destination" ]]; then
    [[ -f "$destination" && ! -L "$destination" ]]
  fi
}
install_auth() {
  local label="$1"
  local destination="$2"
  local staged="$stage/$label"
  local temporary=""
  if [[ ! -e "$staged" ]]; then
    return 0
  fi
  [[ -f "$staged" && ! -L "$staged" && "$(file_mode "$staged")" == "600" ]]
  assert_safe_auth_destination "$destination"
  temporary="$(mktemp "${destination%/*}/.herdr-auth.XXXXXX")"
  install -m 0600 "$staged" "$temporary"
  [[ -f "$temporary" && ! -L "$temporary" && "$(file_mode "$temporary")" == "600" ]]
  assert_safe_auth_destination "$destination"
  mv -f -- "$temporary" "$destination"
  [[ -f "$destination" && ! -L "$destination" && "$(file_mode "$destination")" == "600" ]]
}

install_auth codex "$expected_home/.codex/auth.json"
install_auth pi "$expected_home/.pi/agent/auth.json"
install_auth dcode "$expected_home/.deepagents/.state/chatgpt-auth.json"
install_auth grok "$expected_home/.grok/auth.json"
install_auth opencode "$expected_home/.local/share/opencode/auth.json"
install_auth github "$expected_home/.config/gh/hosts.yml"
install_auth zai "$expected_home/.config/zai/token"
rm -rf -- "$stage"
REMOTE_AUTH_INSTALL
REMOTE_AUTH_STAGE=""

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
sync_executable "$REPO/bin/apply-race-artifact" "/home/user/.local/bin/apply-race-artifact"

# GLM is a required text wrapper plus an individually allowlisted token.
sync_executable "$HOME/.local/bin/glm" "/home/user/.local/bin/glm"

# Keep the custom dcode credential/MCP/socket guards, changing only the native
# executable location from the Mac uv-tool layout to the pinned Linux venv.
require_command grep
require_command sed
dcode_real_lines="$(grep -c '^real=' "$HOME/.claude/bin/dcode-launcher" || true)"
[[ "$dcode_real_lines" == "1" ]] ||
  fail "dcode launcher must contain exactly one real= assignment"
[[ "$(sed -n '1p' "$HOME/.claude/bin/dcode-launcher")" == '#!/bin/zsh' ]] ||
  fail "dcode launcher has an unexpected interpreter"
LOCAL_DCODE_STAGE="$(mktemp "${TMPDIR:-/tmp}/herdr-dcode-launcher.XXXXXX")"
# HOME and command_name must expand on the VPS.
# shellcheck disable=SC2016
sed 's|^real=.*$|real="$HOME/.local/share/herdr-clis/dcode-0.1.56/bin/$command_name"|' \
  "$HOME/.claude/bin/dcode-launcher" > "$LOCAL_DCODE_STAGE"
chmod 0755 "$LOCAL_DCODE_STAGE"
validate_portable_file "$LOCAL_DCODE_STAGE"
sync_executable "$LOCAL_DCODE_STAGE" "/home/user/.claude/bin/dcode-launcher"
rm -f -- "$LOCAL_DCODE_STAGE"
LOCAL_DCODE_STAGE=""

ssh "$SSH_TARGET" bash -s <<'REMOTE_FINALIZE'
set -euo pipefail
expected_home="/home/user"
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "$expected_home" ]]
[[ "$(uname -s)" == "Linux" ]]
[[ "$(uname -m)" == "x86_64" ]]
zsh_path="${HERDR_TEST_ZSH_PATH:-/usr/bin/zsh}"
[[ -x "$zsh_path" ]]
PATH="$expected_home/.local/bin:$expected_home/.grok/bin:$expected_home/.hermes/bin:$PATH"
export PATH

canonical_path() {
  python3 - "$1" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
}
canonical_home="$(canonical_path "$expected_home")"

assert_under_home() {
  local path="$1"
  local resolved=""
  [[ "$path" == "$expected_home" || "$path" == "$expected_home/"* ]]
  resolved="$(canonical_path "$path")"
  [[ "$resolved" == "$canonical_home" || "$resolved" == "$canonical_home/"* ]]
}

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}

for auth_file in \
  "$expected_home/.codex/auth.json" \
  "$expected_home/.pi/agent/auth.json" \
  "$expected_home/.deepagents/.state/chatgpt-auth.json" \
  "$expected_home/.grok/auth.json" \
  "$expected_home/.local/share/opencode/auth.json" \
  "$expected_home/.config/gh/hosts.yml" \
  "$expected_home/.config/zai/token"; do
  if [[ -e "$auth_file" || -L "$auth_file" ]]; then
    [[ -f "$auth_file" && ! -L "$auth_file" && "$(file_mode "$auth_file")" == "600" ]]
  fi
done

for executable in \
  "$expected_home/.local/bin/lanes" \
  "$expected_home/.local/bin/lane-pick" \
  "$expected_home/.local/bin/goal" \
  "$expected_home/.local/bin/omnicode-doctor" \
  "$expected_home/.local/bin/apply-race-artifact" \
  "$expected_home/.local/bin/glm"; do
  if [[ -e "$executable" || -L "$executable" ]]; then
    [[ -f "$executable" && ! -L "$executable" ]]
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

  local parent="${link_path%/*}"
  [[ -d "$parent" && ! -L "$parent" ]]
  assert_under_home "$link_path"
  assert_under_home "$target"
  if [[ -L "$link_path" ]]; then
    resolved="$(canonical_path "$link_path")"
    resolved_target="$(canonical_path "$target")"
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
  [[ "$(canonical_path "$link_path")" == "$(canonical_path "$target")" ]]
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

set_dcode_link() {
  local command_name="$1"
  local target="$2"
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
  assert_under_home "$target"
  ln -sfn "$target" "$link_path"
  [[ "$(canonical_path "$link_path")" == "$(canonical_path "$target")" ]]
}

dcode_launcher="$expected_home/.claude/bin/dcode-launcher"
dcode_native="$expected_home/.local/share/herdr-clis/dcode-0.1.56/bin"
if [[ -f "$dcode_launcher" && ! -L "$dcode_launcher" &&
      -x "$dcode_native/dcode" && -x "$dcode_native/deepagents-code" ]]; then
  chmod 0755 "$dcode_launcher"
  bridge_ok=1
  for command_name in dcode deepagents-code; do
    if ! dcode_version="$(env DCODE_COMMAND_NAME="$command_name" \
      "$zsh_path" "$dcode_launcher" --version </dev/null 2>&1)" ||
      ! printf '%s\n' "$dcode_version" |
        grep -Eq '(^|[^0-9A-Za-z])0\.1\.56([^0-9A-Za-z]|$)'; then
      bridge_ok=0
    fi
  done
  if [[ "$bridge_ok" == "1" ]]; then
    set_dcode_link dcode "$dcode_launcher"
    set_dcode_link deepagents-code "$dcode_launcher"
    for command_name in dcode deepagents-code; do
      if ! dcode_version="$(env DCODE_COMMAND_NAME="$command_name" \
        "$zsh_path" "$dcode_launcher" --version </dev/null 2>&1)" ||
        ! printf '%s\n' "$dcode_version" |
          grep -Eq '(^|[^0-9A-Za-z])0\.1\.56([^0-9A-Za-z]|$)'; then
        set_dcode_link dcode "$dcode_native/dcode"
        set_dcode_link deepagents-code "$dcode_native/deepagents-code"
        echo "INCOMPLETE dcode bridge: post-link probe failed; restored pinned direct shims"
        bridge_ok=0
        break
      fi
    done
    [[ "$bridge_ok" == "0" ]] || echo "READY dcode bridge 0.1.56"
  else
    set_dcode_link dcode "$dcode_native/dcode"
    set_dcode_link deepagents-code "$dcode_native/deepagents-code"
    echo "INCOMPLETE dcode bridge: safety probe failed; restored pinned direct shims"
  fi
else
  # A missing native runtime must never leave an unguarded entrypoint active.
  set_dcode_link dcode "$dcode_launcher"
  set_dcode_link deepagents-code "$dcode_launcher"
  echo "INCOMPLETE dcode bridge: launcher or pinned Linux venv is missing; guarded shims fail closed"
fi

glm="$expected_home/.local/bin/glm"
[[ -f "$glm" && ! -L "$glm" ]]
chmod 0755 "$glm"
if ! glm_version="$("$zsh_path" "$glm" --version </dev/null 2>&1)" ||
  ! printf '%s\n' "$glm_version" |
    grep -Eq '(^|[^0-9A-Za-z])2\.1\.237([^0-9A-Za-z]|$)'; then
  echo "sync-herdr-vps-harness(remote): glm wrapper cannot report Claude Code 2.1.237" >&2
  exit 1
fi
echo "READY glm wrapper via Claude Code 2.1.237"
REMOTE_FINALIZE

echo "Harness sync complete; missing auth/device logins remain explicitly INCOMPLETE above."
