from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class Plugin:
    name: str
    description: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = False
    trusted: bool = False

class PluginRegistry:
    """Small, explicit plugin boundary. Plugins become visible capabilities, never implicit authority."""
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, plugin: Plugin):
        self._plugins[plugin.name] = plugin
        return plugin

    def register_tool(self, plugin_name: str, schema: dict, handler: Callable[..., Any]):
        if plugin_name not in self._plugins:
            raise KeyError(plugin_name)
        name = schema.get("function", {}).get("name")
        if not name:
            raise ValueError("Plugin tool schema must define function.name")
        self._plugins[plugin_name].tools.append(schema)
        self._handlers[name] = handler

    def enable(self, name: str):
        if name not in self._plugins: raise KeyError(name)
        self._plugins[name].enabled = True

    def disable(self, name: str):
        if name in self._plugins: self._plugins[name].enabled = False

    def list(self):
        return [
            {"name": p.name, "description": p.description, "enabled": p.enabled, "trusted": p.trusted,
             "tools": [s.get("function", {}).get("name") for s in p.tools]}
            for p in self._plugins.values()
        ]

    def enabled_schemas(self):
        out=[]
        for p in self._plugins.values():
            if p.enabled:
                out.extend(p.tools)
        return out

    def handler(self, tool_name: str):
        return self._handlers.get(tool_name)
