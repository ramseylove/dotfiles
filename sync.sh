#!/usr/bin/env bash

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Pulling latest dotfiles..."
git -C "$DOTFILES" pull --ff-only || {
    echo "ERROR Pull failed (uncommitted local changes?)"
    echo "      Run: git -C ~/.dotfiles status"
    exit 1
}

echo "Re-linking..."
"$DOTFILES/install.sh"

echo "Done."
