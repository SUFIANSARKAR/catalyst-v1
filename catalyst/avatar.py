"""Catalyst avatar state and VRM manifest service.

This module deliberately separates the avatar's *state* from its renderer.  The
browser can use a VRM renderer today and a different renderer later without
changing Catalyst's cognition or voice layers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any
import json
import struct
import time


AVATAR_STATES = {
    "idle", "listening", "thinking", "speaking", "interrupted",
    "success", "error", "away",
}
EMOTIONS = {
    "neutral", "warm", "focused", "curious", "happy", "serious",
    "concerned", "surprised", "playful", "sad",
}

APPEARANCES: dict[str, dict[str, Any]] = {
    "signature": {"name": "Signature", "outfit": "signature", "tone": "warm", "description": "Catalyst's default signature presentation."},
    "lounge": {"name": "Lounge", "outfit": "lounge", "tone": "soft", "description": "Relaxed everyday presentation."},
    "focus": {"name": "Focus", "outfit": "focus", "tone": "focused", "description": "Deep-work creator presentation."},
    "night": {"name": "Night", "outfit": "night", "tone": "violet", "description": "Low-light evening presentation."},
}
ACTIONS = {"idle", "breathe", "listen", "think", "speak", "gesture", "celebrate", "concern", "reset"}


@dataclass
class AvatarState:
    state: str = "idle"
    emotion: str = "neutral"
    hint: str = "ready when you are"
    speech_level: float = 0.0
    updated_at: float = field(default_factory=time.time)
    source: str = "system"
    appearance: str = "signature"
    action: str = "idle"
    gesture: str = "none"
    gaze: str = "camera"
    motion: str = "full"

    def public(self) -> dict[str, Any]:
        return asdict(self)


class AvatarController:
    """Thread-safe controller used by API/cognition bridges."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = AvatarState()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return self._state.public()

    def set(
        self,
        state: str,
        *,
        emotion: str | None = None,
        action: str | None = None,
        hint: str = "",
        speech_level: float = 0.0,
        source: str = "system",
        appearance: str | None = None,
    ) -> dict[str, Any]:
        state = (state or "idle").lower()
        emotion = (emotion or "neutral").lower()
        if state not in AVATAR_STATES:
            raise ValueError(f"Unknown avatar state: {state}")
        if emotion not in EMOTIONS:
            raise ValueError(f"Unknown avatar emotion: {emotion}")
        selected_action = action or {"idle":"idle","listening":"listen","thinking":"think","speaking":"speak","interrupted":"listen","success":"celebrate","error":"concern","away":"idle"}[state]
        if selected_action not in ACTIONS:
            raise ValueError(f"Unknown avatar action: {selected_action}")
        with self._lock:
            self._state = AvatarState(
                state=state,
                emotion=emotion,
                action=selected_action,
                hint=hint,
                speech_level=max(0.0, min(1.0, float(speech_level))),
                updated_at=time.time(),
                source=source,
                appearance=appearance or self._state.appearance,
                gesture="none",
                gaze="camera",
                motion=self._state.motion,
            )
            return self._state.public()

    def set_appearance(self, appearance: str, *, source: str = "ui") -> dict[str, Any]:
        appearance = (appearance or "signature").lower()
        allowed = set(APPEARANCES)
        if appearance not in allowed:
            raise ValueError(f"Unknown avatar appearance: {appearance}")
        with self._lock:
            self._state.appearance = appearance
            self._state.updated_at = time.time()
            self._state.source = source
            return self._state.public()

    def set_motion(self, motion: str, *, source: str = "ui") -> dict[str, Any]:
        motion = (motion or "full").lower()
        if motion not in {"full", "reduced"}:
            raise ValueError(f"Unknown avatar motion mode: {motion}")
        with self._lock:
            self._state.motion = motion
            self._state.updated_at = time.time()
            self._state.source = source
            return self._state.public()


def load_avatar_manifest(root: Path) -> dict[str, Any]:
    path = root / "catalyst" / "catalyst_avatar_manifest.json"
    if not path.is_file():
        return {"name": "Catalyst", "version": "1.0", "states": sorted(AVATAR_STATES)}
    return json.loads(path.read_text(encoding="utf-8"))


def avatar_runtime_info(frontend_root: Path) -> dict[str, Any]:
    model = frontend_root / "assets" / "catalyst" / "catalyst.vrm"
    validation: dict[str, Any] = {"valid": False, "extensions": [], "nodes": 0, "meshes": 0, "humanoid_bones": 0, "spring_bone": False}
    if model.is_file():
        try:
            data = model.read_bytes()
            magic, version, length = struct.unpack_from('<4sII', data, 0)
            if magic != b'glTF' or version != 2 or length != len(data):
                raise ValueError('Invalid GLB header')
            offset = 12; gltf = None
            while offset < len(data):
                chunk_length, chunk_type = struct.unpack_from('<II', data, offset)
                chunk = data[offset + 8: offset + 8 + chunk_length]
                offset += 8 + chunk_length
                if chunk_type == 0x4E4F534A:
                    gltf = json.loads(chunk.rstrip(b' \t\r\n\x00').decode('utf-8'))
                    break
            if not isinstance(gltf, dict):
                raise ValueError('Missing GLB JSON')
            vrm = (gltf.get('extensions') or {}).get('VRMC_vrm') or {}
            bones = ((vrm.get('humanoid') or {}).get('humanBones') or {})
            expressions = vrm.get('expressions') or {}
            preset_expressions = expressions.get('preset') or {}
            custom_expressions = expressions.get('custom') or {}
            skins = gltf.get('skins') or []
            mesh_nodes = [n for n in (gltf.get('nodes') or []) if 'mesh' in n]
            skinned_mesh_nodes = [n for n in mesh_nodes if 'skin' in n]
            validation = {
                'valid': vrm.get('specVersion') == '1.0' and 'VRMC_springBone' in (gltf.get('extensionsUsed') or []),
                'extensions': list(gltf.get('extensionsUsed') or []),
                'nodes': len(gltf.get('nodes') or []),
                'meshes': len(gltf.get('meshes') or []),
                'humanoid_bones': len(bones),
                'spring_bone': 'VRMC_springBone' in (gltf.get('extensionsUsed') or []),
                'skinned_mesh': bool(skins) and len(skinned_mesh_nodes) == len(mesh_nodes),
                'skin_count': len(skins),
                'mesh_nodes': len(mesh_nodes),
                'skinned_mesh_nodes': len(skinned_mesh_nodes),
                'expression_presets': sorted(preset_expressions.keys()),
                'custom_expressions': sorted(custom_expressions.keys()),
                'asset_name': ((vrm.get('meta') or {}).get('name') or ''),
            }
        except Exception as exc:
            validation['error'] = str(exc)
    return {
        "renderer": "vrm-1.0",
        "model": {
            "installed": model.is_file(),
            "path": "/assets/catalyst/catalyst.vrm" if model.is_file() else None,
            "bytes": model.stat().st_size if model.is_file() else 0,
        },
        "fallback": "/assets/catalyst/avatar_01.png",
        "states": sorted(AVATAR_STATES),
        "emotions": sorted(EMOTIONS),
        "appearances": APPEARANCES,
        "actions": sorted(ACTIONS),
        "validation": validation,
        "rig": {"style": "segmented weighted-skin humanoid alpha", "humanoid_bones": 23, "spring_bone": True, "skinned_mesh": bool(validation.get('skinned_mesh')), "skin_count": validation.get('skin_count', 0), "expression_count": len(validation.get('expression_presets', [])) + len(validation.get('custom_expressions', [])), "runtime_controlled": True},
    }
