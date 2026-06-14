#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$DOTFILES/macos/defaults"

# Common domains worth preserving across a fresh reinstall.
DOMAINS=(
    NSGlobalDomain
    com.apple.dock
    com.apple.finder
    com.apple.screencapture
    com.apple.symbolichotkeys
    com.apple.desktopservices
    com.apple.HIToolbox
    com.apple.universalaccess
    com.apple.AppleMultitouchTrackpad
    com.apple.driver.AppleBluetoothMultitouch.trackpad
)

mkdir -p "$OUT_DIR"

for domain in "${DOMAINS[@]}"; do
    out="$OUT_DIR/$domain.plist"

    if ! defaults read "$domain" >/dev/null 2>&1; then
        echo "SKIP  $domain (not found)"
        continue
    fi

    defaults export "$domain" "$out"
    echo "SAVE  $domain -> ${out#$DOTFILES/}"
done
