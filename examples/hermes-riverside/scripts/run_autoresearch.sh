#!/usr/bin/env bash
# Nightly autoresearch driver. Called by launchd (see
# scripts/com.sgridworks.hermes-autoresearch.plist.template).
#
# Preconditions this script assumes:
#   - Runs under your user account on mini1
#   - REPO_ROOT is a writable checkout of Dynamic-Network-Model
#   - ~/.hermes/autoresearch.env exists and is 700 perms, containing at least
#     GITHUB_TOKEN and optionally OLLAMA_BASE_URL
#   - .venv exists under examples/hermes-riverside/ with the project installed
#
# Safety posture:
#   - auto_push is controlled by the --auto-push flag (default: off). Keep it
#     off until you have watched several successful iterations locally.
#   - logs go to ~/.hermes/logs/autoresearch-YYYYMMDD.log with rotation

set -euo pipefail

REPO_ROOT="${HERMES_REPO_ROOT:-$HOME/Projects/Dynamic-Network-Model}"
ENV_FILE="${HERMES_ENV_FILE:-$HOME/.hermes/autoresearch.env}"
LOG_DIR="${HERMES_LOG_DIR:-$HOME/.hermes/logs}"
AUTO_PUSH="${HERMES_AUTO_PUSH:-false}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/autoresearch-$(date +%Y%m%d).log"

exec >> "$LOG_FILE" 2>&1

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) autoresearch start ==="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 2
fi

# Export every KEY=value line from the env file as an environment variable so
# the Python process inherits it. `source` alone only creates shell variables,
# which don't propagate to child processes. `set -a` (allexport) flips the
# "auto-export" flag for the duration of the source.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN not set in $ENV_FILE" >&2
  exit 3
fi

cd "$REPO_ROOT/examples/hermes-riverside"

# Use the fine-grained PAT for any git push the loop decides to perform.
# Only effective when --auto-push is on.
git config --local credential.helper '!f() { printf "username=x-access-token\npassword=%s\n" "$GITHUB_TOKEN"; }; f'

PUSH_FLAG="--no-auto-push"
if [[ "$AUTO_PUSH" == "true" ]]; then
  PUSH_FLAG="--auto-push"
fi

.venv/bin/python -m hermes.cli autoresearch run \
  --repo-root "$REPO_ROOT" \
  --targets-dir examples/hermes-riverside/hermes/agent \
  --pairs-path examples/hermes-riverside/evals/qa_pairs.yaml \
  --killswitch-path examples/hermes-riverside/runs/autoresearch_state.json \
  --ledger-path examples/hermes-riverside/public/autoresearch-ledger.json \
  --runs-dir examples/hermes-riverside/runs/autoresearch \
  --default-branch main \
  $PUSH_FLAG

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) autoresearch end ==="

# Simple log rotation: keep last 14 days
find "$LOG_DIR" -name 'autoresearch-*.log' -type f -mtime +14 -delete 2>/dev/null || true
