import json, shutil
from datetime import datetime, timezone
from pathlib import Path

class ExportManager:
    def __init__(self, data_root:str): self.data=Path(data_root).resolve()
    def export(self,destination:str):
        dest=Path(destination).resolve();dest.mkdir(parents=True,exist_ok=True)
        bundle=dest/f"catalyst-export-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}";bundle.mkdir()
        for name in ("memory.db","sessions.db","tasks.db","audit.db","automations.db","project_index.json","chunks.db"):
            src=self.data/name
            if src.exists(): shutil.copy2(src,bundle/name)
        for d in ("projects","sessions"):
            src=self.data/d
            if src.exists(): shutil.copytree(src,bundle/d,dirs_exist_ok=True)
        return str(bundle)
