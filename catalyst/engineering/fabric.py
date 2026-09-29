from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from .catalog import EngineeringCatalog


class OptionalRuntime:
    def __init__(self, module: str):
        self.module = module

    @property
    def installed(self) -> bool:
        return importlib.util.find_spec(self.module) is not None


class PyVistaAdapter:
    """Optional geometry/mesh adapter. Catalyst remains usable without PyVista."""

    module = "pyvista"

    def __init__(self):
        self.runtime = OptionalRuntime(self.module)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "pyvista",
            "installed": self.runtime.installed,
            "mode": "optional-runtime",
            "capabilities": EngineeringCatalog.source("pyvista")["capabilities"],
        }

    def inspect(self, path: str) -> dict[str, Any]:
        if not self.runtime.installed:
            raise RuntimeError("PyVista is not installed in this environment.")
        import pyvista as pv  # type: ignore

        mesh = pv.read(path)
        result: dict[str, Any] = {
            "path": str(Path(path).resolve()),
            "dataset_type": type(mesh).__name__,
            "n_points": int(mesh.n_points),
            "n_cells": int(mesh.n_cells),
            "bounds": [float(x) for x in mesh.bounds],
            "arrays": [],
        }
        for name in list(mesh.point_data.keys()):
            arr = mesh.point_data[name]
            result["arrays"].append({
                "association": "point",
                "name": name,
                "components": int(getattr(arr, "n_components", 1)),
                "size": int(len(arr)),
            })
        for name in list(mesh.cell_data.keys()):
            arr = mesh.cell_data[name]
            result["arrays"].append({
                "association": "cell",
                "name": name,
                "components": int(getattr(arr, "n_components", 1)),
                "size": int(len(arr)),
            })
        return result


class PhysicsNeMoAdapter:
    """Optional PhysicsNeMo capability bridge.

    This intentionally does not import or execute models automatically. Catalyst
    can use the catalog to select a physics-AI workflow and only load the user's
    configured runtime/model inside an explicit engineering job.
    """

    module = "physicsnemo"

    def __init__(self):
        self.runtime = OptionalRuntime(self.module)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "physicsnemo",
            "installed": self.runtime.installed,
            "mode": "optional-runtime",
            "capabilities": EngineeringCatalog.source("physicsnemo")["capabilities"],
            "domains": EngineeringCatalog.source("physicsnemo")["domains"],
        }


class EngineeringIntelligenceFabric:
    """Engineering/science orchestration layer built as additive adapters."""

    protocol = "catalyst.engineering.v1"

    def __init__(self, workspace_root: str, data_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.pyvista = PyVistaAdapter()
        self.physicsnemo = PhysicsNeMoAdapter()
        from .repository import RepositoryIntelligence
        from .strategy import EngineeringTestStrategy
        self.repository = RepositoryIntelligence(str(self.workspace_root))
        self.test_strategy = EngineeringTestStrategy(str(self.workspace_root))

    def status(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "runtimes": [self.pyvista.status(), self.physicsnemo.status()],
            "catalog": EngineeringCatalog.list_sources(),
        }

    def recommend(self, objective: str) -> dict[str, Any]:
        matches = EngineeringCatalog.find_for_domain(objective)
        return {
            "protocol": self.protocol,
            "objective": objective,
            "candidates": matches,
            "recommendation": matches[0] if matches else None,
            "note": "Recommendations are capability routing, not proof that a model is suitable for the user's specific physics or data.",
        }

    def inspect_geometry(self, relative_or_absolute_path: str) -> dict[str, Any]:
        path = Path(relative_or_absolute_path)
        if not path.is_absolute():
            path = (self.workspace_root / path).resolve()
        if path != self.workspace_root and self.workspace_root not in path.parents:
            raise PermissionError("Path escapes workspace.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        return self.pyvista.inspect(str(path))
