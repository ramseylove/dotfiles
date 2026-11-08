#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$DOTFILES/macos/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    "$DOTFILES/macos/bootstrap.sh"
fi

"$PYTHON" "$DOTFILES/macos/settings.py" apply "$@"
