from pathlib import Path

from card_in_repo_analyzer import analyze_python


FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def test_extracts_symbols_imports_calls_and_async_fact():
    result = analyze_python("sample.py", FIXTURE.read_text())

    assert result["schema_version"] == 1
    assert result["file"]["content_hash"].startswith("sha256:")
    assert [symbol["name"] for symbol in result["symbols"]] == ["normalize", "load_user", "entry"]
    assert result["symbols"][1]["is_async"] is True
    assert result["imports"][0]["text"] == "import json"

    calls = {call["callee"]: call for call in result["calls"]}
    assert calls["normalize"]["resolved_target_id"].endswith(":function:normalize:4")
    assert calls["load_user"]["resolved_target_id"].endswith(":function:load_user:8")
    assert calls["external_client.fetch"]["resolved_target_id"] is None
    assert calls["normalize"]["source_symbol_id"].endswith(":function:load_user:8")
    assert result["warnings"] == []
