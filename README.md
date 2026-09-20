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

The current backend path runs as separate API and worker processes sharing PostgreSQL and Redis. S3-compatible object storage is also included for the next source-artifact step.

```bash
docker compose up -d --build
```

This starts the FastAPI service on `localhost:8000`, PostgreSQL 16 + pgvector on `localhost:5432`, Redis 7 on `localhost:6379`, and MinIO on `localhost:9000` (console `9001`). The analysis worker has no host port: it consumes Redis jobs and writes results to the same PostgreSQL database as the API. Credentials in `compose.yml` are development-only.

Check the application path with:

```bash
curl http://localhost:8000/health
```

For API-only development outside containers, start the dependencies and bind the persistent store/queue explicitly:

```bash
export CARD_IN_REPO_STORE=postgres
export DATABASE_URL=postgresql://card_in_repo:card_in_repo@localhost:5432/card_in_repo
export CARD_IN_REPO_QUEUE=redis
export REDIS_URL=redis://localhost:6379/0
cd apps/api
python -m pip install -e '.[test]'
uvicorn card_in_repo_api.app:app --reload
```

Run `python -m card_in_repo_api.worker` in a second shell with the same environment to consume queued analyses. Use `docker compose down` to stop the stack, or `docker compose down -v` when you intentionally want to erase local persisted data.

Detailed architecture, data model, analysis pipeline, learning system, and implementation plan live under `docs/` as they are implemented.

## Status

Backend core prototype with a mobile PWA learning path. Public GitHub repositories can be queued through Redis, commit-pinned, and analyzed across Python, JavaScript, JSX, TypeScript, and TSX by a separate worker, then persisted as feature/flow maps and evidence-backed card shells in PostgreSQL. Long functions split at syntax boundaries. The Docker runtime acceptance path exercises real public Python and TypeScript repositories through READY -> Repository Map -> Files -> Concepts -> evidence-backed Cards -> on-demand Intermediate explanation.

The largest remaining MVP gaps are JavaScript/TypeScript cross-file module/import resolution, object-storage source artifacts, GitHub login, reliable job acknowledgement/retry semantics, and the real LLM teaching/verification pipeline. C/Rust analysis and sandbox execution remain post-MVP.