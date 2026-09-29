# Catalyst v3.2.0 — Final 5% Closure

This release closes the highest-value remaining platform gaps without replacing Catalyst's provider-independent core.

## Semantic memory
- Optional provider-backed vector memory using the existing embedding provider abstraction.
- Semantic recall is additive: lexical memory remains the deterministic fallback.
- Durable vector index is separate from the primary memory database.
- Memory indexing can be triggered explicitly through the API.

## Voice / audio
- Provider-backed speech transcription and speech synthesis.
- Configurable provider-specific models, voices, endpoint overrides, and request options.
- Browser microphone capture in the cockpit writes transcription into the composer.
- Generated speech is stored as a durable artifact.
- Uploads and provider responses are bounded.

## Scoped identity and authorization
- Role-scoped API tokens can be supplied through `CATALYST_API_TOKENS`.
- Creator token compatibility remains available through `CATALYST_API_TOKEN`.
- Sensitive operator routes enforce capability policy.
- API can report the authenticated principal without returning credentials.

## Long-horizon reliability
- Persisted multi-step evaluation runs.
- Scenario steps can validate expected structured results.
- Reports capture step timing, failures, completion and run history.

## Additional hardening
- Mission handler JSON parsing fixed for real persisted mission execution.
- Catalyst context can merge semantic and lexical memory without making semantic memory mandatory.
- Capabilities manifest reports audio, identity and long-horizon evaluation surfaces.

## Verification targets
- Python AST parse and compilation
- Full pytest suite
- Catalyst module import sweep
- Frontend JavaScript syntax check
- Release archive integrity and secret/runtime-file exclusion
