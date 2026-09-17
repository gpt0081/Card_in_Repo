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

Detailed architecture, data model, analysis pipeline, learning system, and implementation plan live under `docs/` as they are implemented.

## Status

Bootstrap phase. The repository is intentionally starting with the product contract and an executable vertical-slice plan before framework scaffolding is added.
