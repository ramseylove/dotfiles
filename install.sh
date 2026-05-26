#!/usr/bin/env bash

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="https://github.com/ramseylove/dotfiles.git"

# Clone the repo if this script is run directly (not from within the repo)
if [[ ! -d "$HOME/.dotfiles/.git" ]]; then
    echo "Cloning dotfiles..."
    git clone "$REPO" "$HOME/.dotfiles"
    DOTFILES="$HOME/.dotfiles"
fi

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
