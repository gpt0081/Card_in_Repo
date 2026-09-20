# Dependency provenance

Card in Repo keeps deterministic parser dependencies explicit and records their upstream provenance before they enter the fact layer.

## Tree-sitter language grammars

| Package | Pinned version | Upstream | License | Purpose |
| --- | --- | --- | --- | --- |
| `tree-sitter-javascript` | `0.25.0` | https://github.com/tree-sitter/tree-sitter-javascript | MIT | JavaScript and JSX concrete syntax parsing |
| `tree-sitter-typescript` | `0.23.2` | https://github.com/tree-sitter/tree-sitter-typescript | MIT | TypeScript and TSX concrete syntax parsing |

The versions above correspond to the published Python grammar bindings. The grammar packages are dependencies only: Card in Repo does not copy their parser implementation into this repository. Static facts extracted from their concrete syntax trees remain subject to Card in Repo's conservative resolution rules, and LLM output is never treated as source-of-truth program structure.
