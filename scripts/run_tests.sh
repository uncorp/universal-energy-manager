#!/usr/bin/env bash
# Run the local Home Assistant-compatible UEM test suite.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$repo_root/.venv-ha/bin/python"

if [[ ! -x "$python_bin" ]]; then
  printf 'Missing local HA test environment: %s\n' "$python_bin" >&2
  printf 'Create it with: python3.11 -m venv .venv-ha && .venv-ha/bin/python -m pip install -r requirements_test.txt\n' >&2
  exit 1
fi

cd "$repo_root"
"$python_bin" -m pytest "$@"
"$python_bin" -m ruff check .
