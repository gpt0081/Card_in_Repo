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


def test_typescript_class_functions_are_visible_with_class_ownership():
    facts = analyze_repository({
        "src/service.ts": "class Service {\n  async execute() { return 'ok'; }\n  refresh = () => 'fresh';\n}\n",
    })
    features = build_feature_map(facts)

    by_name = {feature["name"]: feature for feature in features}
    assert {"execute", "refresh"} <= set(by_name)
    for name in ("execute", "refresh"):
        step = by_name[name]["flow_steps"][0]
        assert step["path"] == "src/service.ts"
        assert step["owner_symbol_name"] == "Service"
        assert step["owner_symbol_id"]


def test_nested_local_function_does_not_become_repository_feature():
    facts = analyze_repository({
        "src/main.ts": "function entry() { function helper() { return 1; } return helper(); }\n",
    })
    features = build_feature_map(facts)

    assert "entry" in {feature["name"] for feature in features}
    assert "helper" not in {feature["name"] for feature in features}


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
