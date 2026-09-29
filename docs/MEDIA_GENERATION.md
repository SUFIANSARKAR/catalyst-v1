# Catalyst Media Generation

Catalyst Creative Studio now treats image/video generation as provider-backed production jobs rather than one-shot helper calls.

## Image jobs

Supported controls include:

- prompt and negative prompt
- aspect ratio and optional provider-native size
- quality/background
- 1–4 variants
- up to 16 reference images
- output compression
- per-provider/per-request `options`

The engine accepts both base64 and URL image responses and stores the resulting media as durable Catalyst artifacts.

## Video jobs

Supported controls include:

- text-to-video
- first-frame and last-frame references (up to two images)
- aspect ratio, duration and resolution
- optional generated audio
- negative prompt
- FPS and seed
- per-provider/per-request `options`
- long-running task polling with bounded backoff
- bounded output downloads

## Provider profiles

A provider profile advertises `image_generation` and/or `video_generation`. Legacy capability names `image` and `video` remain accepted for compatibility.

The profile `options` object can contain provider-specific request configuration without requiring a Catalyst code change. The built-in OpenRouter-compatible path uses `/images` and `/videos` below the profile base URL by default; an `endpoint` value can override that route.

Example image profile:

```json
{
  "base_url": "https://api.openrouter.ai/api/v1",
  "model": "your-image-model",
  "api_key": "<local-secret>",
  "kind": "openrouter_image",
  "capabilities": ["image_generation"],
  "role": "media",
  "options": {"app_title": "Catalyst"}
}
```

Example video profile:

```json
{
  "base_url": "https://api.openrouter.ai/api/v1",
  "model": "your-video-model",
  "api_key": "<local-secret>",
  "kind": "openrouter_video",
  "capabilities": ["video_generation"],
  "role": "media",
  "options": {"app_title": "Catalyst"}
}
```

Secrets belong in the local secret configuration/runtime environment and must not be committed or placed in reports.
