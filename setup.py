#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
HOME = Path.home()
LogSink = Callable[[str], None]
LOG_SINK: LogSink | None = None


class SetupError(Exception):
    pass


@dataclass
class MenuItem:
    key: str
    label: str
    description: str
    action: Callable[[], None] | None = None
    check: Callable[[], bool] | None = None
    children: list[MenuItem] = field(default_factory=list)
    selected: bool = True
    checked: bool | None = None  # None=pending, True=already done, False=needs action
    touched: bool = False  # user changed selection; checks must not override it

    @property
    def is_branch(self) -> bool:
        return bool(self.children)


def iter_leaves(item: MenuItem):
    if item.is_branch:
        for child in item.children:
            yield from iter_leaves(child)
    else:
        yield item


def collect_selected(items: list[MenuItem]) -> list[MenuItem]:
    result = []
    for item in items:
        if item.is_branch:
            result.extend(collect_selected(item.children))
        elif item.selected and item.action:
            result.append(item)
    return result


def collect_checkable(items: list[MenuItem]) -> list[MenuItem]:
    result = []
    for item in items:
        if item.is_branch:
            result.extend(collect_checkable(item.children))
        elif item.check:
            result.append(item)
    return result


def item_badge(item: MenuItem) -> str:
    if item.is_branch:
        leaves = list(iter_leaves(item))
        if any(l.checked is None and l.check is not None for l in leaves):
            return " ? "
        on = sum(1 for l in leaves if l.selected)
        total = len(leaves)
        return f"{on}/{total}"
    if item.check is not None and item.checked is None:
        return " ? "
    if item.checked and not item.selected:
        return "OK "
    if item.selected:
        return "ON "
    return "-- "


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(message: str = "") -> None:
    if LOG_SINK:
        LOG_SINK(message)
    else:
        print(message)


def section(title: str) -> None:
    emit("")
    emit(f"== {title} ==")


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    emit(f"$ {' '.join(command)}")

    if not LOG_SINK:
        return subprocess.run(command, check=check)

    # The TUI owns the terminal, so a child that prompts would hang; give it no stdin.
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None

    for line in process.stdout:
        emit(line.rstrip())

    return_code = process.wait()
    if check and return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)

    return subprocess.CompletedProcess(command, return_code)


def _brew_path() -> str | None:
    """Return path to brew, checking known locations if not on PATH."""
    found = shutil.which("brew")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(candidate).exists():
            return candidate
    return None


def command_exists(name: str) -> bool:
    if name == "brew":
        return _brew_path() is not None
    return shutil.which(name) is not None


def backup_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    if not candidate.exists():
        return candidate
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak.{stamp}")


def can_adopt(dst: Path, adopt: Path) -> bool:
    if adopt.exists() or adopt.is_symlink() or not dst.exists():
        return False
    # An existing file that already sources the adopt target would source itself.
    try:
        return adopt.name not in dst.read_text(errors="ignore")
    except OSError:
        return False


def link(src_rel: str, dst: Path, adopt: Path | None = None) -> None:
    src = ROOT / src_rel

    if not src.exists():
        emit(f"SKIP  {src_rel} (not found in dotfiles)")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.is_symlink() and Path(os.readlink(dst)) == src:
        emit(f"OK    {dst}")
        return

    if adopt is not None and can_adopt(dst, adopt):
        emit(f"MOVE  {dst} -> {adopt} (still loaded)")
        dst.rename(adopt)
    elif dst.exists() or dst.is_symlink():
        if adopt is not None:
            emit(f"ACTION Merge anything you still need from the backup into {adopt}")
        if not dst.is_symlink():
            backup = backup_path(dst)
            emit(f"BACKUP {dst} -> {backup}")
            dst.rename(backup)
        else:
            dst.unlink()

    dst.symlink_to(src)
    emit(f"LINK  {dst} -> {src}")


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_brew() -> bool:
    return command_exists("brew")


def check_formula(name: str) -> Callable[[], bool]:
    def _check() -> bool:
        brew = _brew_path()
        if not brew:
            return False
        result = subprocess.run(
            [brew, "list", "--formula", name],
            capture_output=True,
        )
        return result.returncode == 0
    return _check


def check_cask(name: str) -> Callable[[], bool]:
    def _check() -> bool:
        brew = _brew_path()
        if not brew:
            return False
        result = subprocess.run(
            [brew, "list", "--cask", name],
            capture_output=True,
        )
        return result.returncode == 0
    return _check


def check_vscode_ext(name: str) -> Callable[[], bool]:
    def _check() -> bool:
        if not command_exists("code"):
            return False
        result = subprocess.run(
            ["code", "--list-extensions"],
            capture_output=True,
            text=True,
        )
        installed = {line.strip().lower() for line in result.stdout.splitlines()}
        return name.lower() in installed
    return _check


def check_npm_pkg(name: str) -> Callable[[], bool]:
    def _check() -> bool:
        if not command_exists("npm"):
            return False
        result = subprocess.run(
            ["npm", "list", "-g", "--depth=0", name],
            capture_output=True,
        )
        return result.returncode == 0
    return _check


def check_mas(app_id: str) -> Callable[[], bool]:
    def _check() -> bool:
        if not command_exists("mas"):
            return False
        result = subprocess.run(["mas", "list"], capture_output=True, text=True)
        return any(line.split()[:1] == [app_id] for line in result.stdout.splitlines())
    return _check


def check_symlink(src_rel: str, dst: Path) -> Callable[[], bool]:
    def _check() -> bool:
        src = ROOT / src_rel
        return dst.is_symlink() and Path(os.readlink(dst)) == src
    return _check


# ---------------------------------------------------------------------------
# Action functions
# ---------------------------------------------------------------------------

def install_homebrew() -> None:
    section("Install Homebrew")
    if command_exists("brew"):
        emit("OK    Homebrew is already installed")
        return
    if LOG_SINK:
        raise SetupError(
            "the Homebrew installer asks for your password, which can't be typed in the TUI. "
            "Quit (q) and run ./setup.sh --brew, then reopen ./setup.sh"
        )
    run([
        "/bin/bash", "-c",
        "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
    ])


def install_formula(name: str) -> Callable[[], None]:
    def _action() -> None:
        section(f"brew install {name}")
        brew = _brew_path()
        if not brew:
            raise SetupError("Homebrew is not installed — run Install Homebrew first")
        run([brew, "install", name])
    return _action


def install_cask(name: str) -> Callable[[], None]:
    def _action() -> None:
        section(f"brew install --cask {name}")
        brew = _brew_path()
        if not brew:
            raise SetupError("Homebrew is not installed — run Install Homebrew first")
        run([brew, "install", "--cask", name])
    return _action


def install_vscode_ext(name: str) -> Callable[[], None]:
    def _action() -> None:
        section(f"code --install-extension {name}")
        if not command_exists("code"):
            raise SetupError("VSCode CLI not found — ensure 'code' is in PATH")
        run(["code", "--install-extension", name])
    return _action


def install_npm_pkg(name: str) -> Callable[[], None]:
    def _action() -> None:
        section(f"npm install -g {name}")
        if not command_exists("npm"):
            raise SetupError("npm is not installed")
        run(["npm", "install", "-g", name])
    return _action


def install_mas(app_id: str) -> Callable[[], None]:
    def _action() -> None:
        section(f"mas install {app_id}")
        if not command_exists("mas"):
            raise SetupError("mas is not installed — add brew \"mas\" to the Brewfile")
        run(["mas", "install", app_id])
    return _action


def link_file(
    src_rel: str,
    dst: Path,
    chmod: int | None = None,
    adopt: Path | None = None,
    parent_mode: int | None = None,
) -> Callable[[], None]:
    def _action() -> None:
        if parent_mode is not None:
            dst.parent.mkdir(mode=parent_mode, parents=True, exist_ok=True)
            dst.parent.chmod(parent_mode)
        link(src_rel, dst, adopt=adopt)
        if chmod is not None:
            src = ROOT / src_rel
            if src.exists():
                src.chmod(chmod)
    return _action


def apply_macos_settings() -> None:
    section("macOS Settings")
    apply_script = ROOT / "macos/apply.sh"
    settings = ROOT / "macos/settings.yaml"
    if not apply_script.exists() or not settings.exists():
        emit("SKIP  macOS settings manager is not available")
        return
    run([str(apply_script)])


def prepare_raycast_import() -> None:
    section("Raycast")
    src = ROOT / "raycast/settings.rayconfig"
    if not src.exists():
        emit("SKIP  raycast/settings.rayconfig not found")
        return
    dst = HOME / "Desktop/raycast-settings.rayconfig"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    emit("ACTION Import ~/Desktop/raycast-settings.rayconfig")
    emit("       Raycast -> Command-, -> Advanced -> Import Settings & Data")


def show_manual_steps() -> None:
    section("Manual Steps")
    emit("1. Raycast: import ~/Desktop/raycast-settings.rayconfig")
    emit("2. 1Password: sign in to re-link the CLI")
    emit("3. GitHub CLI: run gh auth login")
    emit("4. Restart apps or log out if a macOS setting does not appear immediately")


def verify_setup() -> None:
    section("Verify")
    checks = [
        ("brew", _brew_path() is not None),
        ("gh", command_exists("gh")),
        ("~/.zshrc", (HOME / ".zshrc").is_symlink()),
        ("~/.gitconfig", (HOME / ".gitconfig").is_symlink()),
        ("ghostty config", (HOME / ".config/ghostty/config").is_symlink()),
        ("Raycast import file", (HOME / "Desktop/raycast-settings.rayconfig").exists()),
    ]
    for label, ok in checks:
        emit(f"{'OK' if ok else 'MISS'}   {label}")


# ---------------------------------------------------------------------------
# Brewfile parser
# ---------------------------------------------------------------------------

def parse_brewfile() -> dict[str, list[tuple[str, str]]]:
    """Map entry type to (label, install argument) pairs."""
    brewfile = ROOT / "Brewfile"
    grouped: dict[str, list[tuple[str, str]]] = {
        "brew": [], "cask": [], "vscode": [], "npm": [], "mas": [],
    }
    if not brewfile.exists():
        return grouped
    for raw in brewfile.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for prefix in grouped:
            if line.startswith(f'{prefix} "'):
                name = line.split('"')[1]
                arg = name
                if prefix == "mas":
                    match = re.search(r"id:\s*(\d+)", line)
                    if not match:
                        break
                    arg = match.group(1)
                grouped[prefix].append((name, arg))
                break
    return grouped


# ---------------------------------------------------------------------------
# Menu tree
# ---------------------------------------------------------------------------

def build_menu() -> list[MenuItem]:
    grouped = parse_brewfile()

    type_meta = [
        ("brew",   "Formulae",          check_formula,   install_formula),
        ("cask",   "Casks",             check_cask,      install_cask),
        ("vscode", "VSCode Extensions", check_vscode_ext, install_vscode_ext),
        ("npm",    "npm packages",      check_npm_pkg,   install_npm_pkg),
        ("mas",    "App Store apps",    check_mas,       install_mas),
    ]

    brew_groups: list[MenuItem] = [
        MenuItem(
            key="brew_install_homebrew",
            label="Install Homebrew",
            description="Install the Homebrew package manager (prerequisite for all brew items).",
            action=install_homebrew,
            check=check_brew,
        )
    ]

    for type_key, type_label, check_fn, action_fn in type_meta:
        entries = grouped.get(type_key, [])
        if not entries:
            continue
        packages = [
            MenuItem(
                key=f"{type_key}_{arg}",
                label=name,
                description=f"Install {name}",
                action=action_fn(arg),
                check=check_fn(arg),
            )
            for name, arg in entries
        ]
        brew_groups.append(MenuItem(
            key=f"brew_group_{type_key}",
            label=type_label,
            description=f"Select individual {type_label.lower()} to install.",
            children=packages,
        ))

    dotfile_items = [
        MenuItem(
            key="link_ssh",
            label="ssh/config",
            description="~/.ssh/config",
            action=link_file("ssh/config", HOME / ".ssh/config", chmod=0o600, parent_mode=0o700),
            check=check_symlink("ssh/config", HOME / ".ssh/config"),
        ),
        MenuItem(
            key="link_zshrc",
            label=".zshrc",
            description="~/.zshrc",
            action=link_file("zsh/.zshrc", HOME / ".zshrc", adopt=HOME / ".zshrc.local"),
            check=check_symlink("zsh/.zshrc", HOME / ".zshrc"),
        ),
        MenuItem(
            key="link_aliases",
            label=".aliases",
            description="~/.aliases",
            action=link_file("zsh/.aliases", HOME / ".aliases"),
            check=check_symlink("zsh/.aliases", HOME / ".aliases"),
        ),
        MenuItem(
            key="link_zprofile",
            label=".zprofile",
            description="~/.zprofile",
            action=link_file("zsh/.zprofile", HOME / ".zprofile"),
            check=check_symlink("zsh/.zprofile", HOME / ".zprofile"),
        ),
        MenuItem(
            key="link_gitconfig",
            label=".gitconfig",
            description="~/.gitconfig",
            action=link_file("git/.gitconfig", HOME / ".gitconfig"),
            check=check_symlink("git/.gitconfig", HOME / ".gitconfig"),
        ),
        MenuItem(
            key="link_ghostty",
            label="ghostty/config",
            description="~/.config/ghostty/config",
            action=link_file("ghostty/config", HOME / ".config/ghostty/config"),
            check=check_symlink("ghostty/config", HOME / ".config/ghostty/config"),
        ),
        MenuItem(
            key="link_vscode",
            label="vscode/settings.json",
            description="~/Library/Application Support/Code/User/settings.json",
            action=link_file(
                "vscode/settings.json",
                HOME / "Library/Application Support/Code/User/settings.json",
            ),
            check=check_symlink(
                "vscode/settings.json",
                HOME / "Library/Application Support/Code/User/settings.json",
            ),
        ),
        MenuItem(
            key="link_claude_md",
            label="CLAUDE.md",
            description="~/CLAUDE.md",
            action=link_file("CLAUDE.md", HOME / "CLAUDE.md"),
            check=check_symlink("CLAUDE.md", HOME / "CLAUDE.md"),
        ),
        MenuItem(
            key="link_claude_settings",
            label="claude/settings.json",
            description="~/.claude/settings.json",
            action=link_file("claude/settings.json", HOME / ".claude/settings.json"),
            check=check_symlink("claude/settings.json", HOME / ".claude/settings.json"),
        ),
        MenuItem(
            key="link_claude_keys",
            label="claude/keybindings.json",
            description="~/.claude/keybindings.json",
            action=link_file("claude/keybindings.json", HOME / ".claude/keybindings.json"),
            check=check_symlink("claude/keybindings.json", HOME / ".claude/keybindings.json"),
        ),
    ]

    return [
        MenuItem(
            key="homebrew",
            label="Homebrew",
            description="Install Homebrew and select packages to install.",
            children=brew_groups,
        ),
        MenuItem(
            key="dotfiles",
            label="Link dotfiles",
            description="Select individual dotfiles to symlink into your home directory.",
            children=dotfile_items,
        ),
        MenuItem(
            key="macos",
            label="macOS settings",
            description="Apply the curated settings in macos/settings.yaml.",
            action=apply_macos_settings,
        ),
        MenuItem(
            key="raycast",
            label="Raycast import",
            description="Copy the Raycast export to Desktop for manual import.",
            action=prepare_raycast_import,
            selected=False,
        ),
        MenuItem(
            key="manual",
            label="Manual steps",
            description="Print sign-in and app import tasks that cannot be fully automated.",
            action=show_manual_steps,
            selected=False,
        ),
        MenuItem(
            key="verify",
            label="Verify setup",
            description="Check tools, symlinks, and import files.",
            action=verify_setup,
            selected=False,
        ),
    ]


# ---------------------------------------------------------------------------
# CLI helpers (non-TUI)
# ---------------------------------------------------------------------------

def run_action(item: MenuItem) -> str | None:
    """Run one item; return an error message instead of raising."""
    assert item.action is not None
    try:
        item.action()
    except subprocess.CalledProcessError as exc:
        return f"exit {exc.returncode}"
    except (SetupError, OSError) as exc:
        return str(exc)
    return None


def run_all_actions(items: list[MenuItem]) -> list[tuple[str, str]]:
    failures = []
    for item in items:
        error = run_action(item)
        if error is not None:
            emit(f"ERROR {item.label}: {error}")
            failures.append((item.label, error))
    if failures:
        section(f"{len(failures)} step(s) failed")
        for label, error in failures:
            emit(f"FAIL  {label}: {error}")
    return failures


def run_items(items: list[MenuItem]) -> None:
    selected = collect_selected(items)
    if not selected:
        emit("No setup steps selected.")
        return
    if run_all_actions(selected):
        raise SetupError("some setup steps failed (see above)")


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

def launch_tui() -> None:
    try:
        from textual import events, work
        from textual.app import App, ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.widgets import RichLog, Static

    except ModuleNotFoundError as exc:
        raise SetupError(
            "Textual is not installed. Run ./setup.sh so dependencies bootstrap first."
        ) from exc

    class SetupApp(App[None]):
        TITLE = "Dotfiles Setup"

        CSS = """
        Screen {
            background: #0d1117;
            color: #e6edf3;
        }
        #app {
            height: 100%;
            padding: 1;
            background: #0d1117;
        }
        #topbar {
            height: 1;
            background: #161b22;
            color: #e6edf3;
            padding: 0 1;
        }
        #layout {
            height: 1fr;
            margin-top: 1;
            margin-bottom: 1;
        }
        #sidebar {
            width: 40;
            padding: 1;
            background: #161b22;
            border: solid #30363d;
        }
        #breadcrumb {
            color: #8b949e;
            margin-bottom: 1;
            height: 1;
        }
        #menu-list {
            height: 1fr;
            padding: 0 1;
            color: #e6edf3;
        }
        #details {
            padding: 1;
            height: 5;
            background: #161b22;
            border: solid #30363d;
        }
        #log {
            height: 1fr;
            margin-top: 1;
            padding: 1;
            background: #010409;
            border: solid #30363d;
        }
        #commandbar {
            height: 1;
            padding: 0 1;
            background: #161b22;
            color: #8b949e;
        }
        .hint { color: #8b949e; }
        .accent { color: #ffa657; }
        """

        BINDINGS = [
            ("r", "run_selected", "Run selected"),
            ("x", "run_cursor", "Run item"),
            ("c", "recheck", "Recheck"),
            ("a", "select_all", "All"),
            ("n", "select_none", "None"),
            ("q", "quit", "Quit"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.menu_root = build_menu()
            # stack of (items, cursor_index)
            self.nav_stack: list[tuple[list[MenuItem], int]] = [(self.menu_root, 0)]
            self.running = False
            self.check_lock = threading.Lock()

        # ------------------------------------------------------------------
        # Navigation helpers
        # ------------------------------------------------------------------

        def current_items(self) -> list[MenuItem]:
            return self.nav_stack[-1][0]

        def cursor_index(self) -> int:
            return self.nav_stack[-1][1]

        def cursor_item(self) -> MenuItem:
            return self.current_items()[self.cursor_index()]

        def set_cursor(self, pos: int) -> None:
            items = self.current_items()
            clamped = max(0, min(len(items) - 1, pos))
            self.nav_stack[-1] = (items, clamped)

        def breadcrumb(self) -> str:
            return " › ".join(self._crumb_labels)

        # ------------------------------------------------------------------
        # Compose
        # ------------------------------------------------------------------

        def compose(self) -> ComposeResult:
            self._crumb_labels: list[str] = ["Setup"]
            yield Container(
                Static(
                    "[b]dotfiles setup[/b]  [dim]prepare a new Mac from this repo[/dim]",
                    id="topbar",
                ),
                Horizontal(
                    Vertical(
                        Static("Setup", id="breadcrumb"),
                        Static("", id="menu-list"),
                        id="sidebar",
                    ),
                    Vertical(
                        Static("", id="details"),
                        RichLog(id="log", highlight=True, markup=True, wrap=True),
                    ),
                    id="layout",
                ),
                Static(
                    "[b]↑↓/jk[/b] nav   [b]space/enter[/b] select   [b]b/esc[/b] back   "
                    "[b]r[/b] run all   [b]x[/b] run item   [b]c[/b] recheck   "
                    "[b]a[/b] all   [b]n[/b] none   [b]q[/b] quit",
                    id="commandbar",
                ),
                id="app",
            )

        def on_mount(self) -> None:
            self.refresh_display()
            self.log_line(
                "[b green]Ready.[/b green] "
                "Checks running in background — [b]?[/b] means pending."
            )
            self.run_checks_worker(collect_checkable(self.menu_root))

        # ------------------------------------------------------------------
        # Display
        # ------------------------------------------------------------------

        def log_line(self, message: str) -> None:
            self.query_one("#log", RichLog).write(message)

        def refresh_display(self) -> None:
            items = self.current_items()
            cursor = self.cursor_index()
            rows = []
            for i, item in enumerate(items):
                is_cursor = i == cursor
                badge = item_badge(item)

                # Badge color
                if " ? " in badge or badge == " ? ":
                    badge_style = "dim"
                elif "OK" in badge:
                    badge_style = "green"
                elif "ON" in badge or ("/" in badge and badge.split("/")[0].strip() != "0"):
                    badge_style = "b yellow"
                else:
                    badge_style = "dim"

                cursor_mark = "[b cyan]›[/b cyan]" if is_cursor else " "
                branch_mark = "  [dim]›[/dim]" if item.is_branch else ""

                if is_cursor:
                    label_str = f"[b]{item.label}[/b]"
                elif badge.strip() == "--":
                    label_str = f"[dim]{item.label}[/dim]"
                else:
                    label_str = item.label

                # Textual 8's Content parser treats [WORD] as a markup tag.
                # \[ escapes the bracket so it renders as a literal [.
                badge_display = f"\\[{badge.strip()}]"
                rows.append(
                    f"{cursor_mark} [{badge_style}]{badge_display}[/]  {label_str}{branch_mark}"
                )

            self.query_one("#menu-list", Static).update("\n".join(rows))

            # Breadcrumb
            self.query_one("#breadcrumb", Static).update(
                f"[dim]{self.breadcrumb()}[/dim]"
            )

            # Details
            item = items[cursor] if items else None
            if item:
                badge = item_badge(item)
                if item.is_branch:
                    leaves = list(iter_leaves(item))
                    on = sum(1 for l in leaves if l.selected)
                    desc_extra = f"  [dim]{on}/{len(leaves)} selected[/dim]"
                else:
                    desc_extra = ""
                self.query_one("#details", Static).update(
                    f"[b]{item.label}[/b]{desc_extra}\n"
                    f"[dim]{item.description}[/dim]\n\n"
                    "[dim]space/enter[/dim] = enter/toggle   "
                    "[dim]x[/dim] = run this item   "
                    "[dim]b/esc[/dim] = back"
                )

        # ------------------------------------------------------------------
        # Key handling
        # ------------------------------------------------------------------

        def on_key(self, event: events.Key) -> None:
            key = event.key

            if key in ("j", "down"):
                self.set_cursor(self.cursor_index() + 1)
                self.refresh_display()
                event.stop()
            elif key in ("k", "up"):
                self.set_cursor(self.cursor_index() - 1)
                self.refresh_display()
                event.stop()
            elif key in ("space", "enter", "l", "right"):
                if not self.running:
                    self._activate_cursor()
                event.stop()
            elif key in ("b", "escape", "h", "left"):
                self._go_back()
                event.stop()
            elif key.isdigit() and not self.running:
                idx = int(key) - 1
                items = self.current_items()
                if 0 <= idx < len(items):
                    self.set_cursor(idx)
                    self.refresh_display()
                    self._activate_cursor()
                event.stop()

        def _activate_cursor(self) -> None:
            item = self.cursor_item()
            if item.is_branch:
                self._crumb_labels.append(item.label)
                self.nav_stack.append((item.children, 0))
                self.refresh_display()
            else:
                item.selected = not item.selected
                item.touched = True
                self.refresh_display()

        def _go_back(self) -> None:
            if len(self.nav_stack) > 1:
                self.nav_stack.pop()
                if len(self._crumb_labels) > 1:
                    self._crumb_labels.pop()
                self.refresh_display()

        # ------------------------------------------------------------------
        # Select all / none
        # ------------------------------------------------------------------

        def action_select_all(self) -> None:
            for leaf in iter_leaves_list(self.current_items()):
                leaf.selected = True
                leaf.touched = True
            self.refresh_display()

        def action_select_none(self) -> None:
            for leaf in iter_leaves_list(self.current_items()):
                leaf.selected = False
                leaf.touched = True
            self.refresh_display()

        # ------------------------------------------------------------------
        # Run
        # ------------------------------------------------------------------

        def action_run_selected(self) -> None:
            if self.running:
                return
            selected = collect_selected(self.menu_root)
            if not selected:
                self.log_line("[yellow]Nothing selected.[/yellow]")
                return
            self._run_worker(selected)

        def action_run_cursor(self) -> None:
            if self.running:
                return
            item = self.cursor_item()
            to_run = collect_selected(item.children) if item.is_branch else (
                [item] if item.action else []
            )
            if not to_run:
                self.log_line("[yellow]Nothing to run for this item.[/yellow]")
                return
            self._run_worker(to_run)

        @work(thread=True, exclusive=True)
        def _run_worker(self, items: list[MenuItem]) -> None:
            self.call_from_thread(self._set_running, True)
            labels = ", ".join(i.label for i in items)
            self.call_from_thread(self.log_line, f"\n[b]Running:[/b] {labels}")
            self._run_with_log(items)
            self.call_from_thread(self._set_running, False)
            # Recheck items that were just run
            checkable = [i for i in items if i.check]
            for item in checkable:
                item.touched = False
            if checkable:
                self.run_checks_worker(checkable)

        def _run_with_log(self, items: list[MenuItem]) -> None:
            global LOG_SINK
            prev = LOG_SINK
            LOG_SINK = lambda msg: self.call_from_thread(self.log_line, msg)
            try:
                if run_all_actions(items):
                    self.call_from_thread(
                        self.log_line, "\n[b red]Finished with errors.[/b red]"
                    )
                else:
                    self.call_from_thread(self.log_line, "\n[b green]Done.[/b green]")
            finally:
                LOG_SINK = prev

        def _set_running(self, running: bool) -> None:
            self.running = running

        # ------------------------------------------------------------------
        # Background checks
        # ------------------------------------------------------------------

        def action_recheck(self) -> None:
            all_checkable = collect_checkable(self.menu_root)
            for item in all_checkable:
                item.checked = None
            self.refresh_display()
            self.run_checks_worker(all_checkable)

        @work(thread=True)
        def run_checks_worker(self, items: list[MenuItem]) -> None:
            with self.check_lock:
                for item in items:
                    if item.check is None:
                        continue
                    try:
                        result = item.check()
                    except Exception:
                        result = False
                    item.checked = result
                    if result and not item.touched:
                        item.selected = False
                    self.call_from_thread(self.refresh_display)

    SetupApp().run()


# ---------------------------------------------------------------------------
# iter_leaves_list helper (for select all/none on a list)
# ---------------------------------------------------------------------------

def iter_leaves_list(items: list[MenuItem]):
    for item in items:
        yield from iter_leaves(item)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive new Mac setup app.")
    parser.add_argument("--all", action="store_true", help="Run all setup steps without the TUI.")
    parser.add_argument("--link", action="store_true", help="Link all dotfiles.")
    parser.add_argument("--brew", action="store_true", help="Install all Homebrew packages.")
    parser.add_argument("--macos", action="store_true", help="Apply macOS settings.")
    parser.add_argument("--raycast", action="store_true", help="Prepare Raycast import.")
    parser.add_argument("--manual", action="store_true", help="Show manual steps.")
    parser.add_argument("--verify", action="store_true", help="Verify setup.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    menu = build_menu()

    def find_item(key: str) -> MenuItem | None:
        for item in menu:
            if item.key == key:
                return item
        return None

    try:
        if args.all:
            run_items(menu)
        elif args.link:
            item = find_item("dotfiles")
            assert item
            run_items(item.children)
        elif args.brew:
            item = find_item("homebrew")
            assert item
            run_items(item.children)
        elif args.macos:
            item = find_item("macos")
            assert item
            if run_all_actions([item]):
                return 1
        elif args.raycast:
            item = find_item("raycast")
            assert item
            if run_all_actions([item]):
                return 1
        elif args.manual:
            item = find_item("manual")
            assert item
            if run_all_actions([item]):
                return 1
        elif args.verify:
            item = find_item("verify")
            assert item
            if run_all_actions([item]):
                return 1
        else:
            launch_tui()
    except SetupError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
