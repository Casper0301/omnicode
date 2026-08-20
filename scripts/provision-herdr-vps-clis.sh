#!/usr/bin/env bash
# Install the pinned Linux coding harness for Herdr's unprivileged VPS user.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="caspers_vps"
REMOTE_STAGE=""
REMOTE_INSTALL_STAGE=""
INSTALL_TRANSACTION_ACTIVE=0

CLAUDE_VERSION="2.1.237"
CLAUDE_PACKAGE="@anthropic-ai/claude-code@2.1.237"
CLAUDE_INTEGRITY="sha512-abVRJmxRjeoti4i5luV56PZ2T73gJOO7Y1puy/SsXpF5sid0PXbqBkbX4jQMLtdy2Ho4MftJ71v1vCXYrhb9Ww=="
CODEX_VERSION="0.148.0"
CODEX_PACKAGE="@openai/codex@0.148.0"
CODEX_INTEGRITY="sha512-bh5kH9+BMrFaHGmLeoSansPdfRksvr4UXzjQInns/KRO7r8VJ+6AAW+SqUsE8XcG3+OW/mI4EEy8Gpo9UDXGvQ=="
PI_VERSION="0.84.2"
PI_PACKAGE="@earendil-works/pi-coding-agent@0.84.2"
PI_INTEGRITY="sha512-l4E+B7hgXKWddRo8bC/eSue2aWZjEgJ9xIpf5p0Og+lq8a2TArCwJ0HCoCPCgaBP/tN4zbYH/wOwvx9pJpeLCA=="
OMP_VERSION="17.3.0"
OMP_URL="https://github.com/can1357/oh-my-pi/releases/download/v17.3.0/omp-linux-x64"
OMP_SHA256="287f07366f29896ef1e345423dab79b82a8dc0c1593383e20dfdd62a9dd2e799"
DCODE_VERSION="0.1.56"
DCODE_URL="https://files.pythonhosted.org/packages/93/6c/a8b9b424fd8acbd24fe83df1a60733fc3ee9bf7b699146854fbce77788c3/deepagents_code-0.1.56-py3-none-any.whl"
DCODE_SHA256="635979453e26fc78e838d639a83f50de29d72d418ace6746c82bccded8bd8936"
OPENCODE_VERSION="1.17.13"
OPENCODE_URL="https://github.com/anomalyco/opencode/releases/download/v1.17.13/opencode-linux-x64.tar.gz"
OPENCODE_SHA256="157afa289d1a8d9372de0ce19ac726119b937a1f6b201808d46f06e4e59bb348"
HERMES_VERSION="0.20.4"
HERMES_REPOSITORY="https://github.com/NousResearch/hermes-agent.git"
HERMES_COMMIT="e624e9fde561e1add9388384012b295fde669ade"
UV_VERSION="0.10.9"
UV_URL="https://files.pythonhosted.org/packages/79/34/b104c413079874493eed7bf11838b47b697cf1f0ed7e9de374ea37b4e4e0/uv-0.10.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
UV_SHA256="7c9d6deb30edbc22123be75479f99fb476613eaf38a8034c0e98bba24a344179"
GROK_VERSION="1.0.5"
GROK_URL="https://x.ai/cli/grok-1.0.5-linux-x86_64"
CURSOR_VERSION="2026.08.11-e8db854"
CURSOR_URL="https://downloads.cursor.com/lab/2026.08.11-e8db854/linux/x64/agent-cli-package.tar.gz"
NPM_REGISTRY="https://registry.npmjs.org/"
PYPI_INDEX="https://pypi.org/simple"

fail() {
  echo "provision-herdr-vps-clis: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

print_manifest() {
  cat <<MANIFEST
claude|$CLAUDE_VERSION|npm|$CLAUDE_PACKAGE|$CLAUDE_INTEGRITY
codex|$CODEX_VERSION|npm|$CODEX_PACKAGE|$CODEX_INTEGRITY
pi|$PI_VERSION|npm|$PI_PACKAGE|$PI_INTEGRITY
omp|$OMP_VERSION|native|$OMP_URL|sha256:$OMP_SHA256
dcode|$DCODE_VERSION|wheel|$DCODE_URL|sha256:$DCODE_SHA256
opencode|$OPENCODE_VERSION|native|$OPENCODE_URL|sha256:$OPENCODE_SHA256
hermes|$HERMES_VERSION|git|$HERMES_REPOSITORY|commit:$HERMES_COMMIT
grok|$GROK_VERSION|unavailable|$GROK_URL|no-official-sha256
cursor-agent|$CURSOR_VERSION|unavailable|$CURSOR_URL|no-official-sha256
glm|sync-only|wrapper|~/.local/bin/glm|portable-zai-auth
MANIFEST
}

version_output_matches() {
  local output="$1"
  local expected="$2"
  local escaped="${expected//./\\.}"
  printf '%s\n' "$output" | grep -Eq "(^|[^0-9A-Za-z])v?${escaped}([^0-9A-Za-z]|$)"
}

probe_runtime() {
  local label="$1"
  local expected="$2"
  local executable="$3"
  local output=""

  if ! command -v "$executable" >/dev/null 2>&1; then
    return 2
  fi
  if ! output="$("$executable" --version </dev/null 2>&1)"; then
    echo "replacement required: $label executable cannot report its version" >&2
    return 1
  fi
  if ! version_output_matches "$output" "$expected"; then
    echo "replacement required: $label active executable does not report $expected" >&2
    return 1
  fi
  printf 'READY %s %s\n' "$label" "$expected"
  return 0
}

download_verified_sha256() {
  local label="$1"
  local url="$2"
  local expected_sha256="$3"
  local output="$4"

  require_command curl
  require_command sha256sum
  curl --fail --location --proto '=https' --tlsv1.2 \
    --retry 3 --connect-timeout 10 --max-time 600 \
    --output "$output" "$url"
  if ! printf '%s  %s\n' "$expected_sha256" "$output" |
    sha256sum --check --status -; then
    fail "$label SHA-256 verification failed"
  fi
}

verify_staged_version() {
  local label="$1"
  local expected="$2"
  local executable="$3"
  local output=""

  chmod 0755 "$executable"
  if ! output="$("$executable" --version </dev/null 2>&1)" ||
    ! version_output_matches "$output" "$expected"; then
    fail "$label verified artifact does not report $expected"
  fi
}

ensure_managed_link() {
  local link_path="$1"
  local target="$2"
  local current=""

  if [[ -L "$link_path" ]]; then
    current="$(readlink "$link_path")"
    [[ "$current" == "$target" ]] ||
      fail "replacement required: unrelated symlink at $link_path"
    return
  fi
  [[ ! -e "$link_path" ]] || fail "replacement required: unrelated path at $link_path"
  ln -s "$target" "$link_path"
}

prepare_managed_directory() {
  local directory="$1"
  local marker="$directory/.herdr-vps-managed"

  if [[ -e "$directory" ]]; then
    [[ -f "$marker" ]] || fail "replacement required: unmanaged directory at $directory"
    rm -rf -- "$directory"
  fi
  mkdir -p "$directory"
  : > "$marker"
}

verify_npm_integrity() {
  local package_spec="$1"
  local expected_integrity="$2"
  local actual_integrity=""

  actual_integrity="$(
    npm view "$package_spec" dist.integrity --json \
      --registry "$NPM_REGISTRY" 2>/dev/null
  )" ||
    fail "unable to read npm integrity for $package_spec"
  actual_integrity="${actual_integrity#\"}"
  actual_integrity="${actual_integrity%\"}"
  [[ "$actual_integrity" == "$expected_integrity" ]] ||
    fail "npm integrity mismatch for $package_spec"
}

stage_npm_runtime() {
  local package_spec="$1"
  local expected_integrity="$2"
  local stage="$3"
  local output_variable="$4"
  local filename=""
  local archive=""
  local actual_integrity=""

  verify_npm_integrity "$package_spec" "$expected_integrity"
  filename="$(
    npm pack --silent --pack-destination "$stage" \
      --registry "$NPM_REGISTRY" "$package_spec"
  )" || fail "unable to stage npm package $package_spec"
  filename="${filename##*$'\n'}"
  [[ -n "$filename" && "$filename" == "$(basename "$filename")" ]] ||
    fail "npm returned an unsafe staged filename for $package_spec"
  archive="$stage/$filename"
  [[ -f "$archive" && ! -L "$archive" ]] ||
    fail "npm did not stage a regular archive for $package_spec"
  actual_integrity="$(python3 - "$archive" <<'PY'
import base64
import hashlib
import pathlib
import sys

payload = pathlib.Path(sys.argv[1]).read_bytes()
print("sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii"))
PY
)" || fail "unable to hash staged npm package $package_spec"
  [[ "$actual_integrity" == "$expected_integrity" ]] ||
    fail "staged npm integrity mismatch for $package_spec"
  printf -v "$output_variable" '%s' "$archive"
}

install_npm_runtime() {
  local label="$1"
  local expected="$2"
  local executable="$3"
  local archive="$4"

  npm install --global --prefix "$HOME/.local" --no-audit --no-fund \
    --registry "$NPM_REGISTRY" "$archive"
  hash -r
  probe_runtime "$label" "$expected" "$executable" >/dev/null ||
    fail "$label install did not produce version $expected"
  printf 'INSTALLED %s %s\n' "$label" "$expected"
}

install_hermes() {
  local install_stage="$1"
  local staged_uv="$2"
  local source="$HOME/.hermes/hermes-agent"
  local staged_source="$install_stage/hermes-agent"
  local uv_environment="$HOME/.local/share/herdr-clis/uv-$UV_VERSION"
  local uv_binary="$uv_environment/bin/uv"
  local checkout=""
  local origin=""
  local uv_output=""

  require_command git
  require_command mv
  require_command python3

  if [[ ! -x "$uv_binary" ]]; then
    prepare_managed_directory "$uv_environment"
    python3 -m venv "$uv_environment"
    : > "$uv_environment/.herdr-vps-managed"
    env -u PIP_EXTRA_INDEX_URL -u PIP_TRUSTED_HOST \
      PIP_INDEX_URL="$PYPI_INDEX" \
      "$uv_environment/bin/python" -m pip install \
        --disable-pip-version-check --no-deps "$staged_uv"
  fi
  [[ -x "$uv_binary" ]] || fail "uv bootstrap did not produce $uv_binary"
  uv_output="$("$uv_binary" --version 2>/dev/null || true)"
  version_output_matches "$uv_output" "$UV_VERSION" ||
    fail "replacement required: managed uv does not report $UV_VERSION"

  if [[ -e "$source" ]]; then
    [[ -d "$source/.git" ]] || fail "replacement required: unmanaged Hermes source at $source"
    origin="$(git -C "$source" remote get-url origin 2>/dev/null || true)"
    [[ "$origin" == "$HERMES_REPOSITORY" ]] ||
      fail "replacement required: Hermes checkout has an unexpected origin"
    checkout="$(git -C "$source" rev-parse HEAD 2>/dev/null || true)"
    [[ "$checkout" == "$HERMES_COMMIT" ]] ||
      fail "replacement required: Hermes checkout is not $HERMES_COMMIT"
  else
    [[ -d "$staged_source/.git" ]] || fail "Hermes staged checkout is missing"
    checkout="$(git -C "$staged_source" rev-parse HEAD)"
    [[ "$checkout" == "$HERMES_COMMIT" ]] || fail "Hermes commit verification failed"
    mkdir -p "$(dirname "$source")"
    mv "$staged_source" "$source"
  fi

  env -u UV_INDEX_URL -u UV_EXTRA_INDEX_URL -u UV_PYTHON \
    UV_DEFAULT_INDEX="$PYPI_INDEX" \
    UV_PROJECT_ENVIRONMENT="$source/.venv" \
    "$uv_binary" sync --locked --project "$source" --python "$(command -v python3)"
  [[ -x "$source/.venv/bin/hermes" ]] || fail "Hermes sync did not produce its CLI"
  ensure_managed_link "$HOME/.local/bin/hermes" "$source/.venv/bin/hermes"
  hash -r
  probe_runtime hermes "$HERMES_VERSION" hermes >/dev/null ||
    fail "Hermes install did not produce version $HERMES_VERSION"
  printf 'INSTALLED hermes %s\n' "$HERMES_VERSION"
}

cleanup_install_stage() {
  local status=$?
  if [[ "$INSTALL_TRANSACTION_ACTIVE" == "1" && "$status" != "0" ]]; then
    echo "INCOMPLETE provision transaction: rerun the pinned provisioner; managed paths are recoverable" >&2
  fi
  if [[ -n "$REMOTE_INSTALL_STAGE" ]]; then
    [[ "$REMOTE_INSTALL_STAGE" == "$HOME/.cache/herdr-cli-provision."* ]] || return "$status"
    rm -rf -- "$REMOTE_INSTALL_STAGE"
    REMOTE_INSTALL_STAGE=""
  fi
  return "$status"
}

assert_destination_parent_safe() {
  local path="$1"
  local current="$HOME"
  local relative="${path#"$HOME"/}"
  local component=""
  local parent="${path%/*}"
  local resolved=""
  local resolved_home=""
  local -a components=()

  [[ "$path" == "$HOME/"* ]] || fail "destination escapes home: $path"
  resolved="$(python3 - "$parent" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
)" || fail "cannot resolve destination parent: $parent"
  resolved_home="$(python3 - "$HOME" <<'PY'
import os
import sys
print(os.path.realpath(sys.argv[1]))
PY
)" || fail "cannot resolve remote home"
  [[ "$resolved" == "$resolved_home" || "$resolved" == "$resolved_home/"* ]] ||
    fail "destination parent escapes home: $parent"
  IFS='/' read -r -a components <<< "$relative"
  for component in "${components[@]:0:${#components[@]}-1}"; do
    current="$current/$component"
    [[ ! -L "$current" ]] || fail "replacement required: symlinked destination parent at $current"
    [[ ! -e "$current" || -d "$current" ]] ||
      fail "replacement required: non-directory destination parent at $current"
  done
}

assert_absent_destination() {
  local path="$1"
  assert_destination_parent_safe "$path"
  [[ ! -e "$path" && ! -L "$path" ]] ||
    fail "replacement required: unrelated path at $path"
}

assert_managed_directory_destination() {
  local path="$1"
  assert_destination_parent_safe "$path"
  if [[ -e "$path" || -L "$path" ]]; then
    [[ -d "$path" && ! -L "$path" && -f "$path/.herdr-vps-managed" ]] ||
      fail "replacement required: unmanaged directory at $path"
  fi
}

assert_managed_link_destination() {
  local path="$1"
  local target="$2"
  local current=""
  assert_destination_parent_safe "$path"
  if [[ -L "$path" ]]; then
    current="$(readlink "$path")"
    [[ "$current" == "$target" ]] ||
      fail "replacement required: unrelated symlink at $path"
  elif [[ -e "$path" ]]; then
    fail "replacement required: unrelated path at $path"
  fi
}

stage_hermes_checkout() {
  local stage="$1"
  local staged_source="$stage/hermes-agent"
  local checkout=""

  [[ ! -e "$staged_source" ]] || fail "Hermes staging path already exists"
  mkdir -p "$staged_source"
  git -C "$staged_source" init --quiet
  git -C "$staged_source" remote add origin "$HERMES_REPOSITORY"
  git -C "$staged_source" fetch --quiet --depth 1 origin "$HERMES_COMMIT"
  git -C "$staged_source" checkout --quiet --detach FETCH_HEAD
  checkout="$(git -C "$staged_source" rev-parse HEAD)"
  [[ "$checkout" == "$HERMES_COMMIT" ]] || fail "Hermes commit verification failed"
}

remote_main() {
  local remote_profile="${1:-}"
  local mode="${2:-install}"
  local expected_home="/home/user"
  local mismatch=0
  local probe_result=0
  local have_claude=0
  local have_codex=0
  local have_pi=0
  local have_omp=0
  local have_dcode=0
  local have_opencode=0
  local have_hermes=0
  local have_grok=0
  local have_cursor=0
  local stage=""
  local archive_entries=""
  local claude_archive=""
  local codex_archive=""
  local pi_archive=""
  local dcode_environment="$HOME/.local/share/herdr-clis/dcode-$DCODE_VERSION"
  local uv_environment="$HOME/.local/share/herdr-clis/uv-$UV_VERSION"
  local hermes_source="$HOME/.hermes/hermes-agent"
  local hermes_origin=""
  local hermes_checkout=""
  local uv_output=""

  [[ "$(id -un)" == "user" ]] || fail "SSH login must be user"
  [[ "$HOME" == "$expected_home" ]] || fail "unexpected remote home: $HOME"
  [[ "$(uname -s)" == "Linux" ]] || fail "remote host must run Linux"
  [[ "$(uname -m)" == "x86_64" ]] || fail "remote host must be x86_64"
  [[ -f "$remote_profile" ]] || fail "remote profile not found"
  [[ "$mode" == "install" || "$mode" == "--check" ]] || fail "invalid remote mode: $mode"

  PATH="$HOME/.local/bin:$HOME/.grok/bin:$HOME/.hermes/bin:$PATH"
  export PATH
  npm_config_cache="$HOME/.cache/npm-herdr"
  export npm_config_cache
  mkdir -p "$npm_config_cache"
  chmod 0700 "$npm_config_cache"

  if probe_runtime claude "$CLAUDE_VERSION" claude; then have_claude=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime codex "$CODEX_VERSION" codex; then have_codex=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime pi "$PI_VERSION" pi; then have_pi=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime omp "$OMP_VERSION" omp; then have_omp=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime dcode "$DCODE_VERSION" dcode; then have_dcode=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime opencode "$OPENCODE_VERSION" opencode; then have_opencode=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi
  if probe_runtime hermes "$HERMES_VERSION" hermes; then have_hermes=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi

  if command -v grok >/dev/null 2>&1; then
    if probe_runtime grok "$GROK_VERSION" grok; then have_grok=1; else mismatch=1; fi
  fi
  if [[ -x "$HOME/.grok/bin/agent" ]]; then
    if probe_runtime "grok alias agent" "$GROK_VERSION" "$HOME/.grok/bin/agent"; then
      have_grok=1
    else
      mismatch=1
    fi
  fi
  if probe_runtime cursor-agent "$CURSOR_VERSION" cursor-agent; then have_cursor=1; else
    probe_result=$?; [[ "$probe_result" == "2" ]] || mismatch=1
  fi

  [[ "$mismatch" == "0" ]] || fail "one or more active CLIs require explicit replacement"

  if [[ "$mode" == "--check" ]]; then
    [[ "$have_claude" == "1" ]] || echo "INCOMPLETE claude: $CLAUDE_VERSION is not installed"
    [[ "$have_codex" == "1" ]] || echo "INCOMPLETE codex: $CODEX_VERSION is not installed"
    [[ "$have_pi" == "1" ]] || echo "INCOMPLETE pi: $PI_VERSION is not installed"
    [[ "$have_omp" == "1" ]] || echo "INCOMPLETE omp: $OMP_VERSION is not installed"
    [[ "$have_dcode" == "1" ]] || echo "INCOMPLETE dcode: $DCODE_VERSION is not installed"
    [[ "$have_opencode" == "1" ]] || echo "INCOMPLETE opencode: $OPENCODE_VERSION is not installed"
    [[ "$have_hermes" == "1" ]] || echo "INCOMPLETE hermes: $HERMES_VERSION is not installed"
    [[ "$have_grok" == "1" ]] || echo "INCOMPLETE grok: no vendor-published SHA-256 for Linux $GROK_VERSION"
    [[ "$have_cursor" == "1" ]] || echo "INCOMPLETE cursor-agent: no vendor-published SHA-256 for Linux $CURSOR_VERSION"
    exit 0
  fi

  for command in basename install mkdir mktemp python3 rm; do
    require_command "$command"
  done
  [[ -f "$remote_profile" && ! -L "$remote_profile" ]] ||
    fail "remote profile must be a regular staged file"

  # Resolve every persistent destination before downloads or installation.
  [[ "$have_omp" == "1" ]] || assert_absent_destination "$HOME/.local/bin/omp"
  [[ "$have_opencode" == "1" ]] || assert_absent_destination "$HOME/.local/bin/opencode"
  if [[ "$have_dcode" == "0" ]]; then
    assert_managed_directory_destination "$dcode_environment"
    assert_managed_link_destination "$HOME/.local/bin/dcode" "$dcode_environment/bin/dcode"
    assert_managed_link_destination \
      "$HOME/.local/bin/deepagents-code" "$dcode_environment/bin/deepagents-code"
  fi
  if [[ "$have_claude" == "0" ]]; then
    assert_absent_destination "$HOME/.local/bin/claude"
    assert_absent_destination "$HOME/.local/lib/node_modules/@anthropic-ai/claude-code"
  fi
  if [[ "$have_codex" == "0" ]]; then
    assert_absent_destination "$HOME/.local/bin/codex"
    assert_absent_destination "$HOME/.local/lib/node_modules/@openai/codex"
  fi
  if [[ "$have_pi" == "0" ]]; then
    assert_absent_destination "$HOME/.local/bin/pi"
    assert_absent_destination "$HOME/.local/lib/node_modules/@earendil-works/pi-coding-agent"
  fi
  if [[ "$have_hermes" == "0" ]]; then require_command git; fi
  if [[ "$have_hermes" == "0" ]]; then
    assert_managed_directory_destination "$uv_environment"
    if [[ -x "$uv_environment/bin/uv" ]]; then
      uv_output="$("$uv_environment/bin/uv" --version 2>/dev/null || true)"
      version_output_matches "$uv_output" "$UV_VERSION" ||
        fail "replacement required: managed uv does not report $UV_VERSION"
    fi
    assert_destination_parent_safe "$hermes_source"
    assert_managed_link_destination \
      "$HOME/.local/bin/hermes" "$hermes_source/.venv/bin/hermes"
  fi
  if [[ "$have_hermes" == "0" && ( -e "$hermes_source" || -L "$hermes_source" ) ]]; then
    [[ -d "$hermes_source/.git" && ! -L "$hermes_source" ]] ||
      fail "replacement required: unmanaged Hermes source at $hermes_source"
    hermes_origin="$(git -C "$hermes_source" remote get-url origin 2>/dev/null || true)"
    hermes_checkout="$(git -C "$hermes_source" rev-parse HEAD 2>/dev/null || true)"
    [[ "$hermes_origin" == "$HERMES_REPOSITORY" && "$hermes_checkout" == "$HERMES_COMMIT" ]] ||
      fail "replacement required: Hermes checkout does not match the pinned source"
  fi
  assert_destination_parent_safe "$HOME/.config/herdr/remote-profile.sh"
  [[ ! -L "$HOME/.config/herdr/remote-profile.sh" &&
     ( ! -e "$HOME/.config/herdr/remote-profile.sh" || -f "$HOME/.config/herdr/remote-profile.sh" ) ]] ||
    fail "replacement required: unrelated remote profile destination"
  assert_destination_parent_safe "$HOME/.profile"
  [[ ! -L "$HOME/.profile" && ( ! -e "$HOME/.profile" || -f "$HOME/.profile" ) ]] ||
    fail "replacement required: unrelated login profile"
  assert_destination_parent_safe "$HOME/.cache/herdr-cli-provision.placeholder"

  # Stage and authenticate every static input before any harness binary lands.
  if [[ "$have_omp" == "0" || "$have_opencode" == "0" ||
        "$have_dcode" == "0" || "$have_hermes" == "0" ]]; then
    for command in curl sha256sum; do require_command "$command"; done
  fi
  if [[ "$have_opencode" == "0" ]]; then require_command tar; fi
  if [[ "$have_dcode" == "0" || "$have_hermes" == "0" ||
        "$have_claude" == "0" || "$have_codex" == "0" || "$have_pi" == "0" ]]; then
    require_command python3
  fi
  if [[ "$have_claude" == "0" || "$have_codex" == "0" || "$have_pi" == "0" ]]; then
    require_command npm
  fi
  if [[ "$have_hermes" == "0" ]]; then
    require_command git
    require_command mv
  fi

  mkdir -p "$HOME/.cache"
  REMOTE_INSTALL_STAGE="$(mktemp -d "$HOME/.cache/herdr-cli-provision.XXXXXX")"
  [[ "$REMOTE_INSTALL_STAGE" == "$HOME/.cache/herdr-cli-provision."* ]] ||
    fail "unsafe staging path"
  stage="$REMOTE_INSTALL_STAGE"
  trap cleanup_install_stage EXIT

  if [[ "$have_omp" == "0" ]]; then
    download_verified_sha256 omp "$OMP_URL" "$OMP_SHA256" "$stage/omp"
    verify_staged_version omp "$OMP_VERSION" "$stage/omp"
  fi

  if [[ "$have_opencode" == "0" ]]; then
    download_verified_sha256 opencode "$OPENCODE_URL" "$OPENCODE_SHA256" "$stage/opencode.tar.gz"
    archive_entries="$(tar -tzf "$stage/opencode.tar.gz")"
    [[ "$archive_entries" == "opencode" || "$archive_entries" == "./opencode" ]] ||
      fail "opencode archive contains unexpected paths"
    tar -xzf "$stage/opencode.tar.gz" -C "$stage"
    [[ -f "$stage/opencode" ]] || fail "opencode archive is missing its executable"
    verify_staged_version opencode "$OPENCODE_VERSION" "$stage/opencode"
  fi

  if [[ "$have_dcode" == "0" ]]; then
    download_verified_sha256 dcode "$DCODE_URL" "$DCODE_SHA256" \
      "$stage/deepagents_code-0.1.56-py3-none-any.whl"
  fi
  [[ "$have_claude" == "1" ]] ||
    stage_npm_runtime "$CLAUDE_PACKAGE" "$CLAUDE_INTEGRITY" "$stage" claude_archive
  [[ "$have_codex" == "1" ]] ||
    stage_npm_runtime "$CODEX_PACKAGE" "$CODEX_INTEGRITY" "$stage" codex_archive
  [[ "$have_pi" == "1" ]] ||
    stage_npm_runtime "$PI_PACKAGE" "$PI_INTEGRITY" "$stage" pi_archive
  if [[ "$have_hermes" == "0" ]]; then
    download_verified_sha256 uv "$UV_URL" "$UV_SHA256" \
      "$stage/uv-0.10.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    if [[ ! -e "$hermes_source" ]]; then
      stage_hermes_checkout "$stage"
    fi
  fi
  if [[ "$have_dcode" == "0" || "$have_hermes" == "0" ]]; then
    python3 -m venv "$stage/python-venv-probe" ||
      fail "python3 venv prerequisite is unavailable"
    [[ -x "$stage/python-venv-probe/bin/python" &&
       -x "$stage/python-venv-probe/bin/pip" ]] ||
      fail "python3 venv prerequisite did not provide pip"
    rm -rf -- "$stage/python-venv-probe"
  fi

  INSTALL_TRANSACTION_ACTIVE=1
  mkdir -p "$HOME/.local/bin" "$HOME/.local/share/herdr-clis" "$HOME/.config/herdr"

  if [[ "$have_omp" == "0" ]]; then
    install -m 0755 "$stage/omp" "$HOME/.local/bin/omp"
    printf 'INSTALLED omp %s\n' "$OMP_VERSION"
  fi
  if [[ "$have_opencode" == "0" ]]; then
    install -m 0755 "$stage/opencode" "$HOME/.local/bin/opencode"
    printf 'INSTALLED opencode %s\n' "$OPENCODE_VERSION"
  fi
  if [[ "$have_dcode" == "0" ]]; then
    prepare_managed_directory "$dcode_environment"
    python3 -m venv "$dcode_environment"
    : > "$dcode_environment/.herdr-vps-managed"
    env -u PIP_EXTRA_INDEX_URL -u PIP_TRUSTED_HOST \
      PIP_INDEX_URL="$PYPI_INDEX" \
      "$dcode_environment/bin/python" -m pip install \
        --disable-pip-version-check \
        "$stage/deepagents_code-0.1.56-py3-none-any.whl"
    [[ -x "$dcode_environment/bin/dcode" ]] || fail "dcode wheel did not produce its CLI"
    [[ -x "$dcode_environment/bin/deepagents-code" ]] ||
      fail "dcode wheel did not produce its compatibility CLI"
    ensure_managed_link "$HOME/.local/bin/dcode" "$dcode_environment/bin/dcode"
    ensure_managed_link \
      "$HOME/.local/bin/deepagents-code" \
      "$dcode_environment/bin/deepagents-code"
    hash -r
    probe_runtime dcode "$DCODE_VERSION" dcode >/dev/null ||
      fail "dcode install did not produce version $DCODE_VERSION"
    printf 'INSTALLED dcode %s\n' "$DCODE_VERSION"
  fi

  [[ "$have_claude" == "1" ]] || install_npm_runtime claude "$CLAUDE_VERSION" claude "$claude_archive"
  [[ "$have_codex" == "1" ]] || install_npm_runtime codex "$CODEX_VERSION" codex "$codex_archive"
  [[ "$have_pi" == "1" ]] || install_npm_runtime pi "$PI_VERSION" pi "$pi_archive"

  if [[ "$have_hermes" == "0" ]]; then
    install_hermes "$stage" \
      "$stage/uv-0.10.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
  fi
  install -m 0644 "$remote_profile" "$HOME/.config/herdr/remote-profile.sh"
  local login_profile="$HOME/.profile"
  # HOME must expand when the login profile is sourced.
  # shellcheck disable=SC2016
  local source_line='[ -r "$HOME/.config/herdr/remote-profile.sh" ] && . "$HOME/.config/herdr/remote-profile.sh"'
  if [[ ! -f "$login_profile" ]] || ! grep -Fqx "$source_line" "$login_profile"; then
    printf '\n%s\n' "$source_line" >> "$login_profile"
  fi

  [[ "$have_grok" == "1" ]] || echo "INCOMPLETE grok: no vendor-published SHA-256 for Linux $GROK_VERSION"
  [[ "$have_cursor" == "1" ]] || echo "INCOMPLETE cursor-agent: no vendor-published SHA-256 for Linux $CURSOR_VERSION"
  if [[ ! -x "$HOME/.local/bin/glm" ]]; then
    echo "INCOMPLETE glm: run scripts/sync-herdr-vps-harness.sh"
  fi
  INSTALL_TRANSACTION_ACTIVE=0
}

cleanup_remote_stage() {
  if [[ -n "$REMOTE_STAGE" ]]; then
    ssh "$SSH_TARGET" bash -s -- "$REMOTE_STAGE" <<'REMOTE_CLEANUP' >/dev/null 2>&1 || true
set -euo pipefail
stage="$1"
[[ "$stage" =~ ^/home/user/\.cache/herdr-cli-stage\.[A-Za-z0-9]+$ ]]
rm -rf -- "$stage"
REMOTE_CLEANUP
  fi
}

local_main() {
  local remote_profile="$REPO/config/herdr-vps/remote-profile.sh"

  for command in ssh scp; do
    require_command "$command"
  done
  [[ -f "$remote_profile" ]] || fail "required repository file not found: $remote_profile"

  if ! ssh "$SSH_TARGET" bash -s <<'REMOTE_PREFLIGHT'
set -euo pipefail
[[ "$(id -un)" == "user" ]]
[[ "$HOME" == "/home/user" ]]
[[ "$(uname -s)" == "Linux" ]]
[[ "$(uname -m)" == "x86_64" ]]
REMOTE_PREFLIGHT
  then
    fail "remote identity/platform preflight failed"
  fi

  REMOTE_STAGE="$(
    ssh "$SSH_TARGET" \
      'umask 077; mkdir -p /home/user/.cache; mktemp -d /home/user/.cache/herdr-cli-stage.XXXXXX'
  )"
  [[ "$REMOTE_STAGE" =~ ^/home/user/\.cache/herdr-cli-stage\.[A-Za-z0-9]+$ ]] || {
    REMOTE_STAGE=""
    fail "remote host returned an unsafe staging path"
  }
  trap cleanup_remote_stage EXIT

  scp "$0" "$remote_profile" "$SSH_TARGET:$REMOTE_STAGE/"
  ssh "$SSH_TARGET" bash "$REMOTE_STAGE/$(basename "$0")" \
    --remote "$REMOTE_STAGE/$(basename "$remote_profile")"
}

case "${1:-}" in
  --manifest)
    print_manifest
    ;;
  --remote)
    shift
    remote_main "$@"
    ;;
  "")
    local_main
    ;;
  *)
    fail "usage: $0 [--manifest]"
    ;;
esac
