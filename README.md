# Catalyst Catalyst Alpha

Catalyst is a **female personal AI command intelligence** with persistent cognitive memory, governed tool execution, missions, reasoning, voice, browser control, engineering workflows, media pipelines, device companions, and a holographic command-deck UI.

The goal is not to imitate a fictional character. The goal is to build a real, safe, useful Catalyst-style assistant:

> **Understand → Recall → Plan → Approve → Act → Verify → Report → Remember**

## What is included

| Layer | Capability |
|---|---|
| Identity | Female Catalyst persona, enhanced admin mode, configurable voice profile |
| Memory | SQLite durable memory and pinned cognitive memories that survive restarts |
| Orchestration | Model routing, reasoning briefs, missions, checkpoints, retries, evidence |
| Action | Tools, browser/computer use, engineering agents, device protocol, automations |
| Intelligence | World model, perception, situational signals, proactive suggestions, evidence-gated learning |
| Creative | Image/video generation and editing through external providers |
| Operations | Admin gate, policy engine, approvals, audit, provenance, observability |
| UI | Dark holographic command deck, memory search, missions, model grid, voice playback |
| Durability | State health, portable memory export, self-describing state backups |

Catalyst does **not** bundle frontier model weights or external credentials. Configure a provider at deployment time.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Set CATALYST_API_KEY, CATALYST_MODEL, and CATALYST_ADMIN_PASSWORD_SHA256 in .env
bash run.sh
```

Open `http://127.0.0.1:8000`. Unlock **Creator Admin** for enhanced personality, voice, reasoning, and privileged tools.

## Docker / Codespaces

```bash
test -f .env || cp .env.example .env
docker compose up --build
```

Set provider and admin values in `.env` before deployment. The compose file persists `catalyst_data/` and `workspace/`. GitHub Codespaces can use `bash run.sh` and forward port 8000.

## Permanent memory

Catalyst stores durable state in `catalyst_data/`. Keep this directory on a persistent volume. The runtime seeds two pinned identity anchors: Catalyst is female, and her mission is Catalyst-level personal assistance. User-approved facts, preferences, goals, decisions, commitments, and episode summaries are stored separately from short-lived chat context.

Create a portable state backup through the API after unlocking admin:

```bash
curl -X POST http://127.0.0.1:8000/api/mind/backup
curl -X POST http://127.0.0.1:8000/api/mind/export
curl http://127.0.0.1:8000/api/catalyst/state
curl http://127.0.0.1:8000/api/catalyst/learning/evaluation
```

Backups exclude provider secrets, attachments, generated artifacts, and realtime voice files. Store credentials in a deployment secret manager and back up them separately.

## Generalist learning

Catalyst records only observable or verified outcomes in `catalyst_data/learning.db`. It recalls reusable lessons before planning similar work and exposes its evidence-gated self-evaluation through `/api/catalyst/learning/stats`, `/api/catalyst/learning/search`, and `/api/catalyst/learning/evaluation`. This is adaptive memory and evaluation—not hidden model retraining or a claim of AGI.

## Configuration

The minimum provider settings are:

```dotenv
CATALYST_API_KEY=replace-me
CATALYST_MODEL=your-model
CATALYST_BASE_URL=https://api.openai.com/v1
CATALYST_ADMIN_PASSWORD_SHA256=sha256-of-your-admin-password
CATALYST_CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

See `.env.example` for memory, voice, browser, autonomy, sandbox, integration, and deployment settings.

`CATALYST_API_KEY`, `CATALYST_MODEL`, and `CATALYST_BASE_URL` are the canonical direct provider settings. For compatibility, `tools/bootstrap.sh` can also seed DeepSeek (`DEEPSEEK_API_KEY` and related `DEEPSEEK_*`), OpenAI voice (`OPENAI_API_KEY` and `OPENAI_TTS_*`), and Hugging Face image (`HF_TOKEN` and `HF_IMAGE_MODEL`) profiles into `catalyst_data/secrets.json`. It creates each profile only when absent; changing a legacy variable does not overwrite an already-saved profile.

## Safety model

Reasoning proposes. Policy approves. Tools execute only through registered authorities. Consequential actions remain approval-gated, browser domains can be allowlisted, secret-like values are filtered before cognitive persistence, and Catalyst must not claim success without evidence.

## Verification

```bash
pytest -q
python -m compileall -q catalyst
```

The release currently verifies with **168 tests passing**, one skipped test, Python compilation, API import, and a permanent-memory reopen smoke test.

## Project structure

- `catalyst/` — Python runtime and API
- `frontend/` — PWA command deck
- `android/` — Android companion shell
- `tests/` — regression and capability tests
- `docs/` — architecture and integration notes
- `catalyst_data/` — runtime state; ignored by Git and persist in deployment
- `UPGRADE_NOTES_Catalyst_ALPHA.md` — latest upgrade details and next milestones

## License

MIT. See `LICENSE`.
