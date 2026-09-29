# Catalyst 5.7.0 upgrade notes

This repository is the upgraded Catalyst build requested for GitHub Codespaces, including Enhanced Creator Admin personality and admin-gated realistic voice output.

## Start in Codespaces

1. Open this repository in GitHub Codespaces.
2. Let the post-create hook finish, or run `bash tools/setup.sh` manually.
3. Copy `.env.example` to `.env` and set at least one provider key, for example `DEEPSEEK_API_KEY`.
4. Start the command deck:

```bash
bash run.sh
```

5. Open the forwarded **8000** port. The dark-blue holographic command deck will load.

## Verify locally

```bash
python -m compileall -q catalyst tests
python -m pytest -q
```

## Important configuration

- Keep `.env` and `catalyst_data/secrets.json` private.
- Use `CATALYST_API_TOKENS` or the admin password digest for non-local deployments.
- Keep computer-use domains explicit with `CATALYST_COMPUTER_USE_ALLOWED_DOMAINS`.
- Keep `CATALYST_COMPUTER_USE_REQUIRE_APPROVAL=true` and `CATALYST_AUTONOMOUS_AUTO_DISPATCH=true` only when the surrounding approval policy is understood.

## New surfaces

- `GET /api/cognition/pulse` — bounded, read-only intelligence snapshot used by the command deck.
- Provider profile `options.chat` — safe model-specific request controls.
- Chat and streaming handlers now preserve request-scoped auth state correctly.
