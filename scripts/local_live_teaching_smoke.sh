#!/usr/bin/env bash
set -euo pipefail

: "${TEACHING_LLM_ENDPOINT:?Set TEACHING_LLM_ENDPOINT to the OpenAI-compatible chat completions endpoint}"
: "${TEACHING_LLM_MODEL:?Set TEACHING_LLM_MODEL to the loaded model name}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="${CARD_IN_REPO_SMOKE_POSTGRES_CONTAINER:-card-in-repo-live-smoke}"
POSTGRES_PORT="${CARD_IN_REPO_SMOKE_POSTGRES_PORT:-55432}"
DATABASE_URL="${LIVE_TEACHING_DATABASE_URL:-postgresql://card_in_repo:card_in_repo@127.0.0.1:${POSTGRES_PORT}/card_in_repo_live_smoke}"
STARTED_POSTGRES=0
VENV_DIR=""

cleanup() {
  if [[ "$STARTED_POSTGRES" == "1" ]]; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  if [[ -n "$VENV_DIR" && -d "$VENV_DIR" ]]; then
    rm -rf "$VENV_DIR"
  fi
}
trap cleanup EXIT

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required for the live teaching smoke" >&2
  exit 1
}

if [[ -z "${LIVE_TEACHING_DATABASE_URL:-}" ]]; then
  command -v docker >/dev/null 2>&1 || {
    echo "docker is required unless LIVE_TEACHING_DATABASE_URL points at an existing PostgreSQL + pgvector database" >&2
    exit 1
  }
  docker info >/dev/null 2>&1 || {
    echo "docker is installed but its daemon is not reachable" >&2
    exit 1
  }
  if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    echo "refusing to reuse existing container $CONTAINER_NAME; remove it or set CARD_IN_REPO_SMOKE_POSTGRES_CONTAINER" >&2
    exit 1
  fi
  docker run -d --rm \
    --name "$CONTAINER_NAME" \
    -e POSTGRES_USER=card_in_repo \
    -e POSTGRES_PASSWORD=card_in_repo \
    -e POSTGRES_DB=card_in_repo_live_smoke \
    -p "127.0.0.1:${POSTGRES_PORT}:5432" \
    pgvector/pgvector:pg16 >/dev/null
  STARTED_POSTGRES=1

  echo "waiting for disposable pgvector PostgreSQL on port ${POSTGRES_PORT}..."
  attempts=0
  while (( attempts < 30 )); do
    if docker exec "$CONTAINER_NAME" pg_isready -U card_in_repo -d card_in_repo_live_smoke >/dev/null 2>&1; then
      break
    fi
    attempts=$((attempts + 1))
    sleep 1
  done
  docker exec "$CONTAINER_NAME" pg_isready -U card_in_repo -d card_in_repo_live_smoke >/dev/null
fi

export DATABASE_URL
export TEACHING_SMOKE_LEVEL="${TEACHING_SMOKE_LEVEL:-all}"

# Keep the proof path independent of the host Python installation. Homebrew and
# other externally managed Python installs can reject direct pip writes (PEP 668),
# and a smoke test should not mutate the developer's global environment anyway.
VENV_DIR="$(mktemp -d "${TMPDIR:-/tmp}/card-in-repo-live-smoke.XXXXXX")"
python3 -m venv "$VENV_DIR/venv"
PYTHON="$VENV_DIR/venv/bin/python"
"$PYTHON" -m pip install -e "$ROOT/packages/analyzer"
"$PYTHON" -m pip install -e "$ROOT/apps/api"
"$PYTHON" "$ROOT/apps/api/scripts/live_teaching_smoke.py"
