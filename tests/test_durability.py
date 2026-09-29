import json
import zipfile

from catalyst.durability import DurabilityManager
from catalyst.memory import MemoryStore
from catalyst.mind import CatalystMind


def test_durability_snapshot_and_memory_export(tmp_path):
    data = tmp_path / "data"
    memory_path = data / "memory.db"
    mind_path = data / "mind.db"
    memory = MemoryStore(str(memory_path))
    memory.add("Creator prefers concise mission briefs", "preference", importance=.9)
    mind = CatalystMind(str(mind_path), memory)
    mind.ensure_core_identity()
    manager = DurabilityManager(str(data), str(memory_path), str(mind_path))

    status = manager.status()
    assert status["writable"] is True
    assert status["memory_exists"] is True
    assert status["mind_exists"] is True

    snapshot = manager.snapshot()
    with zipfile.ZipFile(snapshot) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        names = set(archive.namelist())
    assert manifest["format"] == "catalyst-durable-state-v1"
    assert "memory.db" in names and "mind.db" in names
    assert "secrets.json" not in names

    exported = manager.export_memory_json()
    payload = json.loads((data / "backups" / "catalyst-memory-export.json").read_text())
    assert exported.endswith("catalyst-memory-export.json")
    assert len(payload["mind"]) >= 2
    assert any("Creator prefers" in str(row) for row in payload["memory"])

    restored_root = tmp_path / "restored"
    restored = DurabilityManager(str(restored_root))
    result = restored.restore(snapshot)
    assert result["restored"] >= 2
    assert (restored_root / "memory.db").exists()
    assert (restored_root / "mind.db").exists()
