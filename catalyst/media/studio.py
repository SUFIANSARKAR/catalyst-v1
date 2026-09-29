from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .production import MediaProductionPipeline
from .quality import MediaQualityController


@dataclass
class StudioRenderResult:
    protocol: str
    status: str
    plan: dict[str, Any]
    results: dict[str, Any]
    quality: dict[str, Any]
    retries: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "status": self.status,
            "plan": self.plan,
            "results": self.results,
            "quality": self.quality,
            "retries": self.retries,
        }


class MediaStudio:
    """Production supervisor above the existing provider-backed media engine.

    Catalyst owns the creative production contract; providers only perform generation.
    The studio adds asset identity, prompt fingerprints, continuity-aware retries and
    honest completion reporting.
    """

    protocol = "catalyst.media-studio.v1"

    def __init__(self, pipeline: MediaProductionPipeline, quality: MediaQualityController):
        self.pipeline = pipeline
        self.quality = quality

    @staticmethod
    def _fingerprint(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def prepare(self, concept: str, mode: str = "video", style: str = "", shot_limit: int = 8,
                references: list[str] | None = None) -> dict[str, Any]:
        plan = self.pipeline.prepare(concept, mode, style, shot_limit, references or [])
        assets: list[dict[str, Any]] = []
        for scene in plan.get("scenes", []) or []:
            for shot in scene.get("shots", []) or []:
                prompt = str(shot.get("generation_prompt") or shot.get("prompt") or "")
                shot["prompt_fingerprint"] = self._fingerprint(prompt)
                shot["production_role"] = "hero" if str(shot.get("id", "")).endswith("SH01") else "supporting"
                shot["quality_contract"] = {
                    "prompt_present": bool(prompt.strip()),
                    "continuity_present": bool(shot.get("continuity_contract")),
                    "reference_chain_allowed": bool(mode == "image" or shot.get("references")),
                    "metadata_only_quality": False,
                }
                assets.append({"shot_id": shot.get("id"), "fingerprint": shot["prompt_fingerprint"], "scene": scene.get("scene", "")})
        plan["studio_protocol"] = self.protocol
        plan["asset_manifest"] = assets
        plan["postproduction"] = {
            "video": ["render", "coverage-check", "continuity-review", "assembly-ready"],
            "image": ["render", "coverage-check", "continuity-review", "gallery-ready"],
        }.get(mode, ["render", "coverage-check"])
        return plan

    def preflight(self, plan: dict[str, Any]) -> dict[str, Any]:
        base = self.quality.preflight(plan)
        fingerprints = [str(s.get("prompt_fingerprint", "")) for sc in plan.get("scenes", []) or [] for s in sc.get("shots", []) or []]
        base["studio_protocol"] = self.protocol
        base["duplicate_prompt_fingerprints"] = len(fingerprints) - len(set(fingerprints)) if fingerprints else 0
        base["ready"] = bool(base.get("ready")) and base["duplicate_prompt_fingerprints"] == 0
        return base

    async def render(self, plan: dict[str, Any], provider: str | None = None, concurrency: int = 3,
                     chain_references: bool = True, max_retries: int = 2) -> StudioRenderResult:
        preflight = self.preflight(plan)
        if not preflight["ready"]:
            raise ValueError("Media studio preflight failed: " + json.dumps(preflight, ensure_ascii=False))
        attempt = 0
        final: dict[str, Any] = {"results": []}
        failed_shots: list[dict[str, Any]] = []
        current_plan = plan
        while True:
            rendered = await self.pipeline.render(current_plan, provider=provider, concurrency=concurrency,
                                                  chain_references=chain_references)
            final = rendered
            failed_shots = [row for row in rendered.get("results", []) if row.get("error") or not row.get("outputs")]
            if not failed_shots or attempt >= max(0, min(int(max_retries), 4)):
                break
            attempt += 1
            failed_ids = {str(row.get("shot")) for row in failed_shots}
            for scene in current_plan.get("scenes", []) or []:
                for shot in scene.get("shots", []) or []:
                    if str(shot.get("id")) in failed_ids:
                        shot["generation_prompt"] = (
                            str(shot.get("generation_prompt") or shot.get("prompt") or "")
                            + "\nRECOVERY PASS: correct continuity, subject identity, framing and temporal consistency; preserve all established story facts."
                        )
        expected_plan = {"plan": current_plan, "studio_attempts": attempt + 1}
        quality = self.quality.manifest(current_plan, list(final.get("results", [])))
        status = "completed" if quality.get("coverage_complete") else "partial"
        return StudioRenderResult(self.protocol, status, expected_plan, final, quality, attempt)

    def render_sync(self, plan: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return asyncio.run(self.render(plan, **kwargs)).as_dict()
