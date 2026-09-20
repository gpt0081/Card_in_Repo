from pathlib import Path

from card_in_repo_analyzer import analyze_python, analyze_repository, build_feature_map


FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def test_builds_source_backed_flow_from_resolved_calls_only():
    facts = analyze_python("sample.py", FIXTURE.read_text())
    features = build_feature_map(facts)

    by_name = {feature["name"]: feature for feature in features}
    entry = by_name["entry"]

    assert [step["symbol_name"] for step in entry["flow_steps"]] == [
        "entry",
        "load_user",
        "normalize",
    ]
    assert entry["provenance"] == "deterministic-resolved-call-graph"
    assert all(step["range"]["start"]["line"] > 0 for step in entry["flow_steps"])
    assert "external_client.fetch" not in {
        step["symbol_name"] for step in entry["flow_steps"]
    }


def test_cross_file_typescript_flow_preserves_repository_paths():
    facts = analyze_repository({
        "src/main.ts": "import { loadUser } from './services/user';\nfunction entry() { return loadUser(); }\n",
        "src/services/user.ts": "export function loadUser() { return normalize(); }\nfunction normalize() { return 'ok'; }\n",
    })
    features = build_feature_map(facts)

    entry = next(feature for feature in features if feature["name"] == "entry")
    assert [(step["symbol_name"], step["path"]) for step in entry["flow_steps"]] == [
        ("entry", "src/main.ts"),
        ("loadUser", "src/services/user.ts"),
        ("normalize", "src/services/user.ts"),
    ]
    assert entry["provenance"] == "deterministic-resolved-call-graph"


def test_ambiguous_same_name_call_is_not_resolved():
    source = '''
def duplicate():
    return 1

def duplicate():
    return 2

def entry():
    return duplicate()
'''
    facts = analyze_python("ambiguous.py", source)
    call = next(call for call in facts["calls"] if call["callee"] == "duplicate")

    assert call["resolved_target_id"] is None
    assert any(warning["code"] == "AMBIGUOUS_CALL_TARGET" for warning in facts["warnings"])
