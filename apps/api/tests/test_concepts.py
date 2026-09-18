from card_in_repo_api.concepts import build_concept_candidates


def test_concepts_are_derived_only_from_static_evidence():
    facts = {
        "symbols": [
            {"id": "sym:entry", "name": "entry", "range": {"start": {"line": 1}, "end": {"line": 2}}},
            {"id": "sym:load", "name": "load", "range": {"start": {"line": 4}, "end": {"line": 5}}},
        ],
        "symbol_paths": {"sym:entry": "app.py", "sym:load": "service.py"},
    }
    features = [{
        "id": "feature:entry",
        "name": "entry",
        "flow_steps": [
            {"symbol_id": "sym:entry", "relation": "entry", "order": 0},
            {"symbol_id": "sym:load", "relation": "calls", "order": 1},
        ],
    }]

    concepts = build_concept_candidates(facts, features)

    assert len(concepts) == 1
    assert concepts[0]["id"] == "concept:flow:feature:entry"
    assert concepts[0]["kind"] == "execution_flow"
    assert concepts[0]["explanation"] is None
    assert concepts[0]["evidence"] == [
        {"symbol_id": "sym:entry", "symbol_name": "entry", "path": "app.py", "range": facts["symbols"][0]["range"], "relation": "entry", "order": 0},
        {"symbol_id": "sym:load", "symbol_name": "load", "path": "service.py", "range": facts["symbols"][1]["range"], "relation": "calls", "order": 1},
    ]


def test_concepts_are_not_invented_without_resolved_symbols():
    features = [{"id": "feature:ghost", "name": "ghost", "flow_steps": [{"symbol_id": "missing", "order": 0}]}]
    assert build_concept_candidates({"symbols": [], "symbol_paths": {}}, features) == []
