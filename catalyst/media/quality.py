from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any


class MediaQualityController:
    protocol = 'catalyst.media-quality.v2'

    @staticmethod
    def _path_from_output(item: dict[str, Any]) -> Path | None:
        raw = item.get('path') or item.get('artifact', {}).get('path') if isinstance(item, dict) else None
        if not raw:
            return None
        p = Path(str(raw))
        return p if p.exists() and p.is_file() else None

    @staticmethod
    def _image_dimensions(path: Path) -> tuple[int, int] | None:
        data = path.read_bytes()[:64 * 1024]
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            kind='png'
        elif data[:2] == b'\xff\xd8':
            kind='jpeg'
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            kind='webp'
        else:
            kind=None
        try:
            if kind == 'png' and len(data) >= 24:
                return struct.unpack('>II', data[16:24])
            if kind in {'jpeg', 'jpg'}:
                i = 2
                while i + 9 < len(data):
                    if data[i] != 0xFF:
                        i += 1
                        continue
                    marker = data[i + 1]
                    i += 2
                    if marker in {0xD8, 0xD9}:
                        continue
                    length = struct.unpack('>H', data[i:i + 2])[0]
                    if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                        if i + 7 < len(data):
                            h, w = struct.unpack('>HH', data[i + 3:i + 7])
                            return int(w), int(h)
                    i += max(2, length)
            if kind == 'webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                if data[12:16] == b'VP8X' and len(data) >= 30:
                    w = 1 + int.from_bytes(data[24:27], 'little')
                    h = 1 + int.from_bytes(data[27:30], 'little')
                    return w, h
        except Exception:
            return None
        return None

    @staticmethod
    def _ffprobe(path: Path) -> dict[str, Any] | None:
        if not shutil.which('ffprobe'):
            return None
        try:
            proc = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                capture_output=True, text=True, timeout=20,
            )
            if proc.returncode != 0:
                return None
            return json.loads(proc.stdout or '{}')
        except Exception:
            return None

    def inspect_artifact(self, item: dict[str, Any], *, expected_kind: str | None = None) -> dict[str, Any]:
        path = self._path_from_output(item)
        result = {
            'name': item.get('name'),
            'path': str(path) if path else item.get('path'),
            'exists': bool(path),
            'size_bytes': path.stat().st_size if path else 0,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path else None,
            'expected_kind': expected_kind,
            'detected_kind': None,
            'dimensions': None,
            'duration_seconds': None,
            'streams': 0,
            'technical_valid': False,
            'issues': [],
        }
        if not path:
            result['issues'].append('artifact-missing')
            return result
        ext = path.suffix.lower()
        if ext in {'.png', '.jpg', '.jpeg', '.webp', '.avif'}:
            result['detected_kind'] = 'image'
            result['dimensions'] = self._image_dimensions(path)
            if not result['dimensions']:
                result['issues'].append('image-dimensions-unreadable')
            if path.stat().st_size < 32:
                result['issues'].append('image-too-small')
        elif ext in {'.mp4', '.mov', '.webm', '.mkv', '.m4v'}:
            result['detected_kind'] = 'video'
            probe = self._ffprobe(path)
            if probe:
                result['streams'] = len(probe.get('streams') or [])
                fmt = probe.get('format') or {}
                try:
                    result['duration_seconds'] = float(fmt.get('duration')) if fmt.get('duration') else None
                except (TypeError, ValueError):
                    pass
                video_stream = next((x for x in probe.get('streams', []) if x.get('codec_type') == 'video'), None)
                if video_stream:
                    result['dimensions'] = [video_stream.get('width'), video_stream.get('height')]
                if not result['streams']:
                    result['issues'].append('no-media-streams')
            else:
                result['issues'].append('ffprobe-unavailable-or-invalid')
        elif ext in {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}:
            result['detected_kind'] = 'audio'
            probe = self._ffprobe(path)
            if probe:
                result['streams'] = len(probe.get('streams') or [])
                try:
                    result['duration_seconds'] = float((probe.get('format') or {}).get('duration')) if (probe.get('format') or {}).get('duration') else None
                except (TypeError, ValueError):
                    pass
            else:
                result['issues'].append('ffprobe-unavailable-or-invalid')
        else:
            result['detected_kind'] = mimetypes.guess_type(path.name)[0] or 'unknown'

        if expected_kind and result['detected_kind'] != expected_kind:
            result['issues'].append('unexpected-media-kind')
        result['technical_valid'] = bool(path) and not result['issues']
        return result

    def preflight(self, plan):
        shots = [s for sc in plan.get('scenes', []) or [] for s in sc.get('shots', []) or []]
        issues = []
        if not shots: issues.append('no-shots')
        ids = [str(s.get('id', '')) for s in shots]
        if len(ids) != len(set(ids)): issues.append('duplicate-shot-ids')
        for i, s in enumerate(shots, 1):
            if not (s.get('generation_prompt') or s.get('prompt')): issues.append(f'shot-{i}-missing-prompt')
            if plan.get('mode', 'video') == 'video' and int(s.get('duration', 0) or 0) <= 0: issues.append(f'shot-{i}-invalid-duration')
            if not s.get('continuity_contract'): issues.append(f'shot-{i}-missing-continuity-contract')
        return {'protocol': self.protocol, 'stage': 'preflight', 'shot_count': len(shots), 'issues': issues, 'ready': not issues}

    def manifest(self, plan, results):
        expected = {str(s.get('id')) for sc in plan.get('scenes', []) or [] for s in sc.get('shots', []) or []}
        produced = {str(r.get('shot')) for r in results if r.get('outputs')}
        missing = sorted(expected - produced)
        inspections = []
        for row in results:
            mode = 'video' if plan.get('mode') == 'video' else 'image'
            for out in row.get('outputs', []) or []:
                if isinstance(out, dict):
                    inspections.append(self.inspect_artifact(out, expected_kind=mode))
        duplicates = {}
        for item in inspections:
            digest = item.get('sha256')
            if digest:
                duplicates[digest] = duplicates.get(digest, 0) + 1
        duplicate_artifacts = sorted([d for d, count in duplicates.items() if count > 1])
        technical_ok = bool(inspections) and all(x.get('technical_valid') for x in inspections)
        return {
            'protocol': self.protocol,
            'expected_shots': len(expected),
            'produced_shots': len(produced),
            'missing_shots': missing,
            'coverage_complete': not missing,
            'artifacts_inspected': len(inspections),
            'technical_quality_verified': technical_ok,
            'duplicate_artifact_hashes': duplicate_artifacts,
            'inspection': inspections[:200],
            'pixel_quality_verified': False,
            'note': 'Pixel-level visual quality requires an actual vision/evaluation provider; technical validity is checked locally.'
        }
