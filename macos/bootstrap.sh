#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$DOTFILES/macos/.venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR python3 is required for the macOS settings manager."
    echo "      Install it with Homebrew, then rerun: ./macos/bootstrap.sh"
    exit 1
fi

if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install -r "$DOTFILES/macos/requirements.txt"

echo "OK macOS settings Python environment is ready."
