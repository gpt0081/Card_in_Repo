from card_in_repo_analyzer import analyze_python_repository, analyze_repository


def test_repository_analysis_resolves_explicit_cross_file_import():
    facts = analyze_python_repository({
        "app.py": "from services.user import load_user\n\ndef run():\n    return load_user()\n",
        "services/user.py": "def load_user():\n    return {'id': 1}\n",
    })

    call = next(call for call in facts["calls"] if call["callee"] == "load_user")
    target = next(symbol for symbol in facts["symbols"] if symbol["id"] == call["resolved_target_id"])
    assert target["name"] == "load_user"
    assert facts["symbol_paths"][target["id"]] == "services/user.py"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_resolves_package_relative_imports():
    facts = analyze_python_repository({
        "shop/__init__.py": "",
        "shop/api.py": "from .services.user import load_user\n\ndef run():\n    return load_user()\n",
        "shop/services/user.py": "def load_user():\n    return {'id': 1}\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load_user")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "shop/services/user.py"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_resolves_parent_package_relative_imports():
    facts = analyze_python_repository({
        "shop/__init__.py": "",
        "shop/pages/home.py": "from ..services.user import load_user as load\n\ndef home():\n    return load()\n",
        "shop/services/user.py": "def load_user():\n    return {'id': 1}\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "shop/services/user.py"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_does_not_guess_unimported_same_name():
    facts = analyze_python_repository({
        "app.py": "def run():\n    return load_user()\n",
        "services/user.py": "def load_user():\n    return 1\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load_user")
    assert call["resolved_target_id"] is None


def test_repository_analysis_is_deterministic_by_path():
    facts = analyze_python_repository({
        "z.py": "def zed():\n    return 1\n",
        "a.py": "def alpha():\n    return 1\n",
        "README.md": "ignored",
    })
    assert [file["path"] for file in facts["files"]] == ["a.py", "z.py"]


def test_repository_analysis_combines_python_javascript_typescript_and_tsx():
    facts = analyze_repository({
        "backend/app.py": "def serve():\n    return 1\n",
        "web/app.js": "export function boot() { return render(); }\nfunction render() { return 1; }\n",
        "web/model.ts": "export const load = async () => fetch('/api');\n",
        "web/view.tsx": "export const View = () => <main>Card</main>;\n",
        "README.md": "ignored",
    })

    assert [(file["path"], file["language"]) for file in facts["files"]] == [
        ("backend/app.py", "python"),
        ("web/app.js", "javascript"),
        ("web/model.ts", "typescript"),
        ("web/view.tsx", "tsx"),
    ]
    assert {symbol["name"] for symbol in facts["symbols"]} >= {"serve", "boot", "render", "load", "View"}
    assert set(facts["symbol_paths"].values()) == {"backend/app.py", "web/app.js", "web/model.ts", "web/view.tsx"}
    render_call = next(call for call in facts["calls"] if call["callee"] == "render")
    assert render_call["path"] == "web/app.js"
    assert render_call["resolved_target_id"] is not None


def test_repository_analysis_resolves_relative_typescript_named_import_with_alias():
    facts = analyze_repository({
        "web/app.ts": "import { loadUser as load } from './services/user';\nexport function boot() { return load(); }\n",
        "web/services/user.ts": "export function loadUser() { return 1; }\n",
    })

    call = next(call for call in facts["calls"] if call["callee"] == "load")
    target = next(symbol for symbol in facts["symbols"] if symbol["id"] == call["resolved_target_id"])
    assert target["name"] == "loadUser"
    assert facts["symbol_paths"][target["id"]] == "web/services/user.ts"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_resolves_parent_relative_javascript_index_import():
    facts = analyze_repository({
        "web/pages/home.js": "import { render } from '../ui';\nexport function home() { return render(); }\n",
        "web/ui/index.js": "export function render() { return 'ok'; }\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "render")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "web/ui/index.js"


def test_repository_analysis_resolves_named_default_typescript_import():
    facts = analyze_repository({
        "web/app.ts": "import load from './services/user';\nexport function boot() { return load(); }\n",
        "web/services/user.ts": "export default function loadUser() { return 1; }\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load")
    target = next(symbol for symbol in facts["symbols"] if symbol["id"] == call["resolved_target_id"])
    assert target["name"] == "loadUser"
    assert facts["symbol_paths"][target["id"]] == "web/services/user.ts"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_does_not_guess_anonymous_default_export():
    facts = analyze_repository({
        "web/app.ts": "import load from './services/user';\nexport function boot() { return load(); }\n",
        "web/services/user.ts": "export default () => 1;\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load")
    assert call["resolved_target_id"] is None


def test_repository_analysis_resolves_explicit_named_reexport_chain():
    facts = analyze_repository({
        "web/app.ts": "import { load as fetchUser } from './services';\nexport function boot() { return fetchUser(); }\n",
        "web/services/index.ts": "export { loadUser as load } from './user';\n",
        "web/services/user.ts": "export function loadUser() { return 1; }\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "fetchUser")
    target = next(symbol for symbol in facts["symbols"] if symbol["id"] == call["resolved_target_id"])
    assert target["name"] == "loadUser"
    assert facts["symbol_paths"][target["id"]] == "web/services/user.ts"
    assert call["resolution"] == "repository-import"


def test_repository_analysis_resolves_default_as_named_reexport():
    facts = analyze_repository({
        "web/app.ts": "import { load } from './services';\nexport function boot() { return load(); }\n",
        "web/services/index.ts": "export { default as load } from './user';\n",
        "web/services/user.ts": "export default function loadUser() { return 1; }\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "load")
    assert call["resolved_target_id"] is not None
    assert facts["symbol_paths"][call["resolved_target_id"]] == "web/services/user.ts"


def test_repository_analysis_does_not_follow_wildcard_reexport():
    facts = analyze_repository({
        "web/app.ts": "import { loadUser } from './services';\nexport function boot() { return loadUser(); }\n",
        "web/services/index.ts": "export * from './user';\n",
        "web/services/user.ts": "export function loadUser() { return 1; }\n",
    })
    call = next(call for call in facts["calls"] if call["callee"] == "loadUser")
    assert call["resolved_target_id"] is None


def test_repository_analysis_does_not_guess_package_or_ambiguous_extension_imports():
    facts = analyze_repository({
        "web/app.ts": "import { load } from 'pkg';\nimport { render } from './view';\nexport function boot() { load(); return render(); }\n",
        "web/view.ts": "export function render() { return 1; }\n",
        "web/view.tsx": "export function render() { return <main />; }\n",
        "web/pkg.ts": "export function load() { return 1; }\n",
    })
    load_call = next(call for call in facts["calls"] if call["callee"] == "load")
    render_call = next(call for call in facts["calls"] if call["callee"] == "render")
    assert load_call["resolved_target_id"] is None
    assert render_call["resolved_target_id"] is None
