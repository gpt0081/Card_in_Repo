# MVP Architecture

## Decision

Card in Repo starts as a **modular monolith plus background analysis workers**, not a fleet of microservices. The first engineering objective is one end-to-end path that can accept a public GitHub repository, analyze supported source, expose a feature map, and open an evidence-backed Basic learning card.

## Components

### `apps/web`

Mobile-first Next.js/TypeScript PWA.

Responsibilities:
- GitHub authentication UI
- repository URL/input flow
- analysis progress
- feature-first map
- execution-flow view
- code card view
- file and concept secondary views
- learning state interactions

It must not infer repository facts in the browser.

### `apps/api`

FastAPI application and system-of-record boundary.

Responsibilities:
- user/session API
- repository registration
- analysis job lifecycle
- serving immutable analysis snapshots by commit SHA
- cards, evidence, explanations, and learning state
- authorization and rate limits

### `packages/analyzer`

Deterministic repository analysis library used by workers. Initial languages: Python, JavaScript, TypeScript.

Pipeline outputs must be serializable and versioned. Initial facts:
- source file identity and content hash
- language
- symbols and source ranges
- imports
- direct statically resolvable calls
- containment relationships
- analyzer warnings and unsupported constructs

Tree-sitter is the syntax foundation. Language-specific adapters may add resolution rules, but unsupported/dynamic behavior must remain explicit rather than guessed.

### `workers/analysis`

Background job runner.

Jobs:
1. resolve repository + immutable commit SHA
2. enumerate supported source files
3. fetch/cache source
4. parse
5. extract symbols/imports/calls/evidence
6. construct a conservative execution graph
7. derive feature candidates
8. persist an analysis snapshot
9. generate Basic cards only after the map exists
10. verify generated teaching content against evidence

### Persistence

PostgreSQL is authoritative. `pgvector` is used for semantic retrieval only, not as a source of repository truth. Redis stores queues, locks, short-lived progress, and cache data. Object storage stores large/reproducible analysis artifacts and future sandbox traces.

## Trust boundaries

```text
GitHub source at commit SHA
        |
        v
Deterministic analyzers
        |
        v
Versioned Fact Package  <---- authoritative repository facts
        |
        +----> feature/flow construction
        |
        +----> LLM teaching generation
                       |
                       v
                  verifier
                       |
                       v
                published explanation
```

An LLM may classify, summarize, teach, or propose feature grouping, but must not silently create symbols, calls, source ranges, imports, or return types that contradict the Fact Package. Any uncertain feature grouping carries confidence and provenance.

## Snapshot rule

Every analysis result is pinned to an immutable commit SHA. A branch name is accepted only as an input convenience; once resolved, cards and evidence reference the SHA. If upstream changes, a new analysis snapshot is created instead of mutating historical learning evidence.

## Failure behavior

The system fails closed:
- unsupported language -> report unsupported files, do not fabricate analysis
- parser recovery/error nodes -> retain warning and lower evidence quality
- unresolved dynamic call -> mark unresolved, do not invent target
- LLM unavailable -> repository map remains usable; teaching generation can retry later
- verification failure -> card explanation is not published
- upstream rate limit -> job becomes retryable with explicit status

## MVP deployment shape

Local development should be bootable with one command using containers for PostgreSQL/pgvector, Redis, and object storage. Web/API/analyzer may run directly during development for fast iteration. Production packaging can change after the vertical slice is measured.

## Deferred deliberately

- C/Rust analysis
- arbitrary code execution sandbox
- private repositories
- cross-repository concept atlas at scale
- microservice decomposition
- graph database
- native iOS/Android clients

These are extensions, not prerequisites for proving the learning loop.
