#!/usr/bin/env bash

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="https://github.com/ramseylove/dotfiles.git"

# Clone the repo if this script is run directly (not from within the repo)
if [[ ! -d "$HOME/.dotfiles/.git" ]]; then
    echo "Cloning dotfiles..."
    git clone "$REPO" "$HOME/.dotfiles"
    DOTFILES="$HOME/.dotfiles"
fi

"$DOTFILES/setup.sh" --all
