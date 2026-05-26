# dotfiles

Personal machine setup for macOS. Covers shell, git, Claude Code, Homebrew, and Raycast.

## Install

On a fresh machine:

```bash
curl -fsSL https://raw.githubusercontent.com/ramseylove/dotfiles/main/install.sh | bash
```

Or clone first if you want to inspect:

```bash
git clone https://github.com/ramseylove/dotfiles.git ~/.dotfiles
~/.dotfiles/install.sh
```

## What's included

| File | Symlinked to | Notes |
|---|---|---|
| `zsh/.zshrc` | `~/.zshrc` | Shell config. Source `~/.zshrc.local` for machine-specific overrides |
| `zsh/.zprofile` | `~/.zprofile` | Homebrew shell env |
| `git/.gitconfig` | `~/.gitconfig` | Global git config. Add `~/.gitconfig.local` for per-machine overrides (e.g. work email) |
| `Brewfile` | `~/.Brewfile` | Homebrew packages and casks |
| `CLAUDE.md` | `~/CLAUDE.md` | Global Claude Code instructions |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code permissions and settings |
| `raycast/settings.rayconfig` | Desktop (copied) | Must be imported manually in Raycast |
| `vscode/settings.json` | `~/Library/Application Support/Code/User/settings.json` | VSCode user settings |
| `ssh/config` | `~/.ssh/config` | SSH host config. Private keys are never committed |

## Machine-specific overrides

Some config should differ per machine. These files are never committed:

**`~/.zshrc.local`** — extra env vars, aliases, or PATH entries specific to one machine.

**`~/.gitconfig.local`** — git overrides, e.g. a work email or signing key:
```ini
[user]
    email = ryan@company.com
```

## After installing

Manual steps the script can't automate:

1. **Raycast** — import `~/Desktop/raycast-settings.rayconfig` via Raycast → ⌘, → Advanced → Import Settings & Data
2. **1Password** — sign in to re-link the CLI
3. **gh** — run `gh auth login`

## Syncing to an existing machine

Pull the latest and re-link in one command:

```bash
dotfiles-sync
# or directly: ~/.dotfiles/sync.sh
```

Fails safely with `--ff-only` — if you have uncommitted local changes it will stop rather than overwrite them.

## Keeping it up to date

```bash
# Sync new brew installs into the Brewfile
brew bundle dump --global --force

# Re-export Raycast settings after config changes
# Raycast → ⌘, → Advanced → Export Settings & Data → ~/.dotfiles/raycast/settings.rayconfig

# Push changes
git -C ~/.dotfiles add -A && git -C ~/.dotfiles commit -m "..." && git -C ~/.dotfiles push
```
