from card_in_repo_analyzer import analyze_python_repository


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
