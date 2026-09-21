from card_in_repo_analyzer import analyze_javascript, analyze_python, analyze_typescript, split_symbol
from card_in_repo_analyzer.card_splitter import split_python_symbol


def _function(source: str):
    facts = analyze_python("sample.py", source)
    return next(symbol for symbol in facts["symbols"] if symbol["kind"] == "function")


def _ecmascript_function(source: str, path: str):
    facts = analyze_typescript(path, source) if path.endswith((".ts", ".tsx")) else analyze_javascript(path, source)
    return next(symbol for symbol in facts["symbols"] if symbol["kind"] == "function")


def test_short_function_stays_whole():
    source = "def tiny():\n    value = 1\n    return value\n"
    symbol = _function(source)
    assert split_python_symbol(source, symbol, max_lines=10) == [
        {"start_line": 1, "end_line": 3}
    ]


def test_long_function_splits_between_statements_not_arbitrary_lines():
    source = """def work():
    first = (
        1
        + 2
    )
    second = (
        3
        + 4
    )
    return first + second
"""
    symbol = _function(source)
    segments = split_python_symbol(source, symbol, max_lines=5)

    assert segments == [
        {"start_line": 1, "end_line": 5, "index": 0, "count": 2},
        {"start_line": 6, "end_line": 10, "index": 1, "count": 2},
    ]


def test_oversized_single_statement_is_never_cut_mid_syntax():
    source = """def work():
    value = (
        1
        + 2
        + 3
        + 4
    )
"""
    symbol = _function(source)
    assert split_python_symbol(source, symbol, max_lines=3) == [
        {"start_line": 1, "end_line": 7, "index": 0, "count": 1}
    ]


def test_long_typescript_function_splits_at_statement_boundaries():
    source = """function work() {
  const first = (
    1
    + 2
  );
  const second = (
    3
    + 4
  );
  return first + second;
}
"""
    symbol = _ecmascript_function(source, "sample.ts")
    assert split_symbol(source, symbol, "sample.ts", max_lines=5) == [
        {"start_line": 1, "end_line": 5, "index": 0, "count": 3},
        {"start_line": 6, "end_line": 9, "index": 1, "count": 3},
        {"start_line": 10, "end_line": 11, "index": 2, "count": 3},
    ]


def test_long_javascript_function_never_splits_inside_statement():
    source = """function work() {
  const value = (
    1
    + 2
    + 3
    + 4
  );
}
"""
    symbol = _ecmascript_function(source, "sample.js")
    assert split_symbol(source, symbol, "sample.js", max_lines=3) == [
        {"start_line": 1, "end_line": 8, "index": 0, "count": 1}
    ]
