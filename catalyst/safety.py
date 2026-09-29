from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class AuditEvent:
    action: str
    detail: str
    ts: str

class AuditLog:
    def __init__(self, memory): self.memory=memory
    def record(self, action: str, detail: str) -> None:
        self.memory.add(detail,"audit",{"action":action,"timestamp":datetime.now(timezone.utc).isoformat()})
