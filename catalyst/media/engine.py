from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx


class MediaJobError(RuntimeError):
    pass


def _safe_name(name: str, default: str = 'media') -> str:
    raw = Path(name or default).name
    stem = Path(raw).stem or default
    suffix = Path(raw).suffix
    safe = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in stem)[:80]
    return safe + suffix


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _retryable(status: int) -> bool:
    return status in {408, 409, 425, 429} or status >= 500


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


class MediaEngine:
    """Production-oriented provider-backed image/video generation and ffmpeg editing.

    The engine intentionally keeps provider-specific assumptions at the request boundary.
    OpenRouter is first-class, while profile ``options`` allow compatible gateways to add
    provider-specific fields without changing Catalyst code.
    """

    IMAGE_CAPS = {'image', 'image_generation', 'vision_generation'}
    VIDEO_CAPS = {'video', 'video_generation'}
    IMAGE_KINDS = {'openrouter_image', 'openrouter_media', 'image_api', 'openai_image'}
    VIDEO_KINDS = {'openrouter_video', 'openrouter_media', 'video_api'}

    def __init__(self, settings, artifacts, attachments, audit=None):
        self.settings = settings
        self.artifacts = artifacts
        self.attachments = attachments
        self.audit = audit

    def provider_profiles(self):
        profiles = self.settings.load_profiles()
        out = []
        for p in profiles.values():
            caps = set(p.capabilities or ())
            is_media_kind = p.kind in self.IMAGE_KINDS | self.VIDEO_KINDS
            if p.configured and (is_media_kind or self.IMAGE_CAPS & caps or self.VIDEO_CAPS & caps):
                out.append({
                    'name': p.name,
                    'kind': p.kind,
                    'model': p.model,
                    'base_url': p.base_url,
                    'capabilities': sorted(caps),
                    'role': p.role,
                    'active': False,
                    'supports_image': bool(self.IMAGE_CAPS & caps or p.kind in self.IMAGE_KINDS),
                    'supports_video': bool(self.VIDEO_CAPS & caps or p.kind in self.VIDEO_KINDS),
                    'options': getattr(p, 'options', {}) or {},
                })
        return out

    def _profile(self, name: str | None, media: str):
        profiles = self.settings.load_profiles()
        caps_needed = self.IMAGE_CAPS if media == 'image' else self.VIDEO_CAPS
        kinds = self.IMAGE_KINDS if media == 'image' else self.VIDEO_KINDS
        if name and name in profiles:
            p = profiles[name]
        else:
            preferred = [
                p for p in profiles.values()
                if p.configured and (caps_needed & set(p.capabilities or ()) or p.kind in kinds)
            ]
            p = preferred[0] if preferred else None
        if not p or not p.configured:
            raise MediaJobError(
                f'No configured {media} generation provider. Add a provider profile with '
                f'capability {media}_generation or a compatible media kind.'
            )
        if not (caps_needed & set(p.capabilities or ())) and p.kind not in kinds:
            raise MediaJobError(f'Provider {p.name} is configured but does not advertise {media}_generation support')
        return p

    @staticmethod
    def _profile_options(profile) -> dict[str, Any]:
        return dict(getattr(profile, 'options', {}) or {})

    def _reference_payload(self, references: list[str], *, mode: str, max_refs: int) -> list[dict[str, Any]]:
        refs = list(references or [])
        if len(refs) > max_refs:
            raise MediaJobError(f'{mode} generation supports at most {max_refs} reference images')
        payload = []
        for aid in refs:
            path = self.attachments.resolve(aid)
            mime = mimetypes.guess_type(path.name)[0] or 'image/png'
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode('ascii')
            payload.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}, '_path': str(path)})
        return payload

    def _headers(self, profile, *, json_request: bool = True) -> dict[str, str]:
        headers = {'Authorization': f'Bearer {profile.api_key}'}
        if json_request:
            headers['Content-Type'] = 'application/json'
        options = self._profile_options(profile)
        if options.get('http_referer'):
            headers['HTTP-Referer'] = str(options['http_referer'])
        if options.get('app_title'):
            headers['X-OpenRouter-Title'] = str(options['app_title'])
        return headers

    async def _request_json(self, method: str, url: str, *, headers: dict[str, str], payload: dict[str, Any] | None,
                            timeout: float, attempts: int = 3) -> Any:
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await client.request(method, url, headers=headers, json=payload)
                    text = response.text
                    try:
                        body = response.json()
                    except ValueError:
                        body = {'message': text[:4000]}
                    if response.status_code >= 400:
                        err = MediaJobError(f'Media provider HTTP {response.status_code}: {body}')
                        if not _retryable(response.status_code) or attempt >= attempts:
                            raise err
                        last = err
                    else:
                        return body
            except MediaJobError:
                raise
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last = exc
                if attempt >= attempts:
                    raise MediaJobError(f'Media provider request failed after {attempts} attempts: {exc}') from exc
            await asyncio.sleep(min(2 ** (attempt - 1), 8))
        raise MediaJobError(f'Media provider request failed: {last}')

    async def _download(self, url: str, headers: dict[str, str], timeout: float, max_bytes: int) -> bytes:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream('GET', url, headers=headers) as response:
                response.raise_for_status()
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > max_bytes:
                    raise MediaJobError(f'Media output exceeds configured {max_bytes // (1024 * 1024)} MB download limit')
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaJobError(f'Media output exceeds configured {max_bytes // (1024 * 1024)} MB download limit')
                    chunks.append(chunk)
                return b''.join(chunks)

    @staticmethod
    def _decode_b64(encoded: str) -> bytes:
        if encoded.startswith('data:') and ',' in encoded:
            encoded = encoded.split(',', 1)[1]
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise MediaJobError('Image provider returned invalid base64 data') from exc

    @staticmethod
    def _image_media_type(item: dict[str, Any]) -> tuple[str, str]:
        media_type = str(item.get('media_type') or item.get('mime_type') or 'image/png')
        ext = {'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/avif': '.avif'}.get(media_type, '.png')
        return media_type, ext

    async def generate_images(self, prompt: str, provider: str | None = None, references: list[str] | None = None,
                              aspect_ratio: str = '16:9', quality: str = 'auto', background: str = 'auto',
                              variants: int = 1, negative_prompt: str = '', size: str | None = None,
                              output_compression: int | None = None, options: dict[str, Any] | None = None):
        p = self._profile(provider, 'image')
        variants = _safe_int(variants, 1, 1, 4)
        refs = self._reference_payload(references or [], mode='Image', max_refs=16)
        profile_options = self._profile_options(p)
        extra = dict(profile_options.get('image_request', {}) or {})
        extra.update(options or {})
        base = p.base_url.rstrip('/')
        endpoint = str(extra.pop('endpoint', f'{base}/images'))
        payload: dict[str, Any] = {
            'model': p.model,
            'prompt': prompt,
            'n': variants,
            'quality': extra.pop('quality', quality),
            'background': extra.pop('background', background),
            'aspect_ratio': extra.pop('aspect_ratio', aspect_ratio),
        }
        if size:
            payload['size'] = size
        if negative_prompt:
            payload['negative_prompt'] = negative_prompt
        if output_compression is not None:
            payload['output_compression'] = output_compression
        if refs:
            payload['input_references'] = [{k: v for k, v in ref.items() if k != '_path'} for ref in refs]
        payload.update(extra)

        timeout = float(os.getenv('CATALYST_MEDIA_TIMEOUT', '600'))
        body = await self._request_json('POST', endpoint, headers=self._headers(p), payload=payload, timeout=timeout)
        data = body.get('data') if isinstance(body, dict) else None
        if not isinstance(data, list) or not data:
            raise MediaJobError(f'Image provider response did not contain a non-empty data array: {body}')

        outputs = []
        for index, item in enumerate(data[:variants]):
            if not isinstance(item, dict):
                continue
            encoded = item.get('b64_json') or item.get('base64')
            if encoded:
                encoded_text = str(encoded)
                max_download = _safe_int(os.getenv('CATALYST_MEDIA_IMAGE_MAX_MB', '32'), 32, 1, 256) * 1024 * 1024
                estimated_bytes = max(0, (len(encoded_text) * 3) // 4)
                if estimated_bytes > max_download:
                    raise MediaJobError('Image provider returned an image larger than the configured download limit')
                raw = self._decode_b64(encoded_text)
            else:
                url = item.get('url') or item.get('image_url')
                if not url:
                    continue
                raw = await self._download(urljoin(base + '/', str(url)), self._headers(p, json_request=False), timeout, max_download)
            media_type, ext = self._image_media_type(item)
            meta = self.artifacts.write_bytes(f'image-{os.urandom(4).hex()}-{index + 1}{ext}', raw, media_type)
            meta.update({
                'media_kind': 'image', 'prompt': prompt, 'negative_prompt': negative_prompt,
                'provider': p.name, 'model': p.model, 'aspect_ratio': aspect_ratio, 'variant': index + 1,
            })
            outputs.append(meta)
        if not outputs:
            raise MediaJobError(f'Image provider returned no usable image outputs: {body}')
        return outputs

    async def generate_image(self, prompt: str, provider: str | None = None, references: list[str] | None = None,
                             aspect_ratio: str = '16:9', quality: str = 'auto', background: str = 'auto',
                             variants: int = 1, negative_prompt: str = '', size: str | None = None,
                             output_compression: int | None = None, options: dict[str, Any] | None = None):
        return (await self.generate_images(prompt, provider, references, aspect_ratio, quality, background,
                                           variants, negative_prompt, size, output_compression, options))[0]

    async def generate_video(self, prompt: str, provider: str | None = None, references: list[str] | None = None,
                             aspect_ratio: str = '16:9', duration: int = 8, resolution: str = '720p', audio: bool = True,
                             negative_prompt: str = '', fps: int | None = None, seed: int | None = None,
                             options: dict[str, Any] | None = None):
        p = self._profile(provider, 'video')
        refs = self._reference_payload(references or [], mode='Video', max_refs=2)
        profile_options = self._profile_options(p)
        extra = dict(profile_options.get('video_request', {}) or {})
        extra.update(options or {})
        base = p.base_url.rstrip('/')
        endpoint = str(extra.pop('endpoint', f'{base}/videos'))
        payload: dict[str, Any] = {
            'model': p.model,
            'prompt': prompt,
            'aspect_ratio': aspect_ratio,
            'duration': _safe_int(duration, 8, 1, 30),
            'resolution': resolution,
            'generate_audio': bool(audio),
        }
        if negative_prompt:
            payload['negative_prompt'] = negative_prompt
        if fps is not None:
            payload['fps'] = _safe_int(fps, 24, 1, 120)
        if seed is not None:
            payload['seed'] = int(seed)
        if refs:
            frame_images = []
            frame_types = ['first_frame', 'last_frame']
            for i, ref in enumerate(refs):
                frame_images.append({
                    'type': 'image_url',
                    'image_url': ref['image_url'],
                    'frame_type': frame_types[i],
                })
            payload['frame_images'] = frame_images
        payload.update(extra)

        request_timeout = float(os.getenv('CATALYST_MEDIA_REQUEST_TIMEOUT', '90'))
        timeout = float(os.getenv('CATALYST_MEDIA_TIMEOUT', '900'))
        body = await self._request_json('POST', endpoint, headers=self._headers(p), payload=payload, timeout=request_timeout)
        task_id = body.get('id') or body.get('task_id') if isinstance(body, dict) else None
        if not task_id:
            url = (body.get('video_url') or body.get('url')) if isinstance(body, dict) else None
            if url:
                raw = await self._download(str(url), self._headers(p, json_request=False), timeout,
                                           _safe_int(os.getenv('CATALYST_MEDIA_VIDEO_MAX_MB', '512'), 512, 10, 2048) * 1024 * 1024)
                meta = self.artifacts.write_bytes(f'video-{os.urandom(4).hex()}.mp4', raw, 'video/mp4')
                meta.update({'media_kind': 'video', 'prompt': prompt, 'provider': p.name, 'model': p.model})
                return meta
            raise MediaJobError(f'Video provider response did not contain a task id or video URL: {body}')

        status_url = body.get('status_url') or body.get('polling_url') or f'{endpoint.rstrip("/")}/{task_id}'
        status_url = urljoin(base + '/', str(status_url))
        poll_interval = max(0.5, float(os.getenv('CATALYST_MEDIA_POLL', '5')))
        deadline = asyncio.get_running_loop().time() + timeout
        backoff = poll_interval
        last_status = None
        last_payload: Any = body
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(backoff)
            current = await self._request_json('GET', str(status_url), headers=self._headers(p, json_request=False), payload=None,
                                               timeout=min(90.0, request_timeout), attempts=3)
            last_payload = current
            status = str(current.get('status', current.get('state', ''))).lower() if isinstance(current, dict) else ''
            last_status = status
            if status in {'completed', 'complete', 'succeeded', 'success', 'done'}:
                url = None
                if isinstance(current, dict):
                    data = current.get('data') if isinstance(current.get('data'), dict) else {}
                    url = current.get('video_url') or current.get('output_url') or current.get('url') or data.get('video_url') or data.get('url')
                    urls = current.get('unsigned_urls') or []
                    if not url and urls: url = urls[0]
                if not url:
                    url = f'{base}/videos/{task_id}/content?index=0'
                max_bytes = _safe_int(os.getenv('CATALYST_MEDIA_VIDEO_MAX_MB', '512'), 512, 10, 2048) * 1024 * 1024
                raw = await self._download(urljoin(base + '/', str(url)), self._headers(p, json_request=False), timeout, max_bytes)
                meta = self.artifacts.write_bytes(f'video-{os.urandom(4).hex()}.mp4', raw, 'video/mp4')
                meta.update({
                    'media_kind': 'video', 'prompt': prompt, 'negative_prompt': negative_prompt,
                    'provider': p.name, 'model': p.model, 'task_id': task_id, 'duration': duration,
                    'resolution': resolution, 'aspect_ratio': aspect_ratio,
                })
                return meta
            if status in {'failed', 'error', 'cancelled', 'canceled', 'expired'}:
                raise MediaJobError(f'Video generation {status} for {task_id}: {current}')
            # Slow down progressively for long-running jobs, but remain responsive.
            backoff = min(max(backoff * 1.25, poll_interval), 20.0)

        raise MediaJobError(f'Video generation timed out after {timeout:g}s; task_id={task_id}; last_status={last_status}; last_payload={last_payload}')

    def edit(self, operation: str, input_paths: list[str], options: dict[str, Any] | None = None):
        options = options or {}
        if not input_paths:
            raise MediaJobError('At least one media input is required')
        paths = [self._resolve_media_ref(ref) for ref in input_paths]
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise MediaJobError('ffmpeg is required for media editing but was not found in PATH')
        op = operation.lower().strip()
        out_ext = '.mp4'
        if op == 'extract_audio': out_ext = '.mp3'
        elif op == 'thumbnail': out_ext = '.jpg'
        out_path = self.artifacts.root / f'edit-{op}-{os.urandom(4).hex()}{out_ext}'
        if op == 'trim':
            start = float(options.get('start', 0)); end = options.get('end')
            cmd = [ffmpeg, '-y', '-ss', str(start), '-i', str(paths[0])]
            if end is not None: cmd += ['-to', str(end)]
            cmd += ['-c', 'copy', str(out_path)]
        elif op == 'resize':
            width = int(options.get('width', 1280)); height = int(options.get('height', 720))
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease', '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
        elif op == 'crop':
            width = int(options.get('width', 1280)); height = int(options.get('height', 720)); x = str(options.get('x','(iw-ow)/2')); y = str(options.get('y','(ih-oh)/2'))
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-vf', f'crop={width}:{height}:{x}:{y}', '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
        elif op == 'rotate':
            degrees = int(options.get('degrees',90)) % 360
            filters = {90:'transpose=1', 180:'hflip,vflip', 270:'transpose=2'}
            if degrees not in filters: raise MediaJobError('rotate supports 90, 180, or 270 degrees')
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-vf', filters[degrees], '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
        elif op == 'mute':
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-c', 'copy', '-an', str(out_path)]
        elif op == 'thumbnail':
            at = float(options.get('at', 0)); cmd = [ffmpeg, '-y', '-ss', str(at), '-i', str(paths[0]), '-frames:v', '1', '-q:v', '2', str(out_path)]
        elif op == 'extract_audio':
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-vn', '-codec:a', 'libmp3lame', str(out_path)]
        elif op == 'concat':
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, dir=str(self.artifacts.root), encoding='utf-8') as f:
                list_path = Path(f.name)
                for p in paths: f.write("file " + shlex.quote(str(p)) + "\n")
            try:
                cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(list_path), '-c', 'copy', str(out_path)]
                result = self._run(cmd)
            finally: list_path.unlink(missing_ok=True)
            if result.returncode != 0: raise MediaJobError(result.stderr[-3000:])
            return self._artifact_meta(out_path, op)
        elif op == 'add_audio':
            audio = paths[1] if len(paths) > 1 else None
            if not audio: raise MediaJobError('add_audio expects [video, audio]')
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-shortest', str(out_path)]
        elif op == 'mix_audio':
            audio = paths[1] if len(paths) > 1 else None
            if not audio: raise MediaJobError('mix_audio expects [video, audio]')
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-i', str(audio), '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]', '-map', '0:v:0', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', str(out_path)]
        elif op == 'speed':
            factor = float(options.get('factor', 1.0))
            if factor < 0.5 or factor > 2.0: raise MediaJobError('speed factor must be between 0.5 and 2.0 for audio-safe processing')
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-filter_complex', f'[0:v]setpts={1/factor}*PTS[v];[0:a]atempo={max(0.5,min(2.0,factor))}[a]', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
        elif op == 'normalize_audio':
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:v', 'copy', '-c:a', 'aac', str(out_path)]
        elif op == 'reverse':
            cmd = [ffmpeg, '-y', '-i', str(paths[0]), '-vf', 'reverse', '-af', 'areverse', '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
        else:
            raise MediaJobError(f'Unsupported edit operation: {operation}')
        result = self._run(cmd)
        if result.returncode != 0: raise MediaJobError((result.stderr or result.stdout)[-3000:])
        return self._artifact_meta(out_path, op)

    def _resolve_media_ref(self, ref: str) -> Path:
        raw = str(ref)
        try:
            return self.attachments.resolve(raw)
        except Exception:
            p = (self.artifacts.root / Path(raw).name).resolve()
            if self.artifacts.root.resolve() not in p.parents or not p.exists():
                raise FileNotFoundError(raw)
            return p

    def _run(self, cmd):
        return subprocess.run(cmd, capture_output=True, text=True)

    def _artifact_meta(self, path: Path, operation: str):
        data = path.read_bytes()
        meta = self.artifacts._meta(path, path.suffix.lower() or 'binary') if hasattr(self.artifacts, '_meta') else {
            'name': path.name, 'path': str(path), 'size': len(data)
        }
        meta['media_kind'] = 'video' if path.suffix.lower() in {'.mp4','.mov','.webm','.mkv'} else ('audio' if path.suffix.lower() in {'.mp3','.wav','.m4a'} else 'image')
        meta['operation'] = operation
        return meta
