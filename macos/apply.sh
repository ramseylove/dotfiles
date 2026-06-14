#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$DOTFILES/macos/defaults"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "No exported macOS defaults found at ${SRC_DIR#$DOTFILES/}"
    exit 0
fi

shopt -s nullglob

for plist in "$SRC_DIR"/*.plist; do
    domain="$(basename "$plist" .plist)"
    defaults import "$domain" "$plist"
    echo "APPLY $domain"
done

# Refresh the most common UI surfaces so changes show up without logging out.
killall Dock Finder SystemUIServer >/dev/null 2>&1 || true
