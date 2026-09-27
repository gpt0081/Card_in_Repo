from pathlib import Path


REQUIRED_TEACHING_SETTINGS = (
    "CARD_IN_REPO_TEACHING_PROVIDER: ${CARD_IN_REPO_TEACHING_PROVIDER:-none}",
    "CARD_IN_REPO_ALLOW_TEST_PROVIDER: ${CARD_IN_REPO_ALLOW_TEST_PROVIDER:-0}",
    "CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING: ${CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING:-0}",
    "TEACHING_LLM_ENDPOINT: ${TEACHING_LLM_ENDPOINT:-}",
    "TEACHING_LLM_MODEL: ${TEACHING_LLM_MODEL:-}",
    "TEACHING_LLM_API_KEY: ${TEACHING_LLM_API_KEY:-}",
    "TEACHING_LLM_TIMEOUT_SECONDS: ${TEACHING_LLM_TIMEOUT_SECONDS:-30}",
    "TEACHING_LLM_MAX_RESPONSE_BYTES: ${TEACHING_LLM_MAX_RESPONSE_BYTES:-1048576}",
)


def _compose() -> str:
    return (Path(__file__).resolve().parents[3] / "compose.yml").read_text(encoding="utf-8")


def test_compose_forwards_live_teaching_configuration_to_api() -> None:
    api_section = _compose().split("  api:\n", 1)[1].split("  worker:\n", 1)[0]

    for setting in REQUIRED_TEACHING_SETTINGS:
        assert setting in api_section


def test_compose_forwards_live_teaching_configuration_to_worker() -> None:
    worker_section = _compose().split("  worker:\n", 1)[1].split("  web:\n", 1)[0]

    for setting in REQUIRED_TEACHING_SETTINGS:
        assert setting in worker_section
