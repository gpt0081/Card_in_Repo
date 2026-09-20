# JavaScript / TypeScript static-analysis slice

## Goal

Extend Card in Repo's deterministic fact layer from Python to JavaScript and TypeScript without allowing LLM output to become source-of-truth program structure.

## First implementation slice

1. Add the official Tree-sitter JavaScript and TypeScript Python grammar bindings to the analyzer package.
2. Introduce `analyze_javascript(path, source_text)` and `analyze_typescript(path, source_text)` behind a shared ECMAScript-family walker.
3. Preserve the existing analyzer schema: file identity/content hash, symbols, imports, calls, warnings, source ranges, and conservative call-target resolution.
4. Recognize at minimum:
   - function declarations and generator functions;
   - class declarations;
   - arrow/function expressions assigned to lexical variables;
   - ES module imports;
   - call expressions;
   - async functions;
   - TypeScript declarations that contain executable functions/classes.
5. Never fabricate a resolved call target. Resolve only a bare identifier with exactly one same-file symbol candidate. Emit ambiguity warnings otherwise.
6. Add fixture-driven tests for `.js`, `.jsx`, `.ts`, and `.tsx`, including parse-recovery behavior and nested symbols.
7. Route repository analysis by extension only after the language analyzers have direct unit-test coverage.

## Acceptance evidence

The analyzer workflow must prove deterministic extraction for JS/TS fixtures. Repository-level tests must then prove a mixed Python + JS/TS repository produces one coherent fact graph without an LLM dependency.

## Dependency / provenance policy

Use the official `tree-sitter-javascript` and `tree-sitter-typescript` grammar bindings, subject to verification of their upstream licenses before adding them to `pyproject.toml`. Record exact package versions and upstream repository/license references when the dependencies land. Do not copy parser implementation code into Card in Repo.

## Non-goals for this slice

Cross-file/module resolution, bundler semantics, runtime evaluation, package-manager dependency resolution, C/Rust parsing, and sandbox execution remain later work. JSX/TSX syntax should parse in this phase, but framework-specific semantic inference is explicitly not a fact-layer responsibility.
