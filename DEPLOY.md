# Catalyst deploy (personal)

## Quick start (Codespaces)

1. Open a terminal in the repo
2. Run:

```bash
bash tools/setup.sh
bash run.sh
```

3. Open the forwarded port (default `8000`).

## What you still must provide

Catalyst can run without model keys, but it cannot generate answers/images without at least one provider.

Edit `.env` and set:
- `DEEPSEEK_API_KEY=` (for chat/coding)
- (optional) `HF_TOKEN=` (for more reliable free image generation)

Then restart `bash run.sh`.

## Admin unlock

- Click **Admin** in the UI → enter your Creator password.
- The server validates the SHA256 stored in `CATALYST_ADMIN_PASSWORD_SHA256`.

## Notes

- `.env` is loaded automatically by `run.sh`.
- Provider profiles are seeded into `catalyst_data/secrets.json` by `tools/bootstrap.sh`.
