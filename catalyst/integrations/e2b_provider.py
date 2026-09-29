from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class E2BResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    sandbox_id: str | None

class E2BSandboxProvider:
    """Optional E2B execution provider; local Docker remains Catalyst's default."""
    def __init__(self, *, api_key: str | None = None, timeout: int = 300, allow_internet: bool = False):
        self.api_key = api_key
        self.timeout = max(10, int(timeout))
        self.allow_internet = bool(allow_internet)
        self._sandboxes: dict[str, Any] = {}

    async def create(self, *, template: str | None = None, metadata: dict[str, str] | None = None) -> str:
        try:
            from e2b import AsyncSandbox
        except ImportError as exc:
            raise RuntimeError('E2B SDK is not installed; install the optional E2B provider.') from exc
        kwargs = {'timeout': self.timeout, 'secure': True, 'allow_internet_access': self.allow_internet}
        if template: kwargs['template'] = template
        if metadata: kwargs['metadata'] = metadata
        if self.api_key: kwargs['api_key'] = self.api_key
        sandbox = await AsyncSandbox.create(**kwargs)
        sid = sandbox.sandbox_id
        self._sandboxes[sid] = sandbox
        return sid

    async def run(self, sandbox_id: str, command: str, *, cwd: str | None = None, timeout: int = 60) -> E2BResult:
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox is None: raise KeyError(sandbox_id)
        result = await sandbox.commands.run(command, cwd=cwd, timeout=max(1, int(timeout)))
        return E2BResult('completed' if result.exit_code == 0 else 'failed', result.exit_code, result.stdout, result.stderr, sandbox_id)

    async def close(self, sandbox_id: str) -> None:
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox is not None:
            await sandbox.kill()
