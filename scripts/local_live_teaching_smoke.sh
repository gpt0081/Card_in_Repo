#!/usr/bin/env bash
set -euo pipefail

: "${TEACHING_LLM_ENDPOINT:?Set TEACHING_LLM_ENDPOINT to the OpenAI-compatible chat completions endpoint}"

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

# LM Studio and llama.cpp expose the OpenAI-compatible /v1/models endpoint. When
# exactly one model is loaded, discover it so the first real-model proof needs
# only the chat endpoint. Never guess when multiple models are available.
if [[ -z "${TEACHING_LLM_MODEL:-}" ]]; then
  MODELS_ENDPOINT="${TEACHING_LLM_MODELS_ENDPOINT:-${TEACHING_LLM_ENDPOINT%/chat/completions}/models}"
  export MODELS_ENDPOINT
  TEACHING_LLM_MODEL="$(python3 - <<'PY'
import json
import os
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

endpoint = os.environ["MODELS_ENDPOINT"]
parsed = urlparse(endpoint)
api_key = os.environ.get("TEACHING_LLM_API_KEY", "").strip()
loopback_hosts = {"localhost", "127.0.0.1", "::1"}

# Discovery happens before the API runtime gets a chance to validate the chat
# endpoint. Keep bearer credentials behind the same minimum transport boundary:
# HTTPS anywhere, or cleartext HTTP only on the local loopback interface.
if parsed.scheme not in {"http", "https"} or not parsed.hostname:
    print(f"refusing invalid model-discovery URL: {endpoint}", file=sys.stderr)
    raise SystemExit(2)
if api_key and parsed.scheme != "https" and parsed.hostname.lower() not in loopback_hosts:
    print(
        "refusing to send TEACHING_LLM_API_KEY to a non-HTTPS, non-loopback "
        f"model-discovery endpoint: {endpoint}",
        file=sys.stderr,
    )
    print("use HTTPS, a loopback endpoint, or set TEACHING_LLM_MODEL explicitly", file=sys.stderr)
    raise SystemExit(2)

headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
try:
    with urlopen(Request(endpoint, headers=headers), timeout=5) as response:
        payload = json.load(response)
except Exception as exc:
    print(f"could not discover a model from {endpoint}: {exc}", file=sys.stderr)
    print("set TEACHING_LLM_MODEL explicitly to bypass discovery", file=sys.stderr)
    raise SystemExit(2)
models = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")]
if len(models) != 1:
    shown = ", ".join(models) if models else "none"
    print(f"model discovery requires exactly one loaded model; found: {shown}", file=sys.stderr)
    print("set TEACHING_LLM_MODEL explicitly", file=sys.stderr)
    raise SystemExit(2)
print(models[0])
PY
)"
  export TEACHING_LLM_MODEL
  echo "discovered teaching model: ${TEACHING_LLM_MODEL}"
fi

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
