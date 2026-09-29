from dataclasses import dataclass, field
from typing import Any

@dataclass
class Message:
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class TaskResult:
    answer: str
    steps: int
    tools_used: list[str]
    verified: bool
    stopped_reason: str = "completed"
