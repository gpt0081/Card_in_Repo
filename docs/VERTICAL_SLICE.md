# First Executable Vertical Slice

## Goal

Prove the product thesis with the smallest runnable path:

```text
public repository URL
  -> immutable commit resolved
  -> supported files analyzed
  -> symbols + conservative calls extracted
  -> one feature/flow map returned
  -> one function-sized card opened
  -> Basic explanation references concrete evidence
```

The slice is complete only when this path works against a small real public repository and automated tests cover the deterministic analyzer contract.

## API contract

### Start analysis

`POST /v1/analyses`

```json
{
  "repository_url": "https://github.com/owner/repo",
  "ref": "main"
}
```

Returns `202` with an analysis id and state.

### Poll analysis

`GET /v1/analyses/{analysis_id}`

States:
- `QUEUED`
- `RESOLVING`
- `FETCHING`
- `PARSING`
- `BUILDING_MAP`
- `GENERATING_BASIC_CARDS`
- `VERIFYING`
- `READY`
- `FAILED_RETRYABLE`
- `FAILED_TERMINAL`

Progress is descriptive, not a fake percentage unless the denominator is known.

### Feature map

`GET /v1/analyses/{analysis_id}/features`

Minimum response contains feature id/name/confidence and ordered flow steps. Every flow step references a symbol and source range.

### Card

`GET /v1/cards/{card_id}`

Minimum response contains repository, commit SHA, file path, source range, exact code excerpt, Basic explanation, concepts, evidence references, and verification state.

## Analyzer v0 contract

Input:
- repository metadata
- commit SHA
- path
- UTF-8 source
- language

Output:

```json
{
  "schema_version": 1,
  "analyzer_version": "...",
  "file": {
    "path": "src/example.py",
    "language": "python",
    "content_hash": "sha256:..."
  },
  "symbols": [],
  "imports": [],
  "calls": [],
  "warnings": []
}
```

A symbol requires stable local id, name, kind, start/end position, and containment. A call requires source symbol, textual callee, source range, and optional resolved target. Resolution confidence is explicit.

## Feature-map v0

Feature inference is intentionally conservative. Before sophisticated AI grouping exists, the first runnable implementation may construct feature candidates from entry points/modules plus deterministic call reachability. LLM-proposed labels may improve names but may not rewrite graph edges.

This is preferable to waiting for a perfect feature classifier because it exercises the actual product path while preserving the truth boundary.

## Card splitting v0

Default unit: one function/method.

Split only when a function exceeds the configured size threshold. Semantic split points must align to syntax nodes or statement groups; never cut an arbitrary line range merely to hit a token target. Every split card retains:
- parent symbol id
- exact source range
- preceding/following segment relationship
- feature/flow position

## Basic explanation contract

The teaching generator receives only:
- selected source excerpt
- surrounding signature/context needed for comprehension
- Fact Package subset
- current feature/flow position
- learner knowledge summary when available

Structured output:

```json
{
  "summary": "...",
  "why_it_exists": "...",
  "walkthrough": [
    {"evidence_ids": ["..."], "text": "..."}
  ],
  "concepts": ["..."],
  "prerequisites": ["..."]
}
```

Statements about repository behavior require evidence ids. General programming explanations must be distinguishable from repository-specific claims.

## Verification v0

Machine checks run before an LLM reviewer:
- referenced evidence exists
- referenced source ranges are inside the card/supplied context
- named symbols claimed as calls exist in supplied facts
- no invented file paths
- structured output validates against schema

A reviewer may reject for unsupported intent claims, factual mismatch, missing critical context, or inappropriate difficulty. Two failed revisions leave the explanation unpublished and preserve the deterministic map/card shell.

## Test fixture

Keep a tiny in-repository fixture containing:
- one Python entry point calling two functions
- one import
- one async function
- one unresolved/dynamic call case
- one intentionally long function for semantic split testing

Expected analyzer output should be asserted structurally. Later add equivalent TypeScript/JavaScript fixtures.

## Definition of done

- one-command local dependency startup documented
- API health check passes
- analyzer unit tests pass
- integration test submits the fixture repository/snapshot and reaches `READY` without external LLM by using a deterministic teaching stub
- feature response contains source-backed flow steps
- card response contains exact source and evidence ids
- CI runs the deterministic test suite

External LLM access must not be required to prove the vertical slice in CI.
