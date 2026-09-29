# Catalyst Deployment Checklist

## Preflight
1. Python 3.11+
2. Install Catalyst with `python -m pip install -e .`
3. Configure a real model provider/API key outside the repository.
4. Run `pytest -q` and `python -m compileall -q catalyst`.
5. If browser control is enabled: install Playwright Chromium.
6. Configure policy, approvals, domain allowlists, and authentication before exposing the API.

## Start
`python -m catalyst.api.server`

## Native device control
Catalyst's API does not magically control a personal device from Codespaces. A native device agent must run on the target desktop/Android environment and communicate through the governed device protocol.

## Production secrets
Keep API keys, OAuth secrets, admin credentials, device tokens, browser cookies, and runtime databases outside Git.

## Release validation
- Unit/integration tests pass.
- Python compilation passes.
- API import/runtime smoke test passes.
- Archive contains source and documentation but excludes runtime state.
- Confirm rollback snapshot exists before any production self-improvement.
