from pathlib import Path


def test_compose_forwards_live_teaching_configuration_to_api() -> None:
    compose = (Path(__file__).resolve().parents[3] / "compose.yml").read_text(encoding="utf-8")

    required = (
        "TEACHING_LLM_ENDPOINT: ${TEACHING_LLM_ENDPOINT:-}",
        "TEACHING_LLM_MODEL: ${TEACHING_LLM_MODEL:-}",
        "TEACHING_LLM_API_KEY: ${TEACHING_LLM_API_KEY:-}",
    )
    api_section = compose.split("  api:\n", 1)[1].split("  worker:\n", 1)[0]

    for setting in required:
        assert setting in api_section
