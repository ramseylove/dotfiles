#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
HOME = Path.home()
LogSink = Callable[[str], None]
LOG_SINK: LogSink | None = None


class SetupError(Exception):
    pass


@dataclass
class SetupItem:
    key: str
    label: str
    description: str
    action: Callable[[], None]
    selected: bool = True


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

    process = subprocess.Popen(
        command,
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


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def backup_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    if not candidate.exists():
        return candidate

    stamp = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak.{stamp}")


def link(src_rel: str, dst: Path) -> None:
    src = ROOT / src_rel

    if not src.exists():
        emit(f"SKIP  {src_rel} (not found in dotfiles)")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.is_symlink() and Path(os.readlink(dst)) == src:
        emit(f"OK    {dst}")
        return

    if dst.exists() or dst.is_symlink():
        if not dst.is_symlink():
            backup = backup_path(dst)
            emit(f"BACKUP {dst} -> {backup}")
            dst.rename(backup)
        else:
            dst.unlink()

    dst.symlink_to(src)
    emit(f"LINK  {dst} -> {src}")


def link_dotfiles() -> None:
    section("Dotfiles")

    link("ssh/config", HOME / ".ssh/config")
    ssh_config = ROOT / "ssh/config"
    if ssh_config.exists():
        ssh_config.chmod(0o600)

    link("zsh/.zshrc", HOME / ".zshrc")
    link("zsh/.zprofile", HOME / ".zprofile")
    link("git/.gitconfig", HOME / ".gitconfig")
    link("ghostty/config", HOME / ".config/ghostty/config")
    link("vscode/settings.json", HOME / "Library/Application Support/Code/User/settings.json")
    link("CLAUDE.md", HOME / "CLAUDE.md")
    link("claude/settings.json", HOME / ".claude/settings.json")
    link("claude/keybindings.json", HOME / ".claude/keybindings.json")


def install_homebrew_packages() -> None:
    section("Homebrew")

    if not command_exists("brew"):
        emit("ACTION Install Homebrew first: https://brew.sh")
        emit("       Then rerun: ~/.dotfiles/setup.sh")
        return

    link("Brewfile", HOME / ".Brewfile")
    run(["brew", "bundle", "install", "--global", "--no-lock"])


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
        ("brew", command_exists("brew")),
        ("gh", command_exists("gh")),
        ("~/.zshrc", (HOME / ".zshrc").is_symlink()),
        ("~/.gitconfig", (HOME / ".gitconfig").is_symlink()),
        ("ghostty config", (HOME / ".config/ghostty/config").is_symlink()),
        ("Raycast import file", (HOME / "Desktop/raycast-settings.rayconfig").exists()),
    ]

    for label, ok in checks:
        emit(f"{'OK' if ok else 'MISS'}   {label}")


def setup_items() -> list[SetupItem]:
    return [
        SetupItem(
            key="dotfiles",
            label="Link dotfiles",
            description="Symlink shell, git, SSH, Claude, VSCode, and Ghostty config.",
            action=link_dotfiles,
        ),
        SetupItem(
            key="brew",
            label="Install Homebrew packages",
            description="Run brew bundle from the repo Brewfile.",
            action=install_homebrew_packages,
        ),
        SetupItem(
            key="macos",
            label="Apply saved macOS settings",
            description="Apply the curated settings in macos/settings.yaml.",
            action=apply_macos_settings,
        ),
        SetupItem(
            key="raycast",
            label="Prepare Raycast import",
            description="Copy the Raycast export to Desktop for manual import.",
            action=prepare_raycast_import,
        ),
        SetupItem(
            key="manual",
            label="Show manual steps",
            description="Print sign-in and app import tasks that cannot be fully automated.",
            action=show_manual_steps,
        ),
        SetupItem(
            key="verify",
            label="Verify setup",
            description="Check tools, symlinks, and import files.",
            action=verify_setup,
        ),
    ]


def run_items(items: list[SetupItem]) -> None:
    selected = [item for item in items if item.selected]

    if not selected:
        emit("No setup steps are selected.")
        return

    for item in selected:
        try:
            item.action()
        except subprocess.CalledProcessError as exc:
            raise SetupError(f"{item.label} failed with exit code {exc.returncode}") from exc


def run_all() -> None:
    run_items(setup_items())


def run_one(key: str) -> None:
    items = {item.key: item for item in setup_items()}
    if key not in items:
        raise SetupError(f"Unknown setup step: {key}")
    items[key].action()


def launch_tui() -> None:
    try:
        from textual import on, work
        from textual.app import App, ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.widgets import Button, Checkbox, Footer, Header, RichLog, Static
    except ModuleNotFoundError as exc:
        raise SetupError("Textual is not installed. Run ./setup.sh so dependencies bootstrap first.") from exc

    class SetupApp(App[None]):
        TITLE = "Dotfiles Setup"

        CSS = """
        Screen {
            background: #111318;
            color: #e8e2d3;
        }

        Header {
            background: #293241;
            color: #f6f0dd;
        }

        #intro {
            height: 5;
            padding: 1 2;
            background: #1b202b;
            border-bottom: solid #3d5a80;
        }

        #title {
            text-style: bold;
            color: #ffd166;
        }

        #layout {
            height: 1fr;
        }

        #tasks {
            width: 42%;
            min-width: 38;
            padding: 1 2;
            background: #171b24;
            border-right: solid #3d5a80;
        }

        #details {
            padding: 1 2;
            height: 7;
            background: #202634;
            border-bottom: solid #3d5a80;
        }

        #log {
            height: 1fr;
            padding: 1;
            background: #0f1218;
        }

        #buttons {
            height: 5;
            padding: 1 2;
            background: #171b24;
            border-top: solid #3d5a80;
        }

        Checkbox {
            margin-bottom: 1;
        }

        Button {
            margin-right: 1;
            min-width: 7;
        }

        .hint {
            color: #98c1d9;
        }
        """

        BINDINGS = [
            ("r", "run_selected", "Run selected"),
            ("d", "dry_run", "Dry run"),
            ("v", "verify", "Verify"),
            ("a", "select_all", "Select all"),
            ("n", "select_none", "Select none"),
            ("q", "quit", "Quit"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.items = setup_items()
            self.selected = {item.key: item.selected for item in self.items}
            self.running = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Container(
                Static(
                    "[b]New Mac Setup[/b]\n"
                    "Choose exactly what this machine should receive, then run the selected steps.",
                    id="intro",
                ),
                Horizontal(
                    Vertical(
                        Static("Setup checklist", id="title"),
                        *[
                            Checkbox(item.label, value=item.selected, id=f"step-{item.key}")
                            for item in self.items
                        ],
                        Static("Shortcuts: r run, d preview, v verify, q quit", classes="hint"),
                        id="tasks",
                    ),
                    Vertical(
                        Static("", id="details"),
                        RichLog(id="log", highlight=True, markup=True, wrap=True),
                    ),
                    id="layout",
                ),
                Horizontal(
                    Button("Run", id="run", variant="success"),
                    Button("Preview", id="dry-run"),
                    Button("Verify", id="verify", variant="primary"),
                    Button("All", id="select-all"),
                    Button("None", id="select-none"),
                    Button("Quit", id="quit", variant="error"),
                    id="buttons",
                ),
            )
            yield Footer()

        def on_mount(self) -> None:
            self.refresh_details()
            self.log_line("[b]Ready.[/b] Toggle steps on the left, then run selected.")

        def selected_items(self) -> list[SetupItem]:
            items = []
            for item in self.items:
                item.selected = self.selected[item.key]
                if item.selected:
                    items.append(item)
            return items

        def log_line(self, message: str) -> None:
            self.query_one("#log", RichLog).write(message)

        def refresh_details(self) -> None:
            selected_count = len([value for value in self.selected.values() if value])
            selected_labels = ", ".join(item.label for item in self.items if self.selected[item.key])
            if not selected_labels:
                selected_labels = "Nothing selected yet."
            self.query_one("#details", Static).update(
                f"[b]{selected_count} of {len(self.items)} steps selected[/b]\n"
                f"{selected_labels}\n"
                "Use Space/Enter on checkboxes, or the buttons below."
            )

        def set_running(self, running: bool) -> None:
            self.running = running
            for button in self.query(Button):
                button.disabled = running

        @on(Checkbox.Changed)
        def checkbox_changed(self, event: Checkbox.Changed) -> None:
            checkbox_id = event.checkbox.id or ""
            if checkbox_id.startswith("step-"):
                self.selected[checkbox_id.removeprefix("step-")] = event.value
                self.refresh_details()

        @on(Button.Pressed)
        def button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id
            if button_id == "run":
                self.action_run_selected()
            elif button_id == "dry-run":
                self.action_dry_run()
            elif button_id == "verify":
                self.action_verify()
            elif button_id == "select-all":
                self.action_select_all()
            elif button_id == "select-none":
                self.action_select_none()
            elif button_id == "quit":
                self.exit()

        def action_select_all(self) -> None:
            for item in self.items:
                self.selected[item.key] = True
                self.query_one(f"#step-{item.key}", Checkbox).value = True
            self.refresh_details()

        def action_select_none(self) -> None:
            for item in self.items:
                self.selected[item.key] = False
                self.query_one(f"#step-{item.key}", Checkbox).value = False
            self.refresh_details()

        def action_dry_run(self) -> None:
            self.log_line("")
            self.log_line("[b]Dry run[/b]")
            for item in self.selected_items():
                self.log_line(f"- {item.label}: {item.description}")
            if not self.selected_items():
                self.log_line("No setup steps selected.")

        def action_verify(self) -> None:
            if self.running:
                return
            self.run_verify_worker()

        def action_run_selected(self) -> None:
            if self.running:
                return
            self.run_selected_worker()

        @work(thread=True, exclusive=True)
        def run_verify_worker(self) -> None:
            self.call_from_thread(self.set_running, True)
            self.call_from_thread(self.log_line, "\n[b]Running verification[/b]")
            self.run_with_log([item for item in setup_items() if item.key == "verify"])
            self.call_from_thread(self.set_running, False)

        @work(thread=True, exclusive=True)
        def run_selected_worker(self) -> None:
            selected = self.selected_items()
            self.call_from_thread(self.set_running, True)
            self.call_from_thread(self.log_line, "\n[b]Running selected setup steps[/b]")
            self.run_with_log(selected)
            self.call_from_thread(self.set_running, False)

        def run_with_log(self, items: list[SetupItem]) -> None:
            global LOG_SINK
            previous_sink = LOG_SINK
            LOG_SINK = lambda message: self.call_from_thread(self.log_line, message)

            try:
                run_items(items)
                self.call_from_thread(self.log_line, "\n[b green]Finished.[/b green]")
            except SetupError as exc:
                self.call_from_thread(self.log_line, f"\n[b red]ERROR[/b red] {exc}")
            finally:
                LOG_SINK = previous_sink

    SetupApp().run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive new Mac setup app.")
    parser.add_argument("--all", action="store_true", help="Run all setup steps without opening the TUI.")
    parser.add_argument("--link", action="store_true", help="Link dotfiles only.")
    parser.add_argument("--brew", action="store_true", help="Install Homebrew packages only.")
    parser.add_argument("--macos", action="store_true", help="Apply saved macOS settings only.")
    parser.add_argument("--raycast", action="store_true", help="Prepare Raycast import only.")
    parser.add_argument("--manual", action="store_true", help="Show manual steps only.")
    parser.add_argument("--verify", action="store_true", help="Verify setup only.")
    parser.add_argument("--menu", action="store_true", help="Open the interactive TUI.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.all:
            run_all()
        elif args.link:
            run_one("dotfiles")
        elif args.brew:
            run_one("brew")
        elif args.macos:
            run_one("macos")
        elif args.raycast:
            run_one("raycast")
        elif args.manual:
            run_one("manual")
        elif args.verify:
            run_one("verify")
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
