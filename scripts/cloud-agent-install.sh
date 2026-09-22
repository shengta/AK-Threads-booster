#!/usr/bin/env bash
# Idempotent bootstrap for the AK-Threads-Booster Cloud Agent environment.
# Creates a project virtualenv and installs the Python dependencies used by the
# scripts in this repo (requests + optional openai/anthropic LLM providers).
set -euo pipefail

cd "$(dirname "$0")/.."

# python3-venv is not part of the base image; install it once (idempotent).
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r scripts/requirements.txt

echo "[cloud-agent-install] done. Activate with: source .venv/bin/activate"
