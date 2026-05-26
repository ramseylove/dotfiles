#!/usr/bin/env bash

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

link() {
    local src="$DOTFILES/$1"
    local dst="$2"

    if [[ ! -e "$src" ]]; then
        echo "SKIP  $1 (not found in dotfiles)"
        return
    fi

    mkdir -p "$(dirname "$dst")"

    if [[ -L "$dst" && "$(readlink "$dst")" == "$src" ]]; then
        echo "OK    $dst"
        return
    fi

    if [[ -e "$dst" && ! -L "$dst" ]]; then
        echo "BACKUP $dst -> $dst.bak"
        mv "$dst" "$dst.bak"
    fi

    ln -sf "$src" "$dst"
    echo "LINK  $dst -> $src"
}

# Claude
link "CLAUDE.md"             "$HOME/CLAUDE.md"
link "claude/settings.json"  "$HOME/.claude/settings.json"
link "claude/keybindings.json" "$HOME/.claude/keybindings.json"
