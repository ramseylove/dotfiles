#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

section() {
    printf "\n== %s ==\n" "$1"
}

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

install_homebrew() {
    section "Homebrew"

    if ! command -v brew >/dev/null 2>&1; then
        echo "ACTION Install Homebrew first: https://brew.sh"
        echo "       Then rerun: ~/.dotfiles/setup.sh"
        return
    fi

    link "Brewfile" "$HOME/.Brewfile"
    brew bundle install --global --no-lock
}

link_dotfiles() {
    section "Dotfiles"

    link "ssh/config" "$HOME/.ssh/config"
    chmod 600 "$DOTFILES/ssh/config"

    link "zsh/.zshrc" "$HOME/.zshrc"
    link "zsh/.zprofile" "$HOME/.zprofile"
    link "git/.gitconfig" "$HOME/.gitconfig"
    link "ghostty/config" "$HOME/.config/ghostty/config"
    link "vscode/settings.json" "$HOME/Library/Application Support/Code/User/settings.json"
    link "CLAUDE.md" "$HOME/CLAUDE.md"
    link "claude/settings.json" "$HOME/.claude/settings.json"
    link "claude/keybindings.json" "$HOME/.claude/keybindings.json"
}

apply_macos_settings() {
    section "macOS Settings"

    if [[ ! -x "$DOTFILES/macos/apply.sh" || ! -f "$DOTFILES/macos/settings.yaml" ]]; then
        echo "SKIP  macOS settings manager is not available"
        return
    fi

    "$DOTFILES/macos/apply.sh"
}

prepare_raycast_import() {
    section "Raycast"

    if [[ ! -f "$DOTFILES/raycast/settings.rayconfig" ]]; then
        echo "SKIP  raycast/settings.rayconfig not found"
        return
    fi

    cp "$DOTFILES/raycast/settings.rayconfig" "$HOME/Desktop/raycast-settings.rayconfig"
    echo "ACTION Import ~/Desktop/raycast-settings.rayconfig"
    echo "       Raycast -> Command-, -> Advanced -> Import Settings & Data"
}

show_manual_steps() {
    section "Manual Steps"
    echo "1. Raycast: import ~/Desktop/raycast-settings.rayconfig"
    echo "2. 1Password: sign in to re-link the CLI"
    echo "3. GitHub CLI: run gh auth login"
    echo "4. Restart apps or log out if a macOS setting does not appear immediately"
}

verify_setup() {
    section "Verify"

    command -v brew >/dev/null 2>&1 && echo "OK    brew" || echo "MISS  brew"
    command -v gh >/dev/null 2>&1 && echo "OK    gh" || echo "MISS  gh"
    [[ -L "$HOME/.zshrc" ]] && echo "OK    ~/.zshrc" || echo "MISS  ~/.zshrc"
    [[ -L "$HOME/.gitconfig" ]] && echo "OK    ~/.gitconfig" || echo "MISS  ~/.gitconfig"
    [[ -L "$HOME/.config/ghostty/config" ]] && echo "OK    ghostty config" || echo "MISS  ghostty config"
    [[ -f "$HOME/Desktop/raycast-settings.rayconfig" ]] && echo "OK    Raycast import file" || echo "MISS  Raycast import file"
}

run_all() {
    link_dotfiles
    install_homebrew
    apply_macos_settings
    prepare_raycast_import
    show_manual_steps
    verify_setup
}

menu() {
    while true; do
        printf "\nNew Mac Setup\n"
        echo "1. Run full setup"
        echo "2. Link dotfiles"
        echo "3. Install Homebrew packages"
        echo "4. Manage macOS settings"
        echo "5. Apply saved macOS settings"
        echo "6. Prepare Raycast import"
        echo "7. Show manual steps"
        echo "8. Verify setup"
        echo "q. Quit"
        printf "> "
        read -r choice

        case "$choice" in
            1) run_all ;;
            2) link_dotfiles ;;
            3) install_homebrew ;;
            4) "$DOTFILES/macos/settings.sh" ;;
            5) apply_macos_settings ;;
            6) prepare_raycast_import ;;
            7) show_manual_steps ;;
            8) verify_setup ;;
            q|Q) return ;;
            *) echo "Choose 1-8 or q." ;;
        esac
    done
}

case "${1:-menu}" in
    --all|all) run_all ;;
    --link|link) link_dotfiles ;;
    --brew|brew) install_homebrew ;;
    --macos|macos) apply_macos_settings ;;
    --raycast|raycast) prepare_raycast_import ;;
    --manual|manual) show_manual_steps ;;
    --verify|verify) verify_setup ;;
    --menu|menu) menu ;;
    *)
        echo "Usage: $0 [--all|--link|--brew|--macos|--raycast|--manual|--verify|--menu]"
        exit 2
        ;;
esac
