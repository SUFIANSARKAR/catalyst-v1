# Catalyst 3.0 integration fabric

Catalyst 3.0 introduces an integration fabric above specialist runtimes.

- **TC ENGINEERING AI** uses the Phase-7 `/health` and `/v1/tasks` HTTP contract, including task events and approval endpoints.
- **Full Self Coding** remains a Bun/TypeScript CLI/library, so Catalyst invokes its documented `run --config` workflow through an explicit command wrapper and normalizes the result.
- **OpenHands Cloud 0.55.0** is a deployment/Helm repository in the supplied source. Catalyst therefore exposes deployment-aware configuration for the app URL and runtime URL without inventing undocumented task endpoints.

Environment variables:

```text
CATALYST_TC_URL=
CATALYST_TC_OWNER_TOKEN=
CATALYST_SELF_CODING_CMD=full-self-coding
CATALYST_FSC_TIMEOUT=3600
CATALYST_OPENHANDS_URL=
CATALYST_OPENHANDS_RUNTIME_URL=
```

Secrets stay outside Catalyst memory and are read only from runtime environment/config.
