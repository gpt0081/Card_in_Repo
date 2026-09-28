#!/usr/bin/env bash
set -euo pipefail

: "${TEACHING_LLM_ENDPOINT:?Set TEACHING_LLM_ENDPOINT to the OpenAI-compatible chat completions endpoint}"
: "${TEACHING_LLM_MODEL:?Set TEACHING_LLM_MODEL to the loaded model name}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="${CARD_IN_REPO_SMOKE_POSTGRES_CONTAINER:-card-in-repo-live-smoke}"
POSTGRES_PORT="${CARD_IN_REPO_SMOKE_POSTGRES_PORT:-55432}"
DATABASE_URL="${LIVE_TEACHING_DATABASE_URL:-postgresql://card_in_repo:card_in_repo@127.0.0.1:${POSTGRES_PORT}/card_in_repo_live_smoke}"
STARTED_POSTGRES=0

cleanup() {
  if [[ "$STARTED_POSTGRES" == "1" ]]; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

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
  for _ in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" pg_isready -U card_in_repo -d card_in_repo_live_smoke >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  docker exec "$CONTAINER_NAME" pg_isready -U card_in_repo -d card_in_repo_live_smoke >/dev/null
fi

export DATABASE_URL
export TEACHING_SMOKE_LEVEL="${TEACHING_SMOKE_LEVEL:-all}"

if [[ "$TEACHING_LLM_ENDPOINT" == http://127.0.0.1:* || "$TEACHING_LLM_ENDPOINT" == http://localhost:* || "$TEACHING_LLM_ENDPOINT" == http://\[::1\]:* ]]; then
  : # loopback HTTP is allowed by the runtime without a private-network opt-in
fi

python3 -m pip install -e "$ROOT/apps/api"
python3 "$ROOT/apps/api/scripts/live_teaching_smoke.py"
