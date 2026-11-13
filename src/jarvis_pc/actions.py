"""Small, lazy Windows action backend; importing it has no desktop side effects."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .intents import Action


_KINDS = frozenset({
    "volume_set", "volume_change", "mute", "unmute", "minimize_window",
    "minimize_all", "lock",
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
    return user32


def _endpoint():
    # Importing pycaw/comtypes starts COM and loads native libraries. Keep this
    # out of startup, idle listening, dry runs, and non-Windows installations.
    from pycaw.pycaw import AudioUtilities

    device = AudioUtilities.GetSpeakers()
    if device is None:
        raise ActionError("Устройство вывода звука не найдено")
    return device.EndpointVolume


class Actions:
    """Execute only the explicit allowlist of local Windows operations."""

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
