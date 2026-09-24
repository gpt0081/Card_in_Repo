from card_in_repo_analyzer import analyze_repository


def test_repository_analysis_resolves_typescript_namespace_import_member_call():
    facts = analyze_repository({
        "src/app.ts": "import * as Service from './service';\nexport function run() { return Service.loadUser(); }\n",
        "src/service.ts": "export function loadUser() { return 1; }\n",
    })

    call = next(call for call in facts["calls"] if call["callee"] == "Service.loadUser")
    assert call["callee_kind"] == "member"
    assert call["receiver"] == "Service"
    assert call["member_name"] == "loadUser"
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "src/service.ts"
    assert call["resolution"] == "repository-import"


def test_namespace_member_call_does_not_guess_unimported_receiver():
    facts = analyze_repository({
        "src/app.ts": "export function run() { return Service.loadUser(); }\n",
        "src/service.ts": "export function loadUser() { return 1; }\n",
    })

    call = next(call for call in facts["calls"] if call["callee"] == "Service.loadUser")
    assert call["resolved_target_id"] is None
