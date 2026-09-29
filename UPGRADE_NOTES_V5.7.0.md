# Catalyst 5.7.0 — Enhanced Admin Mode

## Codespaces

```bash
bash run.sh
```

Open port `8000`, then select **Creator Admin Access** in the right rail. Enter the password configured by `CATALYST_ADMIN_PASSWORD_SHA256` (or the development default documented by the existing auth tests). Only the unlocked Creator Admin session receives Enhanced Catalyst personality, privileged assistance, reasoning controls, model management, and voice output.

## Voice configuration

Set these in `.env`:

```bash
CATALYST_VOICE_BREATHING=true
CATALYST_VOICE_INSTRUCTIONS="Natural realistic adult female voice; warm, intelligent, expressive, calm, and conversational. Use subtle human-like cadence and occasional quiet breaths at natural boundaries."
```

The configured provider must advertise `audio_speech` and use a compatible TTS model. Providers that do not support speech instructions will return `disabled-by-provider` for breath cues rather than pretending they were applied.

## New behavior

- `POST /api/chat` and `POST /api/chat/stream` require Creator Admin mode when `CATALYST_ENHANCED_ADMIN_ONLY=true`.
- `POST /api/reasoning/brief` and `POST /api/reasoning/analyze` require Creator Admin mode.
- `POST /api/audio/speech` and `POST /api/voice/speak` require Creator Admin mode.
- `GET /api/persona` reports `mode`, `admin_mode`, and voice presentation metadata.
