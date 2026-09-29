import base64, io, json, time, os
from pathlib import Path
import httpx
from urllib.parse import urljoin

RETRYABLE={408,409,425,429}

class AudioEngine:
    """Provider-backed speech I/O using OpenAI-compatible audio routes.
    Provider profile options may supply transcription_model, speech_model, voice,
    response_format, transcription_path, and speech_path overrides.
    """
    def __init__(self, settings, gateway, artifacts, attachments=None):
        self.settings=settings; self.gateway=gateway; self.artifacts=artifacts; self.attachments=attachments

    def _profile(self, name=None, required=()):
        if name:
            p=self.gateway.profiles.get(name)
            if not p or not p.configured: raise RuntimeError(f"Audio provider '{name}' is not configured")
            if required and not all(c in set(p.capabilities or ()) for c in required):
                raise RuntimeError(f"Provider '{name}' lacks capabilities: {', '.join(required)}")
            return p
        p=self.gateway.select_profile('audio', required)
        if not p: raise RuntimeError('No configured provider supports the requested audio capability')
        return p

    @staticmethod
    def _opts(profile, section, overrides):
        out=dict((profile.options or {}).get(section,{}) or {})
        out.update(overrides or {})
        return out

    def transcribe(self, audio_path, provider=None, language=None, prompt='', options=None):
        p=self._profile(provider, ('audio_transcription',) if provider else ())
        src=Path(audio_path); 
        if not src.exists() or not src.is_file(): raise FileNotFoundError(audio_path)
        max_bytes=int(os.getenv('CATALYST_MAX_AUDIO_BYTES','26214400')) if 'os' in globals() else 26214400
        if src.stat().st_size>max_bytes: raise ValueError(f'Audio file exceeds {max_bytes} byte limit')
        opts=self._opts(p,'transcription_request',options)
        model=opts.pop('model',None) or (p.options or {}).get('transcription_model') or 'gpt-4o-transcribe'
        path=opts.pop('endpoint',None) or (p.options or {}).get('transcription_path') or '/audio/transcriptions'
        data={'model':model}
        if language: data['language']=language
        if prompt: data['prompt']=prompt
        data.update(opts)
        headers={'Authorization':f'Bearer {p.api_key}'}
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.settings.request_timeout) as client, src.open('rb') as f:
                    r=client.post(urljoin(p.base_url+'/',path.lstrip('/')),headers=headers,data=data,files={'file':(src.name,f,'application/octet-stream')})
                if r.status_code in RETRYABLE or r.status_code>=500:
                    if attempt<2: time.sleep(.5*(2**attempt)); continue
                r.raise_for_status(); payload=r.json()
                text=str(payload.get('text') or payload.get('transcript') or '')
                result={'status':'completed','provider':p.name,'model':model,'text':text,'response':payload}
                self.artifacts.write_json(f'audio-transcription-{int(time.time()*1000)}.json',result)
                return result
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                if attempt==2: raise RuntimeError(f'Audio transcription failed: {exc}')
                time.sleep(.5*(2**attempt))

    def synthesize(self, text, provider=None, voice=None, response_format='mp3', options=None):
        p=self._profile(provider, ('audio_speech',) if provider else ())
        if not text.strip(): raise ValueError('Text is empty')
        opts=self._opts(p,'speech_request',options)
        model=opts.pop('model',None) or (p.options or {}).get('speech_model') or os.getenv('CATALYST_VOICE_MODEL','gpt-4o-mini-tts')
        voice=voice or opts.pop('voice',None) or (p.options or {}).get('voice') or os.getenv('CATALYST_VOICE_NAME','nova')
        fmt=opts.pop('response_format',None) or response_format or 'mp3'
        path=opts.pop('endpoint',None) or (p.options or {}).get('speech_path') or '/audio/speech'
        breathing_value=opts.pop('breathing',None)
        breathing=str(os.getenv('CATALYST_VOICE_BREATHING','true') if breathing_value is None else breathing_value).lower() in {'1','true','yes','on'}
        breath_interval=max(120,int(os.getenv('CATALYST_VOICE_BREATH_INTERVAL_CHARS','420')))
        instructions=opts.pop('instructions',None) or os.getenv('CATALYST_VOICE_INSTRUCTIONS','Natural realistic adult female voice; warm, intelligent, expressive, calm, and conversational.')
        # OpenAI-compatible TTS providers that expose the instructions field can
        # produce a more natural cadence. Unknown providers receive no invented
        # field unless they explicitly opt in via supports_instructions.
        supports_instructions=bool((p.options or {}).get('supports_instructions')) or str(model).startswith('gpt-4o')
        if breathing and supports_instructions:
            instructions += ' Use subtle, quiet breaths only at natural phrase or paragraph boundaries; never exaggerate them.'
        payload={'model':model,'input':text,'voice':voice,'response_format':fmt};
        if supports_instructions and instructions: payload['instructions']=instructions
        payload.update(opts)
        headers={'Authorization':f'Bearer {p.api_key}','Content-Type':'application/json'}
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.settings.request_timeout) as client:
                    r=client.post(urljoin(p.base_url+'/',path.lstrip('/')),headers=headers,json=payload)
                if r.status_code in RETRYABLE or r.status_code>=500:
                    if attempt<2: time.sleep(.5*(2**attempt)); continue
                r.raise_for_status(); data=r.content
                meta=self.artifacts.write_bytes(f'audio-speech-{int(time.time()*1000)}.{fmt}',data,f'audio/{fmt}')
                return {'status':'completed','provider':p.name,'model':model,'voice':voice,'format':fmt,
                        'breathing': {'enabled': breathing, 'strategy': 'provider-instructions' if breathing and supports_instructions else 'disabled-by-provider', 'interval_chars': breath_interval, 'estimated_cue_points': max(0, len(text) // breath_interval)},
                        'artifact':meta}
            except (httpx.HTTPError,ValueError) as exc:
                if attempt==2: raise RuntimeError(f'Audio synthesis failed: {exc}')
                time.sleep(.5*(2**attempt))

    def providers(self):
        out=[]
        for p in self.gateway.profiles.values():
            opts=p.options or {}
            out.append({'name':p.name,'configured':p.configured,'supports_transcription':'audio_transcription' in set(p.capabilities or ()),'supports_speech':'audio_speech' in set(p.capabilities or ()),'transcription_model':opts.get('transcription_model'),'speech_model':opts.get('speech_model')})
        return out
