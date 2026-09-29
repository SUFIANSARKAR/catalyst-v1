from __future__ import annotations

import json
import os
import subprocess
import time
import shutil
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx


@dataclass
class IntegrationResult:
    provider: str
    status: str
    task_id: str | None = None
    state: str | None = None
    answer: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[Any] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'provider': self.provider,
            'status': self.status,
            'task_id': self.task_id,
            'state': self.state,
            'answer': self.answer,
            'events': self.events[-200:],
            'artifacts': self.artifacts,
            'evidence': self.evidence,
            'raw': self.raw,
            'error': self.error,
        }


def _safe_base_url(url: str) -> str:
    value = (url or '').strip().rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Integration URL must be an absolute http(s) URL')
    return value


class TCIntegration:
    """Native HTTP contract for the TC ENGINEERING AI Phase-7 orchestrator."""
    name = 'tc_engineering_ai'

    def __init__(self, base_url: str, owner_token: str = '', timeout: float = 30):
        self.base_url = _safe_base_url(base_url) if base_url else ''
        self.owner_token = owner_token
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def health(self) -> IntegrationResult:
        if not self.configured:
            return IntegrationResult(self.name, 'unconfigured')
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(f'{self.base_url}/health')
                r.raise_for_status(); data = r.json()
            return IntegrationResult(self.name, 'healthy', state=data.get('status'), raw=data)
        except Exception as exc:
            return IntegrationResult(self.name, 'unreachable', error=str(exc))

    def submit(self, prompt: str, wait: bool = True, poll_seconds: float = 1.0, timeout: float = 900) -> IntegrationResult:
        if not self.configured:
            return IntegrationResult(self.name, 'unconfigured', error='CATALYST_TC_URL is not configured')
        headers = {'Accept': 'application/json'}
        if self.owner_token:
            headers['x-tc-owner-token'] = self.owner_token
        try:
            with httpx.Client(timeout=self.timeout) as c:
                response = c.post(f'{self.base_url}/v1/tasks', json={'prompt': prompt}, headers=headers)
                response.raise_for_status(); data = response.json()
                owner = response.headers.get('x-tc-owner-token')
                task_id = data.get('task_id')
            if owner and not self.owner_token:
                self.owner_token = owner
            if not wait or not task_id:
                return IntegrationResult(self.name, 'submitted', task_id=task_id, state=data.get('status'), raw=data)
            return self.wait(task_id, timeout=timeout, poll_seconds=poll_seconds)
        except Exception as exc:
            return IntegrationResult(self.name, 'failed', error=str(exc))

    def get_task(self, task_id: str) -> IntegrationResult:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f'{self.base_url}/v1/tasks/{task_id}'); r.raise_for_status(); data = r.json()
        return IntegrationResult(self.name, 'ok', task_id=task_id, state=data.get('status'), answer=data.get('answer'), raw=data)

    def events(self, task_id: str) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f'{self.base_url}/v1/tasks/{task_id}/events'); r.raise_for_status(); return r.json()

    def wait(self, task_id: str, timeout: float = 900, poll_seconds: float = 1.0) -> IntegrationResult:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.get_task(task_id)
            events = self.events(task_id)
            result.events = events
            if result.state in {'completed', 'failed'}:
                return result
            time.sleep(max(0.25, poll_seconds))
        return IntegrationResult(self.name, 'timeout', task_id=task_id, state='timeout', events=self.events(task_id))

    def approve(self, task_id: str, nonce: str, decided_by: str = 'Catalyst') -> IntegrationResult:
        headers = {'x-tc-owner-token': self.owner_token} if self.owner_token else {}
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f'{self.base_url}/v1/tasks/{task_id}/approve', json={'nonce': nonce, 'decided_by': decided_by}, headers=headers)
            r.raise_for_status(); data = r.json()
        return IntegrationResult(self.name, 'ok', task_id=task_id, state=data.get('status'), answer=data.get('answer'), raw=data)

    def reject(self, task_id: str, nonce: str, decided_by: str = 'Catalyst') -> IntegrationResult:
        headers = {'x-tc-owner-token': self.owner_token} if self.owner_token else {}
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f'{self.base_url}/v1/tasks/{task_id}/reject', json={'nonce': nonce, 'decided_by': decided_by}, headers=headers)
            r.raise_for_status(); data = r.json()
        return IntegrationResult(self.name, 'ok', task_id=task_id, state=data.get('status'), answer=data.get('answer'), raw=data)


class FSCIntegration:
    """Structured wrapper around Full Self Coding's documented CLI workflow.

    FSC is a local Bun/TypeScript program rather than an HTTP service, so Catalyst
    invokes the CLI with an explicit repository and config, then normalizes its
    final report into Catalyst's common result contract.
    """
    name = 'full_self_coding'

    def __init__(self, command: str | None = None, timeout: int = 3600):
        self.command = command or os.getenv('CATALYST_SELF_CODING_CMD', 'full-self-coding')
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        token=self.command.strip().split()[0] if self.command.strip() else ''
        return bool(token and (shutil.which(token) or os.path.exists(token)))

    def run(self, cwd: str, config: dict[str, Any] | None = None, timeout: int | None = None) -> IntegrationResult:
        config = config or {}
        timeout = timeout or self.timeout
        if not self.configured:
            return IntegrationResult(self.name, 'unconfigured')
        cfg_path = None
        try:
            import tempfile
            fd, cfg_path = tempfile.mkstemp(prefix='catalyst-fsc-', suffix='.json')
            os.close(fd)
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            command = f"{self.command} run --config {json.dumps(cfg_path)}"
            cp = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True, timeout=timeout)
            status = 'completed' if cp.returncode == 0 else 'failed'
            parsed = self._parse_json(cp.stdout)
            return IntegrationResult(self.name, status, answer=self._answer(parsed), artifacts=self._artifacts(parsed), raw=parsed or {'stdout': cp.stdout[-30000:], 'stderr': cp.stderr[-12000:]}, error=None if cp.returncode == 0 else cp.stderr[-4000:])
        except subprocess.TimeoutExpired:
            return IntegrationResult(self.name, 'timeout', state='timeout', error=f'FSC timed out after {timeout}s')
        except Exception as exc:
            return IntegrationResult(self.name, 'failed', error=str(exc))
        finally:
            if cfg_path:
                try: os.unlink(cfg_path)
                except OSError: pass

    @staticmethod
    def _parse_json(stdout: str) -> dict[str, Any] | None:
        text = (stdout or '').strip()
        for candidate in reversed(text.splitlines()):
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict): return obj
            except Exception: continue
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    @staticmethod
    def _answer(data: dict[str, Any] | None) -> str | None:
        if not data: return None
        for key in ('answer', 'report', 'message', 'summary'):
            if data.get(key): return str(data[key])
        return None

    @staticmethod
    def _artifacts(data: dict[str, Any] | None) -> list[Any]:
        if not data: return []
        value = data.get('artifacts') or data.get('reports') or []
        return value if isinstance(value, list) else [value]


class SWEAgentIntegration:
    """Optional bridge to the supplied SWE-agent 1.x CLI.

    The supplied project documents `sweagent run` for single issue/problem
    execution and supports repository/problem-statement configuration. Catalyst
    keeps this integration opt-in and subprocess-isolated: it never embeds the
    SWE-agent source tree or assumes undocumented HTTP APIs.
    """
    name = 'swe_agent'

    def __init__(self, command: str | None = None, timeout: int = 3600):
        self.command = (command or os.getenv('CATALYST_SWEAGENT_CMD', 'sweagent')).strip()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        if not self.command:
            return False
        first = self.command.split()[0]
        return bool(shutil.which(first) or os.path.exists(first))

    def run(self, *, repo_path: str | None = None, github_url: str | None = None,
            problem_path: str | None = None, problem_github_url: str | None = None,
            config: str | None = None, model: str | None = None,
            output_dir: str | None = None, extra_args: list[str] | None = None,
            timeout: int | None = None) -> IntegrationResult:
        if not self.configured:
            return IntegrationResult(self.name, 'unconfigured',
                                     error='CATALYST_SWEAGENT_CMD is not configured or executable')
        import shlex
        args = shlex.split(self.command)
        args += ['run']
        if config: args += ['--config', config]
        if model: args += ['--agent.model.name', model]
        if repo_path: args += ['--env.repo.path', repo_path]
        elif github_url: args += [f'--env.repo.github_url={github_url}']
        if problem_path: args += [f'--problem_statement.path={problem_path}']
        elif problem_github_url: args += [f'--problem_statement.github_url={problem_github_url}']
        if output_dir: args += ['--output_dir', output_dir]
        args += list(extra_args or [])
        timeout = timeout or self.timeout
        try:
            cp = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
            stdout, stderr = cp.stdout[-30000:], cp.stderr[-12000:]
            status = 'completed' if cp.returncode == 0 else 'failed'
            raw = {'returncode': cp.returncode, 'stdout': stdout, 'stderr': stderr, 'command': args}
            return IntegrationResult(self.name, status, answer=stdout[-8000:] if stdout else None,
                                     raw=raw, error=None if cp.returncode == 0 else stderr[-4000:])
        except subprocess.TimeoutExpired:
            return IntegrationResult(self.name, 'timeout', state='timeout',
                                     error=f'SWE-agent timed out after {timeout}s')
        except Exception as exc:
            return IntegrationResult(self.name, 'failed', error=str(exc))

    def descriptor(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'provider': self.name,
            'configured': self.configured,
            'kind': 'native-cli',
            'capabilities': ['issue-solving', 'repository-editing', 'trajectory-output', 'custom-coding-tasks'],
            'source_note': 'Optional integration for the supplied SWE-agent project; its README notes mini-SWE-agent as the current successor.'
        }


class OpenHandsIntegration:
    """Deployment-aware OpenHands Cloud connector.

    The uploaded 0.55.0 repository is the Cloud/Helm deployment layer; it does
    not include the core OpenHands task API. Catalyst therefore treats the app
    URL and optional runtime API URL as configured capabilities rather than
    inventing undocumented endpoint semantics.
    """
    name = 'openhands'

    def __init__(self, app_url: str = '', runtime_url: str = '', timeout: float = 20):
        self.app_url = _safe_base_url(app_url) if app_url else ''
        self.runtime_url = _safe_base_url(runtime_url) if runtime_url else ''
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.app_url or self.runtime_url)

    def health(self) -> IntegrationResult:
        if not self.configured:
            return IntegrationResult(self.name, 'unconfigured')
        checks: dict[str, Any] = {}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as c:
                if self.app_url:
                    try:
                        r = c.get(self.app_url); checks['app'] = r.status_code
                    except Exception as exc: checks['app_error'] = str(exc)
                if self.runtime_url:
                    try:
                        r = c.get(self.runtime_url); checks['runtime'] = r.status_code
                    except Exception as exc: checks['runtime_error'] = str(exc)
            return IntegrationResult(self.name, 'healthy' if any(isinstance(v, int) and v < 500 for v in checks.values()) else 'unreachable', raw=checks)
        except Exception as exc:
            return IntegrationResult(self.name, 'unreachable', error=str(exc))

    def descriptor(self) -> dict[str, Any]:
        return {
            'provider': self.name,
            'configured': self.configured,
            'app_url': self.app_url or None,
            'runtime_url': self.runtime_url or None,
            'note': 'Core task endpoints require the OpenHands runtime/API contract; the uploaded Cloud repo supplies deployment/Helm configuration.'
        }


class IntegrationFabric:
    def __init__(self, settings):
        self.settings = settings
        self.tc = TCIntegration(getattr(settings, 'tc_url', ''), getattr(settings, 'tc_owner_token', ''))
        self.fsc = FSCIntegration(getattr(settings, 'fsc_command', ''), getattr(settings, 'fsc_timeout', 3600))
        self.openhands = OpenHandsIntegration(getattr(settings, 'openhands_url', ''), getattr(settings, 'openhands_runtime_url', ''))
        self.sweagent = SWEAgentIntegration(getattr(settings, 'sweagent_command', ''), getattr(settings, 'sweagent_timeout', 3600))

    def describe(self) -> list[dict[str, Any]]:
        return [
            {'name': 'tc_engineering_ai', 'kind': 'native-http', 'configured': self.tc.configured, 'capabilities': ['task-submit', 'task-status', 'events', 'approvals', 'evaluation']},
            {'name': 'full_self_coding', 'kind': 'native-cli', 'configured': self.fsc.configured, 'capabilities': ['repo-analysis', 'parallel-coding', 'testing', 'git-report']},
            {'name': 'openhands', 'kind': 'deployment-aware', 'configured': self.openhands.configured, 'capabilities': ['cloud-app', 'runtime-api', 'workspace-sandbox']},
            self.sweagent.descriptor(),
        ]

    def health(self) -> dict[str, Any]:
        return {
            'tc_engineering_ai': self.tc.health().as_dict(),
            'openhands': self.openhands.health().as_dict(),
            'full_self_coding': {'provider': 'full_self_coding', 'status': 'configured' if self.fsc.configured else 'unconfigured'},
            'swe_agent': {'provider': 'swe_agent', 'status': 'configured' if self.sweagent.configured else 'unconfigured'},
        }
