#!/usr/bin/env bash
# Provision the repository-managed Herdr runtime for the unprivileged VPS user.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="caspers_vps"
RELEASE_REPOSITORY="herdrdev/herdr"
RELEASE_ASSET="herdr-linux-x86_64"
REMOTE_STAGE=""

fail() {
  echo "provision-herdr-vps: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

cleanup_remote_stage() {
  if [[ -n "$REMOTE_STAGE" ]]; then
    ssh "$SSH_TARGET" rm -rf -- "$REMOTE_STAGE" >/dev/null 2>&1 || true
  fi
}

for command in herdr gh ssh scp; do
  require_command "$command"
done

required_files=(
  "$REPO/bin/herdr-vps-watchdog"
  "$REPO/config/herdr-vps/config.toml"
  "$REPO/config/herdr-vps/herdr-dev.service"
  "$REPO/config/herdr-vps/herdr-vps-watchdog.service"
  "$REPO/config/herdr-vps/herdr-vps-watchdog.timer"
)
for required_file in "${required_files[@]}"; do
  [[ -f "$required_file" ]] || fail "required repository file not found: $required_file"
done

version_output="$(herdr --version)"
local_version="${version_output#herdr }"
if [[ "$version_output" != "herdr $local_version" ]] ||
   [[ ! "$local_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]]; then
  fail "unable to resolve installed Herdr version from: $version_output"
fi

asset_metadata="$(
  gh api "repos/$RELEASE_REPOSITORY/releases/tags/v$local_version" \
    --jq '.assets[] | select(.name == "herdr-linux-x86_64") | [.browser_download_url, .digest] | @tsv'
)"
[[ -n "$asset_metadata" ]] || fail "GitHub release is missing $RELEASE_ASSET"
[[ "$asset_metadata" != *$'\n'* ]] || fail "GitHub release contains multiple $RELEASE_ASSET assets"

IFS=$'\t' read -r asset_url asset_digest extra <<< "$asset_metadata"
expected_url="https://github.com/$RELEASE_REPOSITORY/releases/download/v$local_version/$RELEASE_ASSET"
[[ "$asset_url" == "$expected_url" ]] || fail "unexpected GitHub release asset URL"
[[ -z "${extra:-}" ]] || fail "unexpected GitHub release asset metadata"
[[ "$asset_digest" == sha256:* ]] || fail "GitHub release asset has no SHA-256 digest"
asset_sha256="${asset_digest#sha256:}"
[[ ${#asset_sha256} -eq 64 ]] || fail "GitHub release asset has an invalid SHA-256 digest"
[[ ! "$asset_sha256" =~ [^0-9a-f] ]] || fail "GitHub release asset has an invalid SHA-256 digest"

# No remote state is touched until the official asset digest is present and valid.
REMOTE_STAGE="$(
  ssh "$SSH_TARGET" \
    'umask 077; mkdir -p /home/user/.cache; mktemp -d /home/user/.cache/herdr-provision.XXXXXX'
)"
[[ "$REMOTE_STAGE" =~ ^/home/user/\.cache/herdr-provision\.[A-Za-z0-9]+$ ]] || {
  REMOTE_STAGE=""
  fail "remote host returned an unsafe staging path"
}
trap cleanup_remote_stage EXIT

scp \
  "$REPO/bin/herdr-vps-watchdog" \
  "$REPO/config/herdr-vps/config.toml" \
  "$REPO/config/herdr-vps/herdr-dev.service" \
  "$REPO/config/herdr-vps/herdr-vps-watchdog.service" \
  "$REPO/config/herdr-vps/herdr-vps-watchdog.timer" \
  "$SSH_TARGET:$REMOTE_STAGE/"

ssh "$SSH_TARGET" bash -s -- \
  "$REMOTE_STAGE" "$local_version" "$asset_url" "$asset_sha256" <<'REMOTE_SCRIPT'
set -euo pipefail

stage="$1"
version="$2"
asset_url="$3"
asset_sha256="$4"
expected_home="/home/user"

fail() {
  echo "provision-herdr-vps(remote): $*" >&2
  exit 1
}

cleanup() {
  rm -rf -- "$stage"
}
trap cleanup EXIT

[[ "$(id -un)" == "user" ]] || fail "SSH login must be user"
[[ "$HOME" == "$expected_home" ]] || fail "unexpected remote home: $HOME"
[[ "$(uname -s)" == "Linux" ]] || fail "remote host must run Linux"
[[ "$(uname -m)" == "x86_64" ]] || fail "remote host must be x86_64"
[[ "$stage" =~ ^/home/user/\.cache/herdr-provision\.[A-Za-z0-9]+$ ]] || fail "unsafe staging path"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]] || fail "invalid version"
[[ "$asset_url" == "https://github.com/herdrdev/herdr/releases/download/v$version/herdr-linux-x86_64" ]] || fail "invalid asset URL"
[[ ${#asset_sha256} -eq 64 ]] || fail "invalid SHA-256 digest"
[[ ! "$asset_sha256" =~ [^0-9a-f] ]] || fail "invalid SHA-256 digest"

for command in curl sha256sum install mv systemctl sudo; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done

download="$stage/herdr-linux-x86_64.download"
curl --fail --location --proto '=https' --tlsv1.2 \
  --retry 3 --connect-timeout 10 --max-time 300 \
  --output "$download" "$asset_url"
printf '%s  %s\n' "$asset_sha256" "$download" | sha256sum --check --status -
chmod 0755 "$download"

downloaded_version="$("$download" --version)"
[[ "$downloaded_version" == "herdr $version" ]] || fail "verified binary reports $downloaded_version"

mkdir -p \
  "$HOME/.local/bin" \
  "$HOME/.local/state/herdr-watchdog" \
  "$HOME/.config/herdr" \
  "$HOME/.config/systemd/user" \
  "$HOME/Projects/.herdr-worktrees"

# Install the verified binary atomically so a rerun cannot leave a partial executable.
install -m 0755 "$download" "$HOME/.local/bin/.herdr.new"
mv -f "$HOME/.local/bin/.herdr.new" "$HOME/.local/bin/herdr"
install -m 0755 "$stage/herdr-vps-watchdog" "$HOME/.local/bin/herdr-vps-watchdog"
install -m 0644 "$stage/config.toml" "$HOME/.config/herdr/config.toml"
install -m 0644 "$stage/herdr-dev.service" "$HOME/.config/systemd/user/herdr-dev.service"
install -m 0644 "$stage/herdr-vps-watchdog.service" "$HOME/.config/systemd/user/herdr-vps-watchdog.service"
install -m 0644 "$stage/herdr-vps-watchdog.timer" "$HOME/.config/systemd/user/herdr-vps-watchdog.timer"

# This is the sole privileged action: user -> admin -> root for user lingering.
/usr/bin/sudo -n -u admin /usr/bin/sudo -n /usr/bin/loginctl enable-linger user

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
[[ -S "$XDG_RUNTIME_DIR/bus" ]] || fail "user systemd bus is unavailable"
systemctl --user daemon-reload
systemctl --user enable herdr-dev.service herdr-vps-watchdog.timer
systemctl --user restart herdr-dev.service
systemctl --user restart herdr-vps-watchdog.timer
systemctl --user is-active --quiet herdr-dev.service
systemctl --user is-active --quiet herdr-vps-watchdog.timer
[[ "$("$HOME/.local/bin/herdr" --version)" == "herdr $version" ]] || fail "installed version mismatch"
REMOTE_SCRIPT

REMOTE_STAGE=""
trap - EXIT
echo "Herdr $local_version provisioned for user@$SSH_TARGET"
