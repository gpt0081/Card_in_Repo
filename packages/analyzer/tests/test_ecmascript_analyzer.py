from card_in_repo_analyzer.ecmascript import analyze_javascript, analyze_typescript


def test_javascript_extracts_functions_imports_calls_and_async():
    result = analyze_javascript("src/app.js", """import { read } from './io.js';
function helper() { return 1; }
const run = async () => helper();
class Service { execute() { return run(); } }
""")
    by_name = {symbol["name"]: symbol for symbol in result["symbols"]}
    assert result["file"]["language"] == "javascript"
    assert {"helper", "run", "Service", "execute"} <= set(by_name)
    assert by_name["run"]["is_async"] is True
    assert by_name["execute"]["parent_symbol_id"] == by_name["Service"]["id"]
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


def test_class_methods_and_arrow_fields_are_function_sized_symbols():
    result = analyze_typescript("src/service.ts", """class Service {
  async execute() { return this.finish(); }
  finish = () => 1;
  transform = async (value: number) => value + 1;
}
""")
    by_name = {symbol["name"]: symbol for symbol in result["symbols"]}
    assert {"Service", "execute", "finish", "transform"} <= set(by_name)
    for name in ("execute", "finish", "transform"):
        assert by_name[name]["kind"] == "function"
        assert by_name[name]["parent_symbol_id"] == by_name["Service"]["id"]
    assert by_name["execute"]["is_async"] is True
    assert by_name["transform"]["is_async"] is True
    member_call = next(call for call in result["calls"] if call["callee"] == "this.finish")
    assert member_call["source_symbol_id"] == by_name["execute"]["id"]
    assert member_call["resolved_target_id"] == by_name["finish"]["id"]


def test_this_member_resolution_stays_within_owning_class():
    result = analyze_javascript("src/classes.js", """class Alpha {
  run() { return this.finish(); }
  finish() { return 1; }
}
class Beta {
  finish() { return 2; }
}
""")
    alpha = next(symbol for symbol in result["symbols"] if symbol["name"] == "Alpha")
    alpha_finish = next(symbol for symbol in result["symbols"] if symbol["name"] == "finish" and symbol["parent_symbol_id"] == alpha["id"])
    member_call = next(call for call in result["calls"] if call["callee"] == "this.finish")
    assert member_call["resolved_target_id"] == alpha_finish["id"]


def test_member_calls_are_not_falsely_resolved():
    result = analyze_javascript("src/member.js", "function run() {}\nclient.run();\n")
    member_call = next(call for call in result["calls"] if call["callee"] == "client.run")
    assert member_call["resolved_target_id"] is None
