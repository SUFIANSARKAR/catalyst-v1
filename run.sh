#!/usr/bin/env bash
set -euo pipefail

# Auto-load .env if present (for Codespaces / easy deploy)
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Ensure initial profiles are seeded from env (idempotent).
bash tools/bootstrap.sh >/dev/null 2>&1 || true

python -m pip install -e .
exec uvicorn catalyst.api.server:app --host 0.0.0.0 --port "${PORT:-8000}"
