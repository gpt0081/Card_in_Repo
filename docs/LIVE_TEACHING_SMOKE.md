# Live teaching smoke

The MVP is not considered proven against a real LLM until the `json_http` teaching path survives evidence verification and PostgreSQL persistence. The deterministic provider used by normal CI does not satisfy that criterion.

## Fastest local proof

On the machine that can reach the model provider, start exactly one model and set its OpenAI-compatible chat-completions endpoint:

```bash
export TEACHING_LLM_ENDPOINT=http://127.0.0.1:1234/v1/chat/completions
bash scripts/local_live_teaching_smoke.sh
```

The launcher queries the corresponding `/v1/models` endpoint and automatically uses the model ID when exactly one model is loaded. If the server exposes zero or multiple models, set `TEACHING_LLM_MODEL` explicitly instead. `TEACHING_LLM_MODELS_ENDPOINT` can override model discovery for providers whose models endpoint does not share the chat endpoint prefix.

```bash
export TEACHING_LLM_MODEL=<loaded-model-name>
bash scripts/local_live_teaching_smoke.sh
```

This path is intended for LM Studio, llama.cpp, or another compatible local server. An API key is optional and is also sent during model discovery when configured. By default the launcher creates a disposable `pgvector/pgvector:pg16` PostgreSQL container bound only to `127.0.0.1:55432`, waits for readiness, creates a disposable Python virtual environment, installs the analyzer/API packages there, runs the real smoke program, and removes both the database container and virtual environment on exit. The host Python environment is not modified, which keeps the path compatible with externally managed/Homebrew Python installations. The launcher refuses to take over a pre-existing container with the same name.

The smoke exercises eager Basic generation, requested on-demand teaching depths, evidence verification, PostgreSQL persistence, and serving the durable deeper-level cache after the provider is detached. `TEACHING_SMOKE_LEVEL` may be set to `basic`, `intermediate`, `advanced`, or `deep`; the default is `all`.

If PostgreSQL + pgvector is already available, bypass Docker:

```bash
export LIVE_TEACHING_DATABASE_URL=postgresql://user:password@host:5432/database
bash scripts/local_live_teaching_smoke.sh
```

For a non-loopback private HTTP provider, also set `CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING=1`. Keep that opt-in scoped to trusted private/Tailscale networks.

## GitHub Actions proof

`.github/workflows/live-teaching-smoke.yml` remains the repeatable remote path. Public HTTPS providers run on GitHub-hosted Ubuntu with an isolated pgvector service. Private, localhost, or Tailscale providers require `LIVE_TEACHING_RUNNER` to select a network-reachable self-hosted runner and `LIVE_TEACHING_DATABASE_URL` to select PostgreSQL reachable from it.

The direct local launcher exists so registering a self-hosted GitHub runner is not a prerequisite for the first real-model proof. Once a provider is proven locally, the self-hosted workflow is the preferred repeatable operational check.
