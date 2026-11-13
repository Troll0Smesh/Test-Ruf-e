"""Small, lazy Windows action backend; importing it has no desktop side effects."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import webbrowser
from typing import TYPE_CHECKING

from .targets import clean_targets, clean_value
from .discovery import SITES

if TYPE_CHECKING:
    from .intents import Action


_KINDS = frozenset({
    "volume_set", "volume_change", "mute", "unmute", "minimize_window",
    "minimize_all", "minimize_named", "restore_named", "open_app", "open_site", "open_url",
    "lock", "media_pause", "media_play",
})


class ActionError(RuntimeError):
    """A supported desktop operation could not be completed."""


def _validate(action: Action) -> None:
    if action.kind not in _KINDS:
        raise ValueError(f"Неизвестное действие: {action.kind}")
    if action.kind in {"volume_set", "volume_change"}:
        if type(action.value) is not int:
            raise ValueError("Для громкости требуется целое число процентов")
        if action.kind == "volume_set" and not 0 <= action.value <= 100:
            raise ValueError("Громкость должна быть от 0 до 100 процентов")
    if action.kind in {"minimize_named", "restore_named", "open_app", "open_site"}:
        if not isinstance(action.value, str) or not action.value:
            raise ValueError("Укажите имя окна, приложения или сайта")
    if action.kind == "open_url":
        if not isinstance(action.value, str):
            raise ValueError("Укажите адрес сайта")
        clean_value("sites", action.value)


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.LockWorkStation.argtypes = []
    user32.LockWorkStation.restype = wintypes.BOOL
    user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
    user32.keybd_event.restype = None
    user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    return user32


def _endpoint():
    # Importing pycaw/comtypes starts COM and loads native libraries. Keep this
    # out of startup, idle listening, dry runs, and non-Windows installations.
    from pycaw.pycaw import AudioUtilities

    device = AudioUtilities.GetSpeakers()
    if device is None:
        raise ActionError("Устройство вывода звука не найдено")
    return device.EndpointVolume


def visible_windows() -> list[tuple[int, str]]:
    """Return titled, visible top-level windows for the settings selector."""
    if sys.platform != "win32":
        return []
    user32 = _user32()
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(handle, _):
        if user32.IsWindowVisible(handle):
            length = user32.GetWindowTextLengthW(handle)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(handle, buffer, length + 1)
                title = buffer.value.strip()
                if title:
                    windows.append((handle, title))
        return True

    user32.EnumWindows(visit, 0)
    return windows


def _find_window(title: str) -> int:
    windows = visible_windows()
    exact = [handle for handle, name in windows if name.casefold() == title.casefold()]
    matches = exact or [handle for handle, name in windows if title.casefold() in name.casefold()]
    if not matches and " - " in title:
        # Browser tab titles change. Match its stable application suffix only
        # when exactly one top-level window still has that suffix.
        suffix = title.rsplit(" - ", 1)[-1].casefold()
        matches = [handle for handle, name in windows if name.casefold().endswith(" - " + suffix)]
    if not matches:
        raise ActionError(f"Окно «{title}» не найдено. Обновите его заголовок в настройках.")
    if len(matches) > 1:
        raise ActionError(f"Найдено несколько окон «{title}». Укажите более точный заголовок.")
    return matches[0]


class Actions:
    """Execute only the explicit allowlist of local Windows operations."""

    def __init__(self, targets: dict | None = None) -> None:
        self.targets = clean_targets(targets)
        self.targets["sites"] = {**SITES, **self.targets["sites"]}

    def execute(self, action: Action) -> str:
        _validate(action)
        if sys.platform != "win32":
            raise ActionError("Управление компьютером поддерживается в Windows 10/11")
        try:
            return self._execute(action)
        except ActionError:
            raise
        except Exception as exc:
            raise ActionError(f"Не удалось выполнить {action.kind}: {exc}") from exc

    def _execute(self, action: Action) -> str:
        if action.kind in {"media_pause", "media_play"}:
            from .media import change_media

            return change_media(action.kind)
        if action.kind == "open_url":
            if not webbrowser.open(action.value):
                raise ActionError("Браузер не открыл сайт")
            return f"Сайт {action.value} открыт"
        if action.kind in {"minimize_named", "restore_named", "open_app", "open_site"}:
            kind = {"minimize_named": "windows", "restore_named": "windows", "open_app": "apps", "open_site": "sites"}[action.kind]
            value = self.targets[kind].get(action.value)
            if value is None:
                raise ActionError(f"Имя «{action.value}» не настроено")
            if action.kind == "open_app":
                if not Path(value).is_file():
                    raise ActionError(f"Файл приложения не найден: {value}")
                os.startfile(value)
                return f"Приложение «{action.value}» открыто"
            if action.kind == "open_site":
                if not webbrowser.open(value):
                    raise ActionError("Браузер не открыл сайт")
                return f"Сайт «{action.value}» открыт"
            user32 = _user32()
            handle = _find_window(value)
            if action.kind == "minimize_named":
                user32.ShowWindow(handle, 6)
                return f"Окно «{action.value}» свёрнуто"
            user32.ShowWindow(handle, 3)  # SW_MAXIMIZE, including minimized windows
            user32.SetForegroundWindow(handle)
            return f"Окно «{action.value}» развёрнуто"
        if action.kind in {"volume_set", "volume_change", "mute", "unmute"}:
            volume = _endpoint()  # Resolve again if the default speaker changed.
            if action.kind in {"mute", "unmute"}:
                muted = action.kind == "mute"
                volume.SetMute(int(muted), None)
                return "Звук выключен" if muted else "Звук включён"
            if action.kind == "volume_change":
                percent = round(volume.GetMasterVolumeLevelScalar() * 100) + action.value
            else:
                percent = action.value
            percent = max(0, min(100, percent))
            volume.SetMasterVolumeLevelScalar(percent / 100, None)
            return f"Громкость: {percent}%"

        user32 = _user32()
        if action.kind == "lock":
            if not user32.LockWorkStation():
                raise ActionError("Windows отклонила блокировку компьютера")
            return "Компьютер заблокирован"
        if action.kind == "minimize_window":
            window = user32.GetForegroundWindow()
            if not window:
                raise ActionError("Активное окно не найдено")
            # ShowWindow's return value is previous visibility, not success.
            user32.ShowWindow(window, 6)  # SW_MINIMIZE
            return "Активное окно свёрнуто"
        # Win+M always minimizes; Win+D would restore windows on a second call.
        try:
            user32.keybd_event(0x5B, 0, 0, 0)  # VK_LWIN
            user32.keybd_event(0x4D, 0, 0, 0)  # M
        finally:
            try:
                user32.keybd_event(0x4D, 0, 2, 0)  # KEYEVENTF_KEYUP
            finally:
                user32.keybd_event(0x5B, 0, 2, 0)
        return "Все окна свёрнуты"


class DryRunActions:
    """Report intended operations without importing or calling native APIs."""

    def execute(self, action: Action) -> str:
        _validate(action)
        value = "" if action.value is None else f" {action.value}"
        return f"[dry-run] {action.kind}{value}"
