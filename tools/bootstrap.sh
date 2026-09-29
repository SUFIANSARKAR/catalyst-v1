#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Load .env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

mkdir -p "${CATALYST_DATA_ROOT:-catalyst_data}" "${CATALYST_WORKSPACE:-workspace}"
# Keep deployment-created directories out of package discovery and release archives.
mkdir -p vendor/sources
SECRETS_PATH="${CATALYST_SECRETS_PATH:-catalyst_data/secrets.json}"

python3 - <<'PY'
import json, os
from pathlib import Path

data_root=os.getenv('CATALYST_DATA_ROOT','catalyst_data')
secrets_path=Path(os.getenv('CATALYST_SECRETS_PATH',str(Path(data_root)/'secrets.json')))
secrets_path.parent.mkdir(parents=True, exist_ok=True)

raw={"profiles":{}}
if secrets_path.exists():
    try:
        raw=json.loads(secrets_path.read_text('utf-8') or '{}')
    except Exception:
        raw={"profiles":{}}
raw.setdefault('profiles',{})

# DeepSeek (OpenAI-compatible)
api_key=os.getenv('DEEPSEEK_API_KEY','').strip()
base=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com/v1').strip()
model=os.getenv('DEEPSEEK_MODEL','deepseek-chat').strip()
coder=os.getenv('DEEPSEEK_CODER_MODEL','deepseek-coder').strip()

if api_key:
    raw['profiles'].setdefault('deepseek',{
        'base_url': base,
        'model': model,
        'api_key': api_key,
        'kind': 'openai_compatible',
        'capabilities': ['reasoning','coding'],
        'role': 'general',
        'options': {}
    })
    raw['profiles'].setdefault('deepseek-coder',{
        'base_url': base,
        'model': coder,
        'api_key': api_key,
        'kind': 'openai_compatible',
        'capabilities': ['coding','reasoning'],
        'role': 'coding',
        'options': {}
    })

# Optional realistic voice profile. Keep chat and voice providers separate so
# DeepSeek can remain the reasoning model while a speech-capable provider handles
# natural female delivery and provider-supported breath instructions.
voice_key=os.getenv('OPENAI_API_KEY','').strip()
if voice_key:
    voice_base=os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1').strip()
    voice_model=os.getenv('OPENAI_TTS_MODEL','gpt-4o-mini-tts').strip()
    voice_name=os.getenv('OPENAI_TTS_VOICE','nova').strip()
    raw['profiles'].setdefault('openai-voice',{
        'base_url': voice_base,
        'model': voice_model,
        'api_key': voice_key,
        'kind': 'openai_compatible',
        'capabilities': ['audio_speech','audio_transcription'],
        'role': 'voice',
        'options': {
            'speech_model': voice_model,
            'voice': voice_name,
            'supports_instructions': True,
            'speech_request': {'voice': voice_name}
        }
    })

# Hugging Face (image) — stored as an OpenAI-compatible-ish profile placeholder; actual adapter wiring is next step
hf=os.getenv('HF_TOKEN','').strip()
hf_model=os.getenv('HF_IMAGE_MODEL','stabilityai/stable-diffusion-xl-base-1.0').strip()
if hf:
    raw['profiles'].setdefault('huggingface-image',{
        'base_url': 'https://api-inference.huggingface.co',
        'model': hf_model,
        'api_key': hf,
        'kind': 'image_api',
        'capabilities': ['image_generation'],
        'role': 'media',
        'options': {
            'image_request': {
                'endpoint': 'https://api-inference.huggingface.co/models/'+hf_model
            }
        }
    })

secrets_path.write_text(json.dumps(raw, indent=2), encoding='utf-8')
try:
    os.chmod(secrets_path,0o600)
except OSError:
    pass
print(f"Bootstrapped {secrets_path}")
PY

echo "Bootstrap complete."
