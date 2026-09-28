from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "local_live_teaching_smoke.sh"


def test_local_live_smoke_shell_is_syntactically_valid():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_local_live_smoke_requires_endpoint_but_can_discover_single_model():
    source = SCRIPT.read_text()
    assert "${TEACHING_LLM_ENDPOINT:?" in source
    assert "${TEACHING_LLM_MODEL:?" not in source
    assert '${TEACHING_LLM_ENDPOINT%/chat/completions}/models' in source
    assert 'TEACHING_LLM_MODELS_ENDPOINT' in source
    assert 'len(models) != 1' in source
    assert 'set TEACHING_LLM_MODEL explicitly' in source
    assert 'export TEACHING_LLM_MODEL' in source
    assert "TEACHING_LLM_API_KEY:?" not in source


def test_local_live_smoke_model_discovery_preserves_optional_auth_safely():
    source = SCRIPT.read_text()
    assert 'os.environ.get("TEACHING_LLM_API_KEY", "").strip()' in source
    assert 'parsed.scheme not in {"http", "https"}' in source
    assert 'loopback_hosts = {"localhost", "127.0.0.1", "::1"}' in source
    guard = 'if api_key and parsed.scheme != "https" and parsed.hostname.lower() not in loopback_hosts:'
    authorization = 'headers["Authorization"] = f"Bearer {api_key}"'
    assert guard in source
    assert authorization in source
    assert source.index(guard) < source.index(authorization)


def test_local_live_smoke_provisions_disposable_pgvector_by_default():
    source = SCRIPT.read_text()
    assert "pgvector/pgvector:pg16" in source
    assert "127.0.0.1:${POSTGRES_PORT}:5432" in source
    assert "pg_isready" in source
    assert "docker rm -f" in source
    assert "trap cleanup EXIT" in source


def test_local_live_smoke_can_use_existing_postgres_and_real_smoke_script():
    source = SCRIPT.read_text()
    assert "LIVE_TEACHING_DATABASE_URL" in source
    assert 'export DATABASE_URL' in source
    assert 'apps/api/scripts/live_teaching_smoke.py' in source
    assert 'TEACHING_SMOKE_LEVEL="${TEACHING_SMOKE_LEVEL:-all}"' in source


def test_local_live_smoke_uses_disposable_virtualenv_instead_of_host_pip():
    source = SCRIPT.read_text()
    assert 'python3 -m venv "$VENV_DIR/venv"' in source
    assert 'PYTHON="$VENV_DIR/venv/bin/python"' in source
    assert '"$PYTHON" -m pip install -e "$ROOT/packages/analyzer"' in source
    assert '"$PYTHON" -m pip install -e "$ROOT/apps/api"' in source
    assert '"$PYTHON" "$ROOT/apps/api/scripts/live_teaching_smoke.py"' in source
    assert 'python3 -m pip install' not in source
    assert 'rm -rf "$VENV_DIR"' in source
