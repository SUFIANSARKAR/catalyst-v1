from dataclasses import dataclass
from typing import Any, Callable, List

@dataclass
class Tool: 
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    requires_approval: bool = False

class ToolRegistry:
    def __init__(self): self._tools: dict[str, Tool] = {}
    def register(self, tool: Tool) -> None: self._tools[tool.name] = tool
    def get(self, name: str) -> Tool | None: return self._tools.get(name)
    def list(self) -> List[Tool]: return list(self._tools.values())
    def schemas(self) -> List[dict[str, Any]]:
        return [{"type":"function","function":{"name":t.name,"description":t.description,"parameters":t.parameters}} for t in self._tools.values()]
