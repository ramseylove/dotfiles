#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    print("ERROR PyYAML is not installed.", file=sys.stderr)
    print("      Run: ./macos/bootstrap.sh", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "settings.yaml"
SNAPSHOT_DIR = ROOT / "snapshots"


class SettingsError(Exception):
    pass


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def load_settings() -> dict[str, dict[str, Any]]:
    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise SettingsError("settings.yaml must contain a top-level 'settings' map.")

    for setting_id, setting in settings.items():
        for field in ("label", "domain", "key", "type", "value"):
            if field not in setting:
                raise SettingsError(f"{setting_id} is missing required field: {field}")

    return settings


def coerce(value: str, setting_type: str) -> Any:
    value = value.strip()
    if setting_type == "bool":
        return value.lower() in {"1", "true", "yes"}
    if setting_type == "int":
        return int(value)
    if setting_type == "float":
        return float(value)
    return value


def current_value(setting: dict[str, Any]) -> Any:
    result = run(
        ["defaults", "read", setting["domain"], str(setting["key"])],
        check=False,
    )
    if result.returncode != 0:
        return None
    return coerce(result.stdout, setting["type"])


def defaults_write_args(setting: dict[str, Any]) -> list[str]:
    value = setting["value"]
    setting_type = setting["type"]
    args = ["defaults", "write", setting["domain"], str(setting["key"])]

    if setting_type == "bool":
        return args + ["-bool", "true" if bool(value) else "false"]
    if setting_type == "int":
        return args + ["-int", str(int(value))]
    if setting_type == "float":
        return args + ["-float", str(float(value))]
    if setting_type == "string":
        return args + ["-string", str(value)]

    raise SettingsError(f"Unsupported setting type: {setting_type}")


def matching_settings(
    settings: dict[str, dict[str, Any]],
    ids: list[str] | None = None,
    tag: str | None = None,
) -> dict[str, dict[str, Any]]:
    if ids:
        missing = [setting_id for setting_id in ids if setting_id not in settings]
        if missing:
            raise SettingsError(f"Unknown setting id(s): {', '.join(missing)}")
        return {setting_id: settings[setting_id] for setting_id in ids}

    if tag:
        return {
            setting_id: setting
            for setting_id, setting in settings.items()
            if tag in setting.get("tags", [])
        }

    return settings


def restart_apps(settings: dict[str, dict[str, Any]]) -> None:
    apps = sorted({app for setting in settings.values() for app in setting.get("restart", [])})
    for app in apps:
        run(["killall", app], check=False)


def cmd_list(args: argparse.Namespace) -> None:
    settings = load_settings()
    for setting_id, setting in settings.items():
        tags = ", ".join(setting.get("tags", []))
        print(f"{setting_id}")
        print(f"  {setting['label']}")
        print(f"  domain: {setting['domain']}  key: {setting['key']}")
        print(f"  type: {setting['type']}  saved: {setting['value']}  tags: {tags}")


def cmd_diff(args: argparse.Namespace) -> None:
    settings = matching_settings(load_settings(), tag=args.tag)
    changed = False

    for setting_id, setting in settings.items():
        current = current_value(setting)
        saved = setting["value"]
        if current != saved:
            changed = True
            print(f"{setting_id}: current={current!r} saved={saved!r}")

    if not changed:
        print("All checked macOS settings match settings.yaml.")


def cmd_apply(args: argparse.Namespace) -> None:
    settings = matching_settings(load_settings(), ids=args.ids, tag=args.tag)

    if not settings:
        print("No matching settings.")
        return

    for setting_id, setting in settings.items():
        run(defaults_write_args(setting))
        print(f"APPLY {setting_id}: {setting['value']!r}")

    restart_apps(settings)


def domain_plist(domain: str) -> Path:
    if domain == "NSGlobalDomain":
        return Path.home() / "Library/Preferences/.GlobalPreferences.plist"
    return Path.home() / "Library/Preferences" / f"{domain}.plist"


def snapshot_data() -> dict[str, dict[str, Any]]:
    settings = load_settings()
    domains = sorted(
        {setting["domain"] for setting in settings.values()}
        | {plist.stem for plist in (ROOT / "defaults").glob("*.plist")}
    )
    snapshot: dict[str, dict[str, Any]] = {}

    for domain in domains:
        plist = domain_plist(domain)
        if not plist.exists():
            continue
        with plist.open("rb") as f:
            snapshot[domain] = plistlib.load(f)

    return snapshot


def cmd_snapshot(args: argparse.Namespace) -> None:
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    name = args.name or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SNAPSHOT_DIR / f"{name}.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(snapshot_data(), f, indent=2, sort_keys=True, default=str)
        f.write("\n")

    print(f"SAVE {path.relative_to(ROOT.parent)}")


def load_snapshot(name: str) -> dict[str, Any]:
    path = SNAPSHOT_DIR / f"{name}.json"
    if not path.exists():
        raise SettingsError(f"Snapshot not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def cmd_discover(args: argparse.Namespace) -> None:
    before = load_snapshot(args.before)
    after = load_snapshot(args.after)

    found = False
    for domain in sorted(set(before) | set(after)):
        keys = sorted(set(before.get(domain, {})) | set(after.get(domain, {})))
        changes = [
            (key, before.get(domain, {}).get(key), after.get(domain, {}).get(key))
            for key in keys
            if before.get(domain, {}).get(key) != after.get(domain, {}).get(key)
        ]

        if not changes:
            continue

        found = True
        print(domain)
        for key, old, new in changes:
            print(f"  {key}: {old!r} -> {new!r}")

    if not found:
        print("No preference changes detected in tracked domains.")


def prompt_choice(prompt: str, choices: set[str]) -> str:
    while True:
        choice = input(prompt).strip().lower()
        if choice in choices:
            return choice
        print(f"Choose one of: {', '.join(sorted(choices))}")


def cmd_menu(args: argparse.Namespace) -> None:
    while True:
        print()
        print("macOS Settings")
        print("1. Show saved settings")
        print("2. Show current differences")
        print("3. Apply all saved settings")
        print("4. Apply a tag")
        print("5. Save snapshot")
        print("6. Discover changes between snapshots")
        print("q. Quit")

        choice = prompt_choice("> ", {"1", "2", "3", "4", "5", "6", "q"})
        if choice == "q":
            return
        if choice == "1":
            cmd_list(args)
        elif choice == "2":
            args.tag = None
            cmd_diff(args)
        elif choice == "3":
            args.ids = []
            args.tag = None
            cmd_apply(args)
        elif choice == "4":
            args.ids = []
            args.tag = input("Tag, for example dock or finder: ").strip()
            cmd_apply(args)
        elif choice == "5":
            args.name = input("Snapshot name: ").strip() or None
            cmd_snapshot(args)
        elif choice == "6":
            args.before = input("Before snapshot name: ").strip()
            args.after = input("After snapshot name: ").strip()
            cmd_discover(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage curated macOS settings.")
    subparsers = parser.add_subparsers(required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=cmd_list)

    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("--tag")
    diff_parser.set_defaults(func=cmd_diff)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("ids", nargs="*")
    apply_parser.add_argument("--tag")
    apply_parser.set_defaults(func=cmd_apply)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("name", nargs="?")
    snapshot_parser.set_defaults(func=cmd_snapshot)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("before")
    discover_parser.add_argument("after")
    discover_parser.set_defaults(func=cmd_discover)

    menu_parser = subparsers.add_parser("menu")
    menu_parser.set_defaults(func=cmd_menu)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except SettingsError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
