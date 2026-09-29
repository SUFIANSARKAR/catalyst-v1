from __future__ import annotations

import re

ENGINEERING_SOURCES = {
    "physicsnemo": {
        "name": "NVIDIA PhysicsNeMo",
        "role": "physics_ai",
        "license": "Apache-2.0",
        "source": "attached:physicsnemo-main.zip",
        "capabilities": [
            "physics_ai_models", "mesh_and_domain_representation", "physics_informed_workflows",
            "graph_and_operator_models", "diffusion_workflows", "active_learning",
            "scientific_datapipes", "metrics", "optimization", "distributed_domain_parallelism",
        ],
        "domains": [
            "engineering_design", "cfd", "structural_mechanics", "weather",
            "geophysics", "additive_manufacturing", "data_center_thermal",
        ],
    },
    "pyvista": {
        "name": "PyVista",
        "role": "geometry_visualization",
        "license": "MIT",
        "source": "attached:pyvista-main.zip",
        "capabilities": [
            "mesh_io", "mesh_analysis", "dataset_filters", "surface_analysis",
            "volumetric_analysis", "3d_plotting", "headless_rendering", "plugin_accessors",
        ],
        "domains": ["geometry", "meshes", "scientific_visualization", "engineering_postprocessing"],
    },
}


class EngineeringCatalog:
    """Curated, dependency-neutral map of engineering/science capabilities.

    The catalog is metadata-first so Catalyst can reason about available engineering
    pathways without importing heavyweight scientific runtimes.
    """

    @staticmethod
    def list_sources() -> list[dict]:
        return [{"id": key, **value} for key, value in ENGINEERING_SOURCES.items()]

    @staticmethod
    def source(source_id: str) -> dict | None:
        value = ENGINEERING_SOURCES.get(source_id)
        return {"id": source_id, **value} if value else None

    @staticmethod
    def find_for_domain(query: str) -> list[dict]:
        q = (query or "").lower()
        scored = []
        for sid, item in ENGINEERING_SOURCES.items():
            hay = " ".join(
                [item["name"], item["role"], *item["capabilities"], *item["domains"]]
            ).lower()
            score = sum(1 for token in re.findall(r"[\w-]{3,}", q) if token in hay)
            if score:
                scored.append((score, {"id": sid, **item}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]
