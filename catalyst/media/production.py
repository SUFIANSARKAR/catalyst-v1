from __future__ import annotations

import asyncio
from typing import Any


class MediaProductionError(RuntimeError):
    pass


class MediaProductionPipeline:
    """Turns a creative brief into a continuity-aware, renderable production.

    The provider remains replaceable. Catalyst owns planning, continuity metadata,
    reference chaining, bounded parallelism, artifact tracking and assembly.
    """

    def __init__(self, media_engine, planner):
        self.media = media_engine
        self.planner = planner

    def prepare(self, concept: str, mode: str = "video", style: str = "", shot_limit: int = 8,
                references: list[str] | None = None) -> dict[str, Any]:
        plan = self.planner.plan(concept, mode, style, shot_limit)
        supplied = list(references or [])
        character_contract = [
            {"name": c.get("name", ""), "appearance": c.get("appearance", ""),
             "wardrobe": c.get("wardrobe", ""), "continuity_notes": c.get("continuity_notes", "")}
            for c in plan.get("characters", []) if isinstance(c, dict)
        ]
        world = plan.get("world") or {}
        continuity = {
            "characters": character_contract,
            "world": world,
            "visual_style": plan.get("visual_style", style or "coherent cinematic realism"),
            "reference_ids": supplied,
            "rules": [
                "preserve character identity and wardrobe unless the shot explicitly changes them",
                "preserve environment and time-of-day continuity between adjacent shots",
                "preserve camera direction and screen geography unless intentionally changed",
                "carry the same visual style and lighting language across the sequence",
            ],
        }
        for scene in plan.get("scenes", []):
            for shot in scene.get("shots", []):
                if supplied:
                    refs = list(shot.get("references") or [])
                    for aid in supplied:
                        if aid not in refs:
                            refs.append(aid)
                    shot["references"] = refs[:16]
                shot["continuity_contract"] = continuity
                shot["generation_prompt"] = self.compile_prompt(plan, shot)
        plan["continuity_contract"] = continuity
        plan["production_protocol"] = "catalyst.media-production.v2"
        return plan

    @staticmethod
    def compile_prompt(plan: dict[str, Any], shot: dict[str, Any]) -> str:
        world = plan.get("world") or {}
        style = plan.get("visual_style") or "coherent cinematic realism"
        camera = shot.get("camera") or "medium shot, natural perspective"
        continuity = shot.get("continuity") or "Maintain visual continuity with adjacent shots."
        audio = shot.get("audio") or ""
        blocks = [
            f"VISUAL STYLE: {style}",
            f"WORLD: location={world.get('location','')}; time={world.get('time','')}; lighting={world.get('lighting','')}; palette={world.get('palette','')}",
            f"SHOT: {shot.get('prompt','')}",
            f"CAMERA: {camera}",
            f"CONTINUITY: {continuity}",
        ]
        if plan.get("characters"):
            blocks.append("CHARACTER BIBLE: " + "; ".join(
                f"{c.get('name','')}: {c.get('appearance','')}; wardrobe={c.get('wardrobe','')}" for c in plan["characters"] if isinstance(c, dict)
            ))
        if audio:
            blocks.append(f"AUDIO INTENT: {audio}")
        return "\n".join(x for x in blocks if x.strip())

    def flatten_shots(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        shots = []
        for scene in plan.get("scenes", []):
            for shot in scene.get("shots", []):
                item = dict(shot)
                item.setdefault("scene", scene.get("scene", ""))
                shots.append(item)
        return shots

    async def render(self, plan: dict[str, Any], provider: str | None = None,
                     mode: str | None = None, concurrency: int = 3,
                     chain_references: bool = True) -> dict[str, Any]:
        mode = mode or plan.get("mode", "video")
        shots = self.flatten_shots(plan)
        if not shots:
            raise MediaProductionError("Production plan contains no shots")
        limit = max(1, min(int(concurrency or 3), 8))
        auto_chain = bool(chain_references and mode == "image")

        async def render_one(shot: dict[str, Any], refs: list[str]):
            if mode == "image":
                produced = await self.media.generate_images(
                    shot.get("generation_prompt") or self.compile_prompt(plan, shot),
                    provider=provider, references=refs,
                    aspect_ratio=shot.get("aspect_ratio", "16:9"),
                    variants=min(int(shot.get("variants", 1) or 1), 4),
                    negative_prompt=shot.get("negative_prompt", ""),
                    options=shot.get("options") or {},
                )
                return produced
            produced = await self.media.generate_video(
                shot.get("generation_prompt") or self.compile_prompt(plan, shot),
                provider=provider, references=refs,
                aspect_ratio=shot.get("aspect_ratio", "16:9"),
                duration=int(shot.get("duration", 8) or 8),
                resolution=shot.get("resolution", "1080p"),
                audio=bool(shot.get("audio_enabled", True)),
                negative_prompt=shot.get("negative_prompt", ""),
                fps=shot.get("fps"), seed=shot.get("seed"),
                options=shot.get("options") or {},
            )
            return [produced]

        outputs: list[dict[str, Any]] = []
        if auto_chain:
            prior: list[str] = []
            for index, shot in enumerate(shots):
                refs = list(shot.get("references") or [])
                if prior:
                    refs = (prior[-1:] + refs)[:16]
                produced = await render_one(shot, refs)
                for item in produced:
                    if isinstance(item, dict):
                        item["shot_id"] = shot.get("id", f"SHOT_{index+1:02d}")
                        item["scene"] = shot.get("scene", "")
                        if item.get("name"):
                            prior.append(str(item["name"]))
                outputs.append({"shot": shot.get("id", f"SHOT_{index+1:02d}"), "outputs": produced, "references_used": refs})
        else:
            semaphore = asyncio.Semaphore(limit)
            async def parallel(index: int, shot: dict[str, Any]):
                refs = list(shot.get("references") or [])[:2 if mode == "video" else 16]
                async with semaphore:
                    produced = await render_one(shot, refs)
                for item in produced:
                    if isinstance(item, dict):
                        item["shot_id"] = shot.get("id", f"SHOT_{index+1:02d}")
                        item["scene"] = shot.get("scene", "")
                return {"index": index, "shot": shot.get("id", f"SHOT_{index+1:02d}"), "outputs": produced, "references_used": refs}
            rows = await asyncio.gather(*(parallel(i, shot) for i, shot in enumerate(shots)), return_exceptions=True)
            for index, row in enumerate(rows):
                if isinstance(row, Exception):
                    outputs.append({"index": index, "shot": shots[index].get("id", f"SHOT_{index+1:02d}"), "outputs": [], "error": str(row)})
                else:
                    outputs.append(row)
            outputs.sort(key=lambda x: x.get("index", 0))

        return {
            "protocol": "catalyst.media-production.v2",
            "mode": mode,
            "title": plan.get("title", "Catalyst Production"),
            "shot_count": len(shots),
            "results": outputs,
            "continuity_contract": plan.get("continuity_contract", {}),
        }
