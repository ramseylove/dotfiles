#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR python3 is required for the setup app."
    echo "      Install Xcode Command Line Tools or Homebrew Python, then rerun setup."
    exit 1
fi

VENV="$DOTFILES/.setup-venv"

if [[ ! -x "$VENV/bin/python" ]]; then
    python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import textual" >/dev/null 2>&1; then
    "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV/bin/python" -m pip install -r "$DOTFILES/requirements.txt"
fi

exec "$VENV/bin/python" "$DOTFILES/setup.py" "$@"
