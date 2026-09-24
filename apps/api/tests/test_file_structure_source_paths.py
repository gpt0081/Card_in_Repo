from importlib import import_module

from fastapi.testclient import TestClient

from card_in_repo_api import app
from card_in_repo_api.store import MemoryAnalysisStore

client = TestClient(app)


def test_file_structure_preserves_analyzed_source_without_symbols():
    app_module = import_module("card_in_repo_api.app")
    store = MemoryAnalysisStore()
    app_module.set_store(store)

    result = app_module.store_completed_analysis(
        "fixture/barrel",
        "a" * 40,
        {
            "src/index.ts": "export { run } from './run';\n",
            "src/run.ts": "export function run() { return 1; }\n",
        },
        {
            "symbols": [
                {
                    "id": "symbol:run",
                    "name": "run",
                    "kind": "function",
                    "range": {"start": {"line": 1}, "end": {"line": 1}},
                    "parent_symbol_id": None,
                }
            ],
            "symbol_paths": {"symbol:run": "src/run.ts"},
            "calls": [],
        },
    )

    response = client.get(f"/v1/analyses/{result['id']}/files")
    assert response.status_code == 200
    files = {item["path"]: item["symbols"] for item in response.json()["files"]}
    assert set(files) == {"src/index.ts", "src/run.ts"}
    assert files["src/index.ts"] == []
    assert [symbol["name"] for symbol in files["src/run.ts"]] == ["run"]
