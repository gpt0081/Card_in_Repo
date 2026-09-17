# Evidence-first Data Model

This is the logical model for the MVP. Physical migrations may combine or normalize fields as implementation evidence demands, but the boundaries below are intentional.

## Source identity

- `repositories`: provider identity, owner/name, default branch, metadata
- `repository_commits`: repository id + immutable SHA + commit metadata
- `source_files`: commit id, path, language, content hash, size

A card never points only to a mutable branch.

## Deterministic facts

- `symbols`: file, stable analysis-local id, name, kind, signature, source range, parent symbol
- `symbol_relations`: source symbol, target symbol when resolved, relation type, confidence
- `imports`: source file/symbol, imported text, resolved target when known, source range
- `analysis_evidence`: entity, evidence type, file, source range, analyzer version, payload
- `analysis_warnings`: scope, code, message, source range, severity

Initial relation types: `CALLS`, `CONTAINS`, `IMPORTS`, `EXTENDS`, `IMPLEMENTS`, `READS`, `WRITES`. Only emit a relation when the language adapter has evidence for it.

## Repository learning map

- `features`: analysis snapshot, name, description, parent, confidence, provenance
- `feature_symbols`: feature, symbol, role, importance
- `execution_flows`: feature, name, description
- `flow_steps`: flow, position, symbol, evidence id, description

Feature names may be assisted by an LLM; membership and flow edges retain provenance so deterministic and inferred edges are distinguishable.

## Concepts

- `concepts`: canonical name, category, description, baseline difficulty
- `concept_edges`: from, to, relation (`PREREQUISITE`, `RELATED`, `SPECIALIZATION`, `USED_WITH`)
- `symbol_concepts`: symbol, concept, confidence, evidence/provenance

## Cards and teaching

- `cards`: analysis snapshot, feature, parent symbol, exact source range, card type, difficulty, source hash
- `card_segments`: ordered relationship when a large symbol is semantically split
- `card_explanations`: card, level, model, prompt version, structured content, confidence, verification status
- `explanation_evidence`: explanation statement/segment -> evidence id
- `verification_runs`: explanation, verifier version/model, machine-check result, reviewer result, unsupported claims

Explanation levels: `BASIC`, `INTERMEDIATE`, `ADVANCED`, `DEEP`. Only Basic is generated eagerly in the MVP.

## Learner state

- `users`: application identity; GitHub is an auth/provider identity, not the learning-data primary key
- `user_card_progress`: state, attempts, last seen, next review
- `user_concept_mastery`: recognition, explanation, application, confidence, last seen, next review
- `learning_events`: append-oriented evidence such as understood/uncertain/unknown, quiz outcome, explanation reveal, transfer success

Mastery is derived state. Learning events preserve enough history to revise the mastery algorithm later.

## Large/reproducible artifacts

Object storage rather than relational rows:
- parser/AST dumps when retained
- graph snapshots
- future runtime traces/assembly
- generated media

Objects are addressed by analysis snapshot/version and content hash where practical.

## Versioning

Persist versions for:
- fact schema
- analyzer
- language adapter
- feature inference
- card splitter
- prompt
- verifier

A future analyzer upgrade can create a new analysis snapshot without corrupting old evidence or learner history.
