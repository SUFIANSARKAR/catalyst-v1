# Catalyst Deployment

## Quick start (Codespaces)

1. Open a terminal in the repository.
2. Run:

```bash
bash tools/setup.sh
bash run.sh
```

3. Open the forwarded port (default `8000`).

`tools/setup.sh` creates `.env` from `.env.example` when needed, bootstraps provider profiles, and installs the development dependencies. The server can start without provider credentials, but model-backed responses and media generation require a configured provider.

For Docker Compose, create the env file before starting the service:

```bash
test -f .env || cp .env.example .env
docker compose up --build
```

## What you still must provide

The canonical direct chat-provider settings are:

```dotenv
CATALYST_API_KEY=...
CATALYST_MODEL=...
CATALYST_BASE_URL=https://api.openai.com/v1
CATALYST_ADMIN_PASSWORD_SHA256=...
```

See `.env.example` for all runtime settings. The admin password value must be the SHA-256 digest of the password, not the plaintext password.

## Legacy provider compatibility

`tools/bootstrap.sh` still accepts `DEEPSEEK_API_KEY` and related `DEEPSEEK_*` values for chat/coding, `OPENAI_API_KEY` and `OPENAI_TTS_*` values for voice, and `HF_TOKEN`/`HF_IMAGE_MODEL` for an image-provider profile. These are compatibility inputs that seed profiles in `catalyst_data/secrets.json`; profiles are created only when absent, so changing a legacy variable does not replace an existing saved profile. Configure or switch saved profiles through Creator Settings.

## Admin unlock

- Click **Creator mode** in the UI and enter your Creator password.
- The server validates the SHA256 stored in `CATALYST_ADMIN_PASSWORD_SHA256`.

## Notes

- `.env` is loaded automatically by `run.sh` and is ignored by Git.
- Provider profiles are seeded into `catalyst_data/secrets.json` by `tools/bootstrap.sh`; this file is runtime state and is ignored by Git.
