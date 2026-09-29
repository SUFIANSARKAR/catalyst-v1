# Catalyst Repository Guide

## Architecture

- `catalyst/api/server.py` is the FastAPI application and production ASGI entrypoint. It wires the model gateway, `catalyst/core/` orchestration, policy/auth, tools and agents, memory, missions, jobs, integrations, voice, and avatar services.
- `catalyst/app.py` and `catalyst/__main__.py` provide the terminal CLI and construct a separate runtime. Inspect both paths before changing shared behavior.
- `frontend/` is the static browser PWA. `frontend/catalyst-app.js` owns UI workflows; `frontend/catalyst-vrm.js` renders avatar state supplied by the backend in `catalyst/avatar.py`.
- `desktop/` is the Tauri/Vite device companion. `android/` is the Android device companion. Both connect to the FastAPI device-command API; neither replaces the PWA.
- `catalyst_data/` is persistent runtime state and is ignored by Git. `workspace/` is the configured user workspace.

## Preservation and Safety

- Inspect the owning implementation, callers, related tests, and current Git status before editing. State the smallest behavior hypothesis and a focused check before making changes.
- Preserve existing Catalyst systems and public APIs. Similar-looking mission, memory, provider, or runtime modules may serve different contracts; map ownership before proposing consolidation. Do not delete legacy implementations as cleanup.
- Preserve all tracked assets and embedded archives, including the root ZIP files, `vendor/sources/`, and the VRM model at `frontend/assets/catalyst/catalyst.vrm`. Do not replace the VRM renderer, avatar state pipeline, or reference assets without explicit direction.
- Never read, print, copy into reports, or modify `.env` or secret values. Use `.env.example` for safe configuration documentation. Treat `catalyst_data/secrets.json` and all runtime databases as private user state.
- Do not reset, stage, unstage, or revert pre-existing user changes. Keep edits narrow and do not commit or push unless explicitly requested.
- Preserve authentication, policy, approval, audit, provenance, workspace-guard, and sandbox boundaries. Do not broaden privileged behavior without focused tests.

## Validation

- Install Python dependencies with `pip install -e '.[dev]'` when needed.
- Run focused tests first, for example `python -m pytest -q tests/test_chat_authorization.py` or the relevant test module.
- Run the Python suite with `python -m pytest -q`; compile with `python -m compileall -q catalyst tests`.
- `python tools/verify_release.py` runs compilation and tests and enforces the release version. Use `--archive PATH` only when verifying an explicitly selected release archive.
- For the desktop client, use `cd desktop && npm run build` when Node.js dependencies are installed. Do not install or download dependencies without a task need.
- Validate deployment changes against `pyproject.toml`, `catalyst/config.py`, `tools/bootstrap.sh`, `run.sh`, `Dockerfile`, and `compose.yaml`. `CATALYST_*` settings are canonical; legacy provider variables are bootstrap compatibility inputs. Create `.env` from `.env.example` for a clean Compose deployment, and never inspect the existing `.env`.