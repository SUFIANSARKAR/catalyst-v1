import json, os, shlex, subprocess, tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from ..agent_protocol import normalize_result

@dataclass
class AgentAdapter:
    name: str
    description: str
    command: str | None = None
    timeout: int = 900
    protocol: str = 'text'
    env: dict[str, str] = field(default_factory=dict)

    def available(self):
        return bool(self.command and self.command.strip())

    def run(self, task: str, cwd: str, task_id: str | None = None) -> dict[str, Any]:
        if not self.available():
            return {'status': 'unconfigured', 'agent': self.name, 'message': 'No command configured.'}
        workdir = str(Path(cwd).resolve())
        request = {
            'protocol': 'catalyst.agent.v1',
            'task_id': task_id,
            'agent': self.name,
            'task': task,
            'cwd': workdir,
        }
        command = self.command
        if self.protocol == 'json':
            command = command.replace('{task}', shlex.quote(task))
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.json', delete=False) as f:
                json.dump(request, f, ensure_ascii=False)
                request_path = f.name
            try:
                env = os.environ.copy(); env.update(self.env); env['CATALYST_AGENT_REQUEST'] = request_path
                env['CATALYST_AGENT_PROTOCOL'] = 'catalyst.agent.v1'
                cp = subprocess.run(command, shell=True, cwd=workdir, text=True, capture_output=True, timeout=self.timeout, env=env)
            finally:
                try: Path(request_path).unlink()
                except OSError: pass
        else:
            command = command.replace('{task}', shlex.quote(task))
            env = os.environ.copy(); env.update(self.env)
            cp = subprocess.run(command, shell=True, cwd=workdir, text=True, capture_output=True, timeout=self.timeout, env=env)
        parsed = self._parse_output(cp.stdout)
        result = {
            'status': 'completed' if cp.returncode == 0 else 'failed',
            'returncode': cp.returncode,
            'stdout': cp.stdout[-50000:],
            'stderr': cp.stderr[-20000:],
            'agent': self.name,
        }
        if isinstance(parsed, dict):
            result.update({k: v for k, v in normalize_result(parsed, self.name, task_id or '').items() if k not in {'stdout', 'stderr', 'agent'}})
            result['protocol'] = 'catalyst.agent.v1'
        result['capability_contract'] = ['summary','artifacts','tests','commits','evidence']
        return result

    @staticmethod
    def _parse_output(stdout: str):
        text = stdout.strip()
        if not text:
            return None
        for candidate in (text, text.splitlines()[-1]):
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except (TypeError, ValueError):
                pass
        return None


def default_adapters():
    return [
        AgentAdapter('tc_engineering_ai', 'Specialist engineering system', os.getenv('CATALYST_TC_AGENT_CMD'), protocol=os.getenv('CATALYST_TC_AGENT_PROTOCOL', 'json')),
        AgentAdapter('full_self_coding', 'Multi-task coding backend', os.getenv('CATALYST_SELF_CODING_CMD'), protocol=os.getenv('CATALYST_SELF_CODING_PROTOCOL', 'json')),
        AgentAdapter('openhands', 'OpenHands-compatible coding backend', os.getenv('CATALYST_OPENHANDS_CMD'), protocol=os.getenv('CATALYST_OPENHANDS_PROTOCOL', 'json')),
    ]
