#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# 1) Create .env from template if missing
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  else
    echo "Missing .env.example" >&2
    exit 1
  fi
fi

# 2) Bootstrap secrets/profiles from .env
bash tools/bootstrap.sh

python3 -m pip install -e ".[dev]"
echo "Setup complete. Next: ./run.sh"
