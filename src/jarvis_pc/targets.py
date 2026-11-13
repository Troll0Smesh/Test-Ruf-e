"""Validated user names for windows, applications and websites."""

from __future__ import annotations

import re
from urllib.parse import urlparse

KINDS = ("windows", "apps", "sites")
LABELS = {"windows": "Окно", "apps": "Приложение", "sites": "Сайт"}
_ALIAS = re.compile(r"[а-яёa-z0-9][а-яёa-z0-9 -]{0,49}", re.IGNORECASE)


def clean_alias(alias: str) -> str:
    alias = " ".join(alias.lower().replace("ё", "е").split())
    if not _ALIAS.fullmatch(alias):
        raise ValueError("Имя должно содержать от 1 до 50 букв или цифр")
    return alias


def clean_value(kind: str, value: str) -> str:
    value = value.strip()
    if not value or len(value) > 2048:
        raise ValueError("Укажите путь, адрес сайта или заголовок окна")
    if kind == "sites":
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Укажите полный адрес сайта, начиная с https://")
    elif kind == "apps":
        if not value.lower().endswith((".exe", ".lnk")):
            raise ValueError("Выберите файл приложения .exe или ярлык .lnk")
    elif kind != "windows":
        raise ValueError("Неизвестный тип команды")
    return value


def clean_targets(data: object) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {kind: {} for kind in KINDS}
    if not isinstance(data, dict):
        return result
    for kind in KINDS:
        entries = data.get(kind)
        if not isinstance(entries, dict):
            continue
        for alias, value in list(entries.items())[:300]:
            if not isinstance(alias, str) or not isinstance(value, str):
                continue
            try:
                result[kind][clean_alias(alias)] = clean_value(kind, value)
            except ValueError:
                continue
    return result
