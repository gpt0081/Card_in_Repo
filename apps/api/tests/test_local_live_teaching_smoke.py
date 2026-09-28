from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "local_live_teaching_smoke.sh"


def test_local_live_smoke_shell_is_syntactically_valid():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_local_live_smoke_requires_provider_endpoint_and_model():
    source = SCRIPT.read_text()
    assert "${TEACHING_LLM_ENDPOINT:?" in source
    assert "${TEACHING_LLM_MODEL:?" in source
    assert "TEACHING_LLM_API_KEY:?" not in source


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
