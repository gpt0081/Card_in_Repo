from card_in_repo_analyzer import analyze_repository


def _call(facts, callee):
    return next(call for call in facts["calls"] if call["callee"] == callee)


def test_repository_analysis_resolves_explicit_tsconfig_wildcard_path_alias():
    facts = analyze_repository({
        "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@core/*":["src/core/*"]}}}',
        "src/app.ts": "import { loadUser as load } from '@core/user';\nexport function boot() { return load(); }\n",
        "src/core/user.ts": "export function loadUser() { return 1; }\n",
    })

    call = _call(facts, "load")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "src/core/user.ts"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_resolves_exact_tsconfig_path_alias():
    facts = analyze_repository({
        "web/tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@services":["src/services/index.ts"]}}}',
        "web/src/app.ts": "import { load } from '@services';\nexport function boot() { return load(); }\n",
        "web/src/services/index.ts": "export function load() { return 1; }\n",
    })

    call = _call(facts, "load")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "web/src/services/index.ts"


def test_repository_analysis_does_not_guess_ambiguous_tsconfig_targets():
    facts = analyze_repository({
        "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@core/*":["src/core/*","generated/core/*"]}}}',
        "src/app.ts": "import { load } from '@core/user';\nexport function boot() { return load(); }\n",
        "src/core/user.ts": "export function load() { return 1; }\n",
        "generated/core/user.ts": "export function load() { return 2; }\n",
    })

    assert _call(facts, "load")["resolved_target_id"] is None


def test_repository_analysis_does_not_apply_sibling_tsconfig():
    facts = analyze_repository({
        "packages/a/tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@core/*":["src/core/*"]}}}',
        "packages/a/src/core/user.ts": "export function load() { return 1; }\n",
        "packages/b/src/app.ts": "import { load } from '@core/user';\nexport function boot() { return load(); }\n",
    })

    assert _call(facts, "load")["resolved_target_id"] is None
