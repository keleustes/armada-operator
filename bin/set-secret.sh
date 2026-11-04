#!/usr/bin/env bash
# set-secret.sh — Store a project secret in the macOS Keychain.
# Companion to bin/load-secrets.sh; reads the canonical key list from
# .env.example and writes via `security add-generic-password -U`.
#
# Usage:
#   bin/set-secret.sh <KEY>           # prompt silently for the value, then store
#   bin/set-secret.sh --bootstrap     # walk every key in .env.example, skip already-set
#   bin/set-secret.sh --list          # show which keys are set vs missing
#   bin/set-secret.sh -h | --help     # this help
#
# Override the GitHub handle (if no origin remote yet):
#   PROJECT_GHHANDLE=<owner> bin/set-secret.sh ...

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
GHHANDLE="${PROJECT_GHHANDLE:-$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#' || true)}"

[[ -n "${GHHANDLE:-}" ]] || {
  echo "set-secret.sh: cannot determine ghhandle (set PROJECT_GHHANDLE)" >&2
  exit 1
}

SERVICE="com.${GHHANDLE}.${PROJECT_NAME}"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

usage() {
  sed -n '2,14p' "$0" | sed -E 's/^# ?//'
}

# Guard that must run in the MAIN shell, not inside a `< <(...)` process
# substitution — an `exit` from there only kills the subshell, leaving the
# caller to exit 0 with no keys. Call this before consuming list_env_keys.
require_env_example() {
  [[ -f "$ENV_EXAMPLE" ]] || {
    echo "set-secret.sh: .env.example not found at $ENV_EXAMPLE" >&2
    exit 1
  }
}

list_env_keys() {
  local line key
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line//[[:space:]]/}" ]] && continue
    key="${line%%=*}"
    key="${key//[[:space:]]/}"
    [[ -z "$key" ]] && continue
    printf '%s\n' "$key"
  done <"$ENV_EXAMPLE"
}

prompt_and_store() {
  local key="$1" value
  if ! (exec 3<>/dev/tty) 2>/dev/null; then
    echo "set-secret.sh: no controlling TTY; secrets must be entered interactively" >&2
    return 1
  fi
  exec 3<>/dev/tty
  printf 'value for %s (input hidden): ' "$key" >&3
  IFS= read -rs value <&3 || {
    echo >&3
    exec 3<&-
    return 1
  }
  echo >&3
  exec 3<&-
  if [[ -z "$value" ]]; then
    echo "set-secret.sh: empty value; not storing" >&2
    return 1
  fi
  security add-generic-password -U -s "$SERVICE" -a "$key" -w "$value"
  echo "stored: $key (service=$SERVICE)" >&2
}

case "${1:-}" in
  -h | --help)
    usage
    ;;
  --list)
    require_env_example
    while IFS= read -r key; do
      if security find-generic-password -s "$SERVICE" -a "$key" >/dev/null 2>&1; then
        printf '  set     %s\n' "$key"
      else
        printf '  missing %s\n' "$key"
      fi
    done < <(list_env_keys)
    ;;
  --bootstrap)
    require_env_example
    while IFS= read -r key; do
      if security find-generic-password -s "$SERVICE" -a "$key" >/dev/null 2>&1; then
        echo "skipping: $key already set (use 'bin/set-secret.sh $key' to overwrite)" >&2
        continue
      fi
      prompt_and_store "$key" || continue
    done < <(list_env_keys)
    ;;
  "")
    usage >&2
    exit 1
    ;;
  *)
    prompt_and_store "$1"
    ;;
esac
