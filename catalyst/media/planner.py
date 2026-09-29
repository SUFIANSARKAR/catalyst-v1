from __future__ import annotations

import json
import re
from typing import Any


class CreativePlanner:
    """LLM-assisted production planning with explicit visual continuity contracts."""

    def __init__(self, gateway):
        self.gateway = gateway

    def plan(self, concept: str, mode: str = 'video', style: str = '', shot_limit: int = 8) -> dict[str, Any]:
        shot_limit = max(1, min(int(shot_limit or 8), 24))
        mode = mode if mode in {'video', 'image'} else 'video'
        prompt = f"""Create a production-ready {mode} plan for this concept:
{concept}

Style: {style or 'cinematic, coherent, production-ready'}
Shot limit: {shot_limit}

Return ONLY valid JSON with this schema:
{{
  "title": "...",
  "logline": "...",
  "visual_style": "...",
  "characters": [{{"name":"...","appearance":"...","wardrobe":"...","continuity_notes":"..."}}],
  "world": {{"location":"...","time":"...","lighting":"...","palette":"..."}},
  "scenes": [
    {{
      "scene":"...",
      "purpose":"...",
      "shots":[
        {{
          "id":"S01_SH01",
          "prompt":"complete generation prompt",
          "negative_prompt":"common failure avoidance",
          "camera":"shot size + lens + movement",
          "duration":8,
          "aspect_ratio":"16:9",
          "continuity":"what must remain consistent from adjacent shots",
          "references":[],
          "audio":"dialogue/music/SFX intent"
        }}
      ]
    }}
  ]
}}

Requirements:
- Preserve creator intent; do not invent major plot facts.
- Keep characters, wardrobe, environment, lighting, and screen direction consistent.
- Every shot must be directly usable as an image/video generation prompt.
- Use references as attachment IDs only when explicitly supplied; otherwise use an empty array.
- Avoid vague phrases such as 'make it cinematic' without specifying camera, subject, action, and environment.
- Keep the total number of shots <= {shot_limit}.
"""
        result = self.gateway.chat([
            {'role': 'system', 'content': 'You are Catalyst Creative Director and continuity supervisor. Return valid JSON only.'},
            {'role': 'user', 'content': prompt},
        ], task='creative')
        content = result.get('content', '') if isinstance(result, dict) else str(result)
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.I)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Creative planner returned invalid JSON: {content[:600]}') from exc

        data.setdefault('title', 'Catalyst Creative Project')
        data.setdefault('logline', '')
        data.setdefault('visual_style', style or 'coherent cinematic realism')
        data.setdefault('characters', [])
        data.setdefault('world', {})
        data.setdefault('scenes', [])

        shots = 0
        for scene_index, scene in enumerate(data.get('scenes') or [], 1):
            scene['shots'] = list(scene.get('shots') or [])
            if shots >= shot_limit:
                scene['shots'] = []
                continue
            allowed = max(0, shot_limit - shots)
            scene['shots'] = scene['shots'][:allowed]
            for shot_index, shot in enumerate(scene['shots'], 1):
                shot.setdefault('id', f'S{scene_index:02d}_SH{shot_index:02d}')
                shot.setdefault('prompt', '')
                shot.setdefault('negative_prompt', '')
                shot.setdefault('camera', 'medium shot, natural perspective')
                shot.setdefault('duration', 8 if mode == 'video' else 0)
                shot.setdefault('aspect_ratio', '16:9')
                shot.setdefault('continuity', '')
                shot.setdefault('references', [])
                shot.setdefault('audio', '')
            shots += len(scene['shots'])
        data['shot_count'] = shots
        data['mode'] = mode
        return data
