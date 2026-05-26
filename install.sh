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

# SSH
link "ssh/config" "$HOME/.ssh/config"
chmod 600 "$HOME/.dotfiles/ssh/config"

# Zsh
link "zsh/.zshrc"    "$HOME/.zshrc"
link "zsh/.zprofile" "$HOME/.zprofile"

# Git
link "git/.gitconfig" "$HOME/.gitconfig"

# Homebrew
if command -v brew &>/dev/null; then
    link "Brewfile" "$HOME/.Brewfile"
    brew bundle install --global --no-lock
else
    echo "ACTION Homebrew not installed: https://brew.sh"
fi

# Ghostty
link "ghostty/config" "$HOME/.config/ghostty/config"

# VSCode
link "vscode/settings.json" "$HOME/Library/Application Support/Code/User/settings.json"

# Claude
link "CLAUDE.md"               "$HOME/CLAUDE.md"
link "claude/settings.json"    "$HOME/.claude/settings.json"
link "claude/keybindings.json" "$HOME/.claude/keybindings.json"

# Raycast
if [[ -f "$DOTFILES/raycast/settings.rayconfig" ]]; then
    cp "$DOTFILES/raycast/settings.rayconfig" "$HOME/Desktop/raycast-settings.rayconfig"
    echo "ACTION Raycast: import ~/Desktop/raycast-settings.rayconfig"
    echo "       Raycast → ⌘, → Advanced → Import Settings & Data"
fi
