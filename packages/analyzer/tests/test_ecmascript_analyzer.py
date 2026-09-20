from card_in_repo_analyzer.ecmascript import analyze_javascript, analyze_typescript


def test_javascript_extracts_functions_imports_calls_and_async():
    result = analyze_javascript("src/app.js", """import { read } from './io.js';
function helper() { return 1; }
const run = async () => helper();
class Service { execute() { return run(); } }
""")
    by_name = {symbol["name"]: symbol for symbol in result["symbols"]}
    assert result["file"]["language"] == "javascript"
    assert {"helper", "run", "Service"} <= set(by_name)
    assert by_name["run"]["is_async"] is True
    assert result["imports"][0]["text"].startswith("import { read }")
    helper_call = next(call for call in result["calls"] if call["callee"] == "helper")
    assert helper_call["resolved_target_id"] == by_name["helper"]["id"]
    assert all(symbol["range"]["start"]["line"] >= 1 for symbol in result["symbols"])


def test_typescript_and_tsx_use_their_grammars():
    ts = analyze_typescript("src/app.ts", """type Id = string;
export async function load(id: Id): Promise<Id> { return id; }
const invoke = (id: Id) => load(id);
""")
    assert ts["file"]["language"] == "typescript"
    assert {symbol["name"] for symbol in ts["symbols"]} >= {"load", "invoke"}
    assert next(symbol for symbol in ts["symbols"] if symbol["name"] == "load")["is_async"] is True
    assert next(call for call in ts["calls"] if call["callee"] == "load")["resolved_target_id"] is not None

    tsx = analyze_typescript("src/view.tsx", "const View = () => <main>Hello</main>;", tsx=True)
    assert tsx["file"]["language"] == "tsx"
    assert tsx["symbols"][0]["name"] == "View"
    assert not tsx["warnings"]


def test_member_calls_are_not_falsely_resolved():
    result = analyze_javascript("src/member.js", "function run() {}\nclient.run();\n")
    member_call = next(call for call in result["calls"] if call["callee"] == "client.run")
    assert member_call["resolved_target_id"] is None
