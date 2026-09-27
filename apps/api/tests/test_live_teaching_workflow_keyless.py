from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = API_ROOT.parents[1] / ".github" / "workflows" / "live-teaching-smoke.yml"


def test_live_smoke_workflow_does_not_require_api_key():
    workflow = WORKFLOW_PATH.read_text()
    assert "TEACHING_LLM_API_KEY: ${{ secrets.TEACHING_LLM_API_KEY }}" in workflow
    assert 'test -n "$TEACHING_LLM_ENDPOINT"' in workflow
    assert 'test -n "$TEACHING_LLM_MODEL"' in workflow
    assert 'test -n "$TEACHING_LLM_API_KEY"' not in workflow


def test_live_smoke_workflow_forwards_private_http_opt_in():
    workflow = WORKFLOW_PATH.read_text()
    assert (
        "CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING: "
        "${{ vars.CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING }}"
    ) in workflow


def test_private_live_smoke_requires_a_networked_runner_and_database():
    workflow = WORKFLOW_PATH.read_text()
    assert "private-provider:" in workflow
    assert "runs-on: ${{ vars.LIVE_TEACHING_RUNNER || 'ubuntu-latest' }}" in workflow
    assert "LIVE_TEACHING_RUNNER: ${{ vars.LIVE_TEACHING_RUNNER }}" in workflow
    assert "DATABASE_URL: ${{ vars.LIVE_TEACHING_DATABASE_URL }}" in workflow
    assert 'test -n "$LIVE_TEACHING_RUNNER"' in workflow
    assert 'test -n "$DATABASE_URL"' in workflow
    assert "Private teaching smoke requires LIVE_TEACHING_RUNNER" in workflow
    assert "Private teaching smoke requires LIVE_TEACHING_DATABASE_URL" in workflow


def test_private_live_smoke_does_not_depend_on_linux_service_containers():
    workflow = WORKFLOW_PATH.read_text()
    private_job = workflow.split("  private-provider:", 1)[1]
    assert "services:" not in private_job
    assert "pgvector/pgvector:pg16" not in private_job


def test_public_live_smoke_keeps_isolated_pgvector_service():
    workflow = WORKFLOW_PATH.read_text()
    public_job = workflow.split("  public-provider:", 1)[1].split("  private-provider:", 1)[0]
    assert "runs-on: ubuntu-latest" in public_job
    assert "services:" in public_job
    assert "pgvector/pgvector:pg16" in public_job
