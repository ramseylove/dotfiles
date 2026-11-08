#!/usr/bin/env bash

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BREW_INSTALL='/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'

find_brew() {
    local candidate
    for candidate in "$(command -v brew 2>/dev/null)" /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

print_brew_help() {
    echo
    echo "Install Homebrew yourself, then rerun setup:"
    echo
    echo "  $BREW_INSTALL"
    echo "  $DOTFILES/setup.sh"
    echo
}

# exec keeps this PID for setup.py, so the refresh loop lasts through the whole run.
keep_sudo_alive() {
    local parent="$$"
    while kill -0 "$parent" 2>/dev/null; do
        sudo -n true 2>/dev/null
        sleep 50
    done &
}

ensure_brew() {
    local brew answer
    if brew="$(find_brew)"; then
        eval "$("$brew" shellenv)"
        return 0
    fi

    echo "Homebrew is not installed. Most setup steps need it."
    if ! { exec 3</dev/tty; } 2>/dev/null; then
        print_brew_help
        exit 1
    fi

    read -r -u 3 -p "Install Homebrew now? It will ask for your password. [Y/n] " answer
    case "$answer" in
        ""|[Yy]*)
            echo "Enter your password once. Setup keeps it cached until it finishes, so you can walk away."
            if ! sudo -v <&3; then
                echo "ERROR Could not get admin rights."
                print_brew_help
                exit 1
            fi
            exec 3<&-
            keep_sudo_alive
            NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            if ! brew="$(find_brew)"; then
                echo "ERROR Homebrew install did not finish."
                print_brew_help
                exit 1
            fi
            eval "$("$brew" shellenv)"
            ;;
        *)
            exec 3<&-
            print_brew_help
            exit 0
            ;;
    esac
}

ensure_brew

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
