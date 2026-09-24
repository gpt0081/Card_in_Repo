# Card in Repo

**Learn code where it actually lives.**

Card in Repo turns real open-source repositories into evidence-backed learning maps and code cards. Instead of teaching isolated snippets, it starts from a repository's real feature flow, lets learners inspect the files and concepts behind that flow, and progressively removes explanation until they can read the original code independently.

## Product path

```text
Public GitHub repository
  -> deterministic repository analysis
  -> feature map
  -> execution flow
  -> real code cards
  -> prerequisite concept detours
  -> return to original code
  -> deeper explanations on demand
  -> original-code reading
```

## MVP scope

- Mobile-first PWA
- GitHub sign-in and public repositories first
- Python, JavaScript, and TypeScript analysis
- Feature-first repository map, followed by file-structure and concept views
- Tree-sitter/static analysis as the factual source of truth
- Function-sized learning cards, with semantic splitting for long functions
- Basic explanations generated first; Intermediate, Advanced, and Deep explanations on demand
- Evidence-linked AI explanations with verification before publication
- Personalized concept mastery and review state
- PostgreSQL + pgvector, Redis, and object storage
- C/Rust analysis and sandbox execution after the MVP path works end to end

## Non-negotiable design rules

1. **Map before cards.** A learner should know where a code fragment lives in the feature flow before studying it.
2. **Facts before LLM prose.** Parsers and static analysis establish symbols, imports, calls, source ranges, and evidence. LLMs teach from those facts; they do not invent the repository model.
3. **Return to real code.** Concept detours must return the learner to the original repository context.
4. **Evidence is traceable.** Explanations should be attributable to concrete source ranges and analyzer output.
5. **End-to-end operability beats isolated polish.** The first engineering target is a runnable path from repository input to a visible feature map and Basic learning card.

## Planned architecture

```text
Next.js / TypeScript PWA
          |
       FastAPI
          |
  +-------+---------+
  |       |         |
Postgres Redis  Object Storage
+pgvector  |         |
           +---- Analysis workers
                 - repository fetch
                 - Tree-sitter parse
                 - symbol/import/call extraction
                 - feature/flow construction
                 - concept detection
                 - teaching generation
                 - verification
```

## Local runtime

The current product path runs as separate web, API, and worker processes sharing PostgreSQL, Redis, and S3-compatible object storage. Source snapshots are stored by immutable commit SHA and are read back through the evidence API with SHA-256 verification.

```bash
docker compose up -d --build
```

This starts the PWA on `localhost:8080`, FastAPI on `localhost:8000`, PostgreSQL 16 + pgvector on `localhost:5432`, Redis 7 on `localhost:6379`, and SeaweedFS S3 on `localhost:9000`. The analysis worker has no host port: it consumes acknowledged Redis Stream jobs and writes results to the same PostgreSQL database as the API. Credentials in `compose.yml` are development-only.

Check the application path with:

```bash
curl http://localhost:8000/health
curl http://localhost:8080/api-health
```

For API-only development outside containers, start the dependencies and bind the persistent store/queue explicitly:

```bash
export CARD_IN_REPO_STORE=postgres
export DATABASE_URL=postgresql://card_in_repo:card_in_repo@localhost:5432/card_in_repo
export CARD_IN_REPO_QUEUE=redis
export REDIS_URL=redis://localhost:6379/0
export CARD_IN_REPO_SOURCE_ARTIFACTS=s3
export CARD_IN_REPO_SOURCE_BUCKET=card-in-repo-sources
export S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=card_in_repo
export AWS_SECRET_ACCESS_KEY=card_in_repo_dev_only
export AWS_REGION=us-east-1
cd apps/api
python -m pip install -e '.[test]'
uvicorn card_in_repo_api.app:app --reload
```

Run `python -m card_in_repo_api.worker` in a second shell with the same persistence environment plus `CARD_IN_REPO_GITHUB_TOKEN` when authenticated GitHub API access is desired. Use `docker compose down` to stop the stack, or `docker compose down -v` when you intentionally want to erase local persisted data.

The optional teaching boundary is provider-neutral. Production-style JSON HTTP generation is enabled with `CARD_IN_REPO_TEACHING_PROVIDER=json_http` plus `TEACHING_LLM_ENDPOINT`, `TEACHING_LLM_MODEL`, and `TEACHING_LLM_API_KEY`; generated claims are still rejected unless they cite evidence IDs supplied by the static fact layer. The deterministic provider is test-only and requires the explicit `CARD_IN_REPO_ALLOW_TEST_PROVIDER=1` guard.

Detailed architecture, data model, analysis pipeline, learning system, and implementation plan live under `docs/` as they are implemented.

## Status

The MVP runtime now has a browser-driven path from a public GitHub repository through commit-pinned Python/JavaScript/TypeScript analysis, feature-first maps, cross-file execution flow, file and concept views, evidence-backed Basic cards, and on-demand deeper teaching. PostgreSQL persists product state, Redis Streams provide acknowledged/stale-recoverable analysis delivery with retry/DLQ handling, and SeaweedFS persists commit-pinned source snapshots. Card evidence is reconstructed from those durable snapshots and SHA-256 verified rather than trusting a copied database excerpt.

The runtime acceptance suite exercises real public Python and TypeScript repositories through READY -> Repository Map -> Files -> Concepts -> Cards and, for the TypeScript path, back through durable object storage to the verified evidence API. GitHub OAuth support is implemented; deployment still requires real OAuth credentials and production cookie/URL configuration.

The largest remaining MVP gap is proving the real `json_http` LLM teaching/verification path against a production-compatible provider instead of the deterministic CI provider, then hardening deployment/operations around that path. pgvector-backed retrieval/personalization is still largely architectural rather than a demonstrated product path. C/Rust analysis and sandbox execution remain post-MVP.