#!/bin/sh
set -eu

cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python scripts/bootstrap.py "$@"
elif command -v python3.12 >/dev/null 2>&1; then
    exec python3.12 scripts/bootstrap.py "$@"
fi
exec python3 scripts/bootstrap.py "$@"
