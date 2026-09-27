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
