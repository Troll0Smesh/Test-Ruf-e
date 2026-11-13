"""Small, on-demand catalogue of open windows and Start Menu applications."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import json

from .targets import clean_alias, clean_targets, clean_value


SITES = {
    "ютуб": "https://www.youtube.com/", "ютьюб": "https://www.youtube.com/",
    "youtube": "https://www.youtube.com/", "гугл": "https://www.google.com/",
    "google": "https://www.google.com/", "яндекс": "https://ya.ru/",
    "википедия": "https://ru.wikipedia.org/", "википедию": "https://ru.wikipedia.org/",
    "телеграм": "https://web.telegram.org/", "телеграм веб": "https://web.telegram.org/",
    "вконтакте": "https://vk.com/", "вк": "https://vk.com/",
    "рутуб": "https://rutube.ru/", "твитч": "https://www.twitch.tv/",
    "twitch": "https://www.twitch.tv/", "реддит": "https://www.reddit.com/",
    "reddit": "https://www.reddit.com/", "гитхаб": "https://github.com/",
    "github": "https://github.com/", "стим": "https://store.steampowered.com/",
    "steam": "https://store.steampowered.com/", "нетфликс": "https://www.netflix.com/",
    "кино поиск": "https://www.kinopoisk.ru/", "кинопоиск": "https://www.kinopoisk.ru/",
    "авито": "https://www.avito.ru/", "озон": "https://www.ozon.ru/",
    "вайлдберриз": "https://www.wildberries.ru/", "почта": "https://mail.google.com/",
}

APP_ALIASES = {
    "google chrome": ("хром", "гугл хром"),
    "mozilla firefox": ("файрфокс", "мозилла"),
    "microsoft edge": ("эдж", "майкрософт эдж"),
    "telegram": ("телеграм",),
    "discord": ("дискорд",),
    "spotify": ("спотифай",),
    "steam": ("стим",),
    "visual studio code": ("визуал студио код", "вс код"),
    "notepad": ("блокнот",),
    "калькулятор": ("калькулятор",),
}


def _alias(text: str) -> str | None:
    text = re.sub(r"[^а-яёa-z0-9 -]", " ", text.lower())
    try:
        return clean_alias(text)
    except ValueError:
        return None


def _unique(entries: list[tuple[str, str]]) -> dict[str, str]:
    found: dict[str, str] = {}
    ambiguous: set[str] = set()
    for alias, value in entries:
        if alias in found and found[alias] != value:
            ambiguous.add(alias)
        else:
            found[alias] = value
    return {alias: value for alias, value in found.items() if alias not in ambiguous}


def discover_windows() -> dict[str, str]:
    if sys.platform != "win32":
        return {}
    from .actions import visible_windows

    entries = []
    for _, title in visible_windows()[:80]:
        if title == "Джарвис":
            continue
        candidates = {title, title.rsplit(" - ", 1)[-1]}
        for candidate in candidates:
            alias = _alias(candidate)
            if alias:
                entries.append((alias, title))
            for key, variants in APP_ALIASES.items():
                if key in candidate.lower():
                    entries.extend((variant, title) for variant in variants)
    return _unique(entries)


def discover_apps() -> dict[str, str]:
    if sys.platform != "win32":
        return {}
    entries = []
    roots = [Path(value) / "Microsoft/Windows/Start Menu/Programs"
             for key in ("APPDATA", "PROGRAMDATA") if (value := os.environ.get(key))]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            shortcuts = sorted(root.rglob("*.lnk"))[:300]
        except OSError:
            continue
        for path in shortcuts:
            name = path.stem
            if re.search(r"uninstall|remove|удалить|деинстал", name, re.IGNORECASE):
                continue
            alias = _alias(name)
            if alias:
                entries.append((alias, str(path)))
            for key, variants in APP_ALIASES.items():
                if key in name.lower():
                    entries.extend((variant, str(path)) for variant in variants)
    found = _unique(entries)
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    for alias, path in (
        ("блокнот", windir / "System32/notepad.exe"),
        ("калькулятор", windir / "System32/calc.exe"),
        ("проводник", windir / "explorer.exe"),
        ("пейнт", windir / "System32/mspaint.exe"),
    ):
        if path.is_file():
            found.setdefault(alias, str(path))
    # App Paths covers programs that register an executable but have no Start
    # Menu shortcut. It is read once per catalogue refresh, with no process
    # scanning or additional resident service.
    try:
        import winreg
    except ImportError:
        return found
    key_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as parent:
                count = min(winreg.QueryInfoKey(parent)[0], 500)
                for index in range(count):
                    try:
                        name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, name) as item:
                            path = winreg.QueryValueEx(item, "")[0]
                        if not isinstance(path, str) or not Path(path).is_file():
                            continue
                        aliases = [_alias(Path(name).stem)]
                        for key, variants in APP_ALIASES.items():
                            if key in name.lower():
                                aliases.extend(variants)
                        for alias in aliases:
                            if alias:
                                found.setdefault(alias, path)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def discover_browser_bookmarks() -> dict[str, str]:
    """Read local Chromium bookmarks, with a strict bound on file and list size."""
    local = os.environ.get("LOCALAPPDATA")
    if sys.platform != "win32" or not local:
        return {}
    roots = (
        Path(local) / "Google/Chrome/User Data",
        Path(local) / "Microsoft/Edge/User Data",
        Path(local) / "BraveSoftware/Brave-Browser/User Data",
    )
    entries = []
    for root in roots:
        if not root.is_dir():
            continue
        for profile in list(root.glob("*/Bookmarks"))[:10]:
            try:
                if profile.stat().st_size > 5_000_000:
                    continue
                data = json.loads(profile.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            stack = list(data.get("roots", {}).values()) if isinstance(data, dict) else []
            seen = 0
            while stack and seen < 500:
                item = stack.pop()
                if not isinstance(item, dict):
                    continue
                seen += 1
                if isinstance(item.get("children"), list):
                    stack.extend(item["children"][:500])
                name, url = item.get("name"), item.get("url")
                if isinstance(name, str) and isinstance(url, str):
                    alias = _alias(name)
                    if alias:
                        try:
                            entries.append((alias, clean_value("sites", url)))
                        except ValueError:
                            continue
    return _unique(entries)


def available_targets(saved: dict | None = None) -> dict[str, dict[str, str]]:
    targets = {"windows": discover_windows(), "apps": discover_apps(),
               "sites": {**discover_browser_bookmarks(), **SITES}}
    for kind, entries in clean_targets(saved).items():
        targets[kind].update(entries)  # Explicit user choices take precedence.
    return targets
