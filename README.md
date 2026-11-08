# dotfiles

Personal machine setup for macOS. Covers shell, git, Claude Code, Homebrew, Raycast, and curated macOS settings.

## New Mac setup

On a fresh machine:

```bash
curl -fsSL https://raw.githubusercontent.com/ramseylove/dotfiles/main/install.sh | bash
```

Or clone first if you want to inspect:

```bash
git clone https://github.com/ramseylove/dotfiles.git ~/.dotfiles
~/.dotfiles/setup.sh
```

The Textual setup app can run everything or guide you through one section at a time:

```bash
~/.dotfiles/setup.sh          # interactive checklist
~/.dotfiles/setup.sh --brew   # install Homebrew only
~/.dotfiles/setup.sh --all    # blind full setup
~/.dotfiles/setup.sh --verify # check what is installed
```

If Homebrew is missing, `setup.sh` offers to install it first. It asks for your password once, then the rest runs unattended.

The checklist lets you toggle setup sections before running them:

```text
1. [x] Link dotfiles
2. [x] Install Homebrew packages
3. [x] Apply saved macOS settings
4. [x] Prepare Raycast import
5. [x] Show manual steps
6. [x] Verify setup
```

The first run creates `.setup-venv` and installs the terminal UI dependency from `requirements.txt`.

## What's included

| File | Symlinked to | Notes |
|---|---|---|
| `zsh/.zshrc` | `~/.zshrc` | Shell config. Sources `~/.aliases` and `~/.zshrc.local` |
| `zsh/.aliases` | `~/.aliases` | Shell aliases, kept separate from `.zshrc` |
| `zsh/.zprofile` | `~/.zprofile` | Homebrew shell env |
| `git/.gitconfig` | `~/.gitconfig` | Global git config. Add `~/.gitconfig.local` for per-machine overrides (e.g. work email) |
| `Brewfile` | Not linked | Package list the setup app installs from. Your machine's brew state stays separate |
| `CLAUDE.md` | `~/CLAUDE.md` | Global Claude Code instructions |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code permissions and settings |
| `raycast/settings.rayconfig` | Desktop (copied) | Must be imported manually in Raycast |
| `vscode/settings.json` | `~/Library/Application Support/Code/User/settings.json` | VSCode user settings |
| `ssh/config` | `~/.ssh/config` | Generic SSH host config. Per-machine bits live in `~/.ssh/config.local` (see below) |
| `ghostty/config` | `~/.config/ghostty/config` | Ghostty terminal config |
| `macos/settings.yaml` | Applied with `macos/apply.sh` | Human-editable macOS settings catalog |
| `macos/defaults/*.plist` | Backup snapshots | Exported macOS preference domains |

## Machine-specific overrides

Some config should differ per machine. These files live only on the machine
they apply to and are never committed, so the structure is documented here —
recreate them by hand on each new machine.

**`~/.zshrc.local`** — extra env vars or PATH entries specific to one machine. Shared aliases go in the committed `zsh/.aliases` instead. When setup links `.zshrc`, an existing `~/.zshrc` is moved here so it keeps loading (unless `~/.zshrc.local` already exists, in which case it's backed up to `~/.zshrc.bak` for you to merge).

**`~/.gitconfig.local`** — git overrides, e.g. a work email or signing key:
```ini
[user]
    email = ryan@company.com
```

**`~/.ssh/config.local`** — per-machine SSH options, most commonly the `IdentityFile` for that machine's key. The committed `ssh/config` holds the generic `Host`/`HostName`/`User`, and includes this file from the top so its values win (ssh uses the first value it sees for each option). Copy the committed template `ssh/config.local.example` as a starting point:

```bash
cp ssh/config.local.example ~/.ssh/config.local
chmod 600 ~/.ssh/config.local
```

Match the `Host` to a block in `ssh/config` and add only the per-machine bits — the shared settings are inherited:

```sshconfig
Host github.com
    IdentityFile ~/.ssh/your_key_here
```

Verify the merged result with `ssh -G github.com`.

## After installing

Manual steps the script can't automate:

1. **Raycast** — import `~/Desktop/raycast-settings.rayconfig` via Raycast → ⌘, → Advanced → Import Settings & Data
2. **1Password** — sign in to re-link the CLI
3. **gh** — run `gh auth login`
4. **Finder** — Settings → Sidebar → check your home folder

If `macos/settings.yaml` exists, `install.sh` applies those saved macOS settings automatically during setup.

You can rerun the setup app any time:

```bash
~/.dotfiles/setup.sh
```

## Saving macOS settings before a wipe

Run this before you reformat the Mac:

```bash
./macos/export.sh
git add macos/defaults
git commit -m "Save macOS defaults"
git push
```

That captures the common preferences this repo manages, including Finder, Dock, screenshots, keyboard shortcuts, and global UI defaults. Some things still cannot be fully restored by `defaults`, like Apple ID sign-in, Touch ID, Wi-Fi passwords, and permissions prompts.

## Managing macOS settings

macOS settings are one section in the larger setup app. You can open them from `./setup.sh`, or call the macOS tools directly:

```bash
# Browse and apply settings from an interactive menu
./macos/settings.sh

# Apply all saved settings
./macos/apply.sh

# Apply one setting or one group
./macos/apply.sh dock.autohide
./macos/apply.sh --tag finder

# See what differs between this Mac and settings.yaml
./macos/diff.sh
```

The first run creates `macos/.venv` and installs `PyYAML` from `macos/requirements.txt`.

## Adding more macOS settings later

Most macOS preferences live in a `defaults` domain. To add one manually:

1. Change the setting in System Settings or the app.
2. Find the domain, usually from the plist name in `~/Library/Preferences`, for example `com.apple.dock`.
3. Add a friendly entry to `macos/settings.yaml`.
4. Run `./macos/diff.sh` and `./macos/apply.sh <setting-id>` to verify it.

For discovery, take a before/after snapshot around a System Settings change:

```bash
./macos/snapshot.sh before
# Change the setting in System Settings
./macos/snapshot.sh after
./macos/discover.sh before after
```

When you find the changed domain and key, add it to `macos/settings.yaml`. If it belongs in raw backup snapshots too, add that domain to `DOMAINS` in `macos/export.sh`.

The exporter converts plist files to XML so they are readable in editors and easy to diff.

## Syncing to an existing machine

Pull the latest and re-link in one command:

```bash
dotfiles-sync
# or directly: ~/.dotfiles/sync.sh
```

Fails safely with `--ff-only` — if you have uncommitted local changes it will stop rather than overwrite them.

## Keeping it up to date

```bash
# Overwrite the repo Brewfile with what's installed on this machine
brewfile-sync
# or directly: brew bundle dump --file ~/.dotfiles/Brewfile --force

# Re-export Raycast settings after config changes
# Raycast → ⌘, → Advanced → Export Settings & Data → ~/.dotfiles/raycast/settings.rayconfig

# Re-export macOS defaults after changing system preferences
./macos/export.sh

# Update curated macOS settings
./macos/settings.sh

# Push changes
git -C ~/.dotfiles add -A && git -C ~/.dotfiles commit -m "..." && git -C ~/.dotfiles push
```
