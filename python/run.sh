#!/usr/bin/env bash
set -e
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" main.py "$@"
else
    exec python3 main.py "$@"
fi
