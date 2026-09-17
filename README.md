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

## Local dependencies

Docker Compose provides the MVP persistence/queue/blob dependencies with pinned major/release images:

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on `localhost:5432`, Redis 7 on `localhost:6379`, and the S3-compatible object store on `localhost:9000` (console `9001`). The credentials in `compose.yml` are development-only.

To run the API against persistent PostgreSQL instead of its deterministic in-memory test store:

```bash
export CARD_IN_REPO_STORE=postgres
export DATABASE_URL=postgresql://card_in_repo:card_in_repo@localhost:5432/card_in_repo
cd apps/api
python -m pip install -e '.[test]'
uvicorn card_in_repo_api.app:app --reload
```

Use `docker compose down` to stop dependencies, or `docker compose down -v` when you intentionally want to erase local persisted data.

Detailed architecture, data model, analysis pipeline, learning system, and implementation plan live under `docs/` as they are implemented.

## Status

Backend core prototype. Public GitHub repositories can be commit-pinned, Python source can be analyzed across files, feature/flow maps and evidence-backed card shells can be produced, long functions can be split at syntax boundaries, and analysis/card snapshots have PostgreSQL persistence support. The mobile PWA, JavaScript/TypeScript analyzer, asynchronous Redis worker path, object-storage integration, GitHub login, and real LLM teaching/verification pipeline are still pending.
