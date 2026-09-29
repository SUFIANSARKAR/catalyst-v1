from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class DurabilityManager:
    """Protect Catalyst's durable state from restarts and deployment mistakes.

    Backups are self-describing ZIP snapshots. Secrets are excluded by default;
    provider credentials must be backed up through the deployment secret manager.
    """

    EXCLUDED_PARTS = {"secrets.json", "attachments", "artifacts", "realtime_voice", "backups"}

    def __init__(self, data_root: str, memory_path: str | None = None, mind_path: str | None = None):
        self.root = Path(data_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.memory_path = Path(memory_path).resolve() if memory_path else self.root / "memory.db"
        self.mind_path = Path(mind_path).resolve() if mind_path else self.root / "mind.db"

    def _safe_files(self):
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root)
            if any(part in self.EXCLUDED_PARTS for part in rel.parts):
                continue
            if path.name.endswith((".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm")):
                continue
            yield path, rel

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def status(self) -> dict:
        files = list(self._safe_files())
        total = sum(path.stat().st_size for path, _ in files)
        writable = os.access(self.root, os.W_OK)
        return {
            "data_root": str(self.root),
            "exists": self.root.exists(),
            "writable": writable,
            "persistent_state_files": len(files),
            "bytes": total,
            "memory_exists": self.memory_path.exists(),
            "mind_exists": self.mind_path.exists(),
            "backup_ready": writable and self.root.exists(),
            "excluded": sorted(self.EXCLUDED_PARTS),
        }

    def snapshot(self, destination: str | None = None) -> str:
        backup_dir = Path(destination).resolve() if destination else self.root / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = backup_dir / f"catalyst-state-{stamp}.zip"
        manifest = []
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path, rel in self._safe_files():
                archive.write(path, rel.as_posix())
                manifest.append({"path": rel.as_posix(), "bytes": path.stat().st_size, "sha256": self._sha256(path)})
            metadata = {
                "format": "catalyst-durable-state-v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "data_root": str(self.root),
                "files": manifest,
                "secrets_excluded": True,
            }
            archive.writestr("MANIFEST.json", json.dumps(metadata, indent=2, sort_keys=True))
        return str(output)

    def export_memory_json(self, destination: str | None = None) -> str:
        """Export the two cognitive databases into a portable JSON document."""
        output = Path(destination).resolve() if destination else self.root / "backups" / "catalyst-memory-export.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": "catalyst-memory-export-v1", "created_at": datetime.now(timezone.utc).isoformat(), "mind": [], "memory": []}
        if self.mind_path.exists():
            with sqlite3.connect(self.mind_path) as db:
                db.row_factory = sqlite3.Row
                try:
                    payload["mind"] = [dict(row) for row in db.execute("SELECT * FROM cognitive_memory ORDER BY updated_at").fetchall()]
                except sqlite3.OperationalError:
                    pass
        if self.memory_path.exists():
            with sqlite3.connect(self.memory_path) as db:
                db.row_factory = sqlite3.Row
                try:
                    payload["memory"] = [dict(row) for row in db.execute("SELECT * FROM memories ORDER BY ts").fetchall()]
                except sqlite3.OperationalError:
                    pass
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        try:
            os.chmod(output, 0o600)
        except OSError:
            pass
        return str(output)

    def restore(self, snapshot: str) -> dict:
        """Restore a verified snapshot without allowing archive path escapes."""
        source = Path(snapshot).resolve()
        if not source.exists() or not zipfile.is_zipfile(source):
            raise ValueError("snapshot must be an existing ZIP archive")
        with zipfile.ZipFile(source) as archive:
            try:
                manifest = json.loads(archive.read("MANIFEST.json"))
            except KeyError as exc:
                raise ValueError("snapshot manifest is missing") from exc
            restored = 0
            for item in manifest.get("files", []):
                rel = Path(str(item.get("path", "")))
                if not rel.parts or rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("snapshot contains an unsafe path")
                target = (self.root / rel).resolve()
                if self.root not in target.parents:
                    raise ValueError("snapshot path escapes data root")
                payload = archive.read(rel.as_posix())
                if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
                    raise ValueError(f"snapshot checksum failed for {rel}")
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix(target.suffix + ".restore-tmp")
                temp.write_bytes(payload)
                os.replace(temp, target)
                restored += 1
        return {"restored": restored, "format": manifest.get("format"), "snapshot": str(source)}
