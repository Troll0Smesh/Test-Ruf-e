"""Explicit play and pause through the Windows global media session."""

from __future__ import annotations

import asyncio


async def _change(kind: str) -> str:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
    )

    manager = await Manager.request_async()
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("Нет активного проигрывателя в медиасессии Windows")
    info = session.get_playback_info()
    status = info.playback_status
    if kind == "media_pause":
        if status in (Status.PAUSED, Status.STOPPED):
            return "Воспроизведение уже на паузе"
        if status != Status.PLAYING:
            raise RuntimeError("Не удалось определить состояние воспроизведения")
        if not info.controls.is_pause_enabled or not await session.try_pause_async():
            raise RuntimeError("Проигрыватель не поддерживает команду паузы")
        return "Воспроизведение приостановлено"
    if status == Status.PLAYING:
        return "Воспроизведение уже идёт"
    if status not in (Status.PAUSED, Status.STOPPED):
        raise RuntimeError("Не удалось определить состояние воспроизведения")
    if not info.controls.is_play_enabled or not await session.try_play_async():
        raise RuntimeError("Проигрыватель не поддерживает продолжение воспроизведения")
    return "Воспроизведение продолжено"


def change_media(kind: str) -> str:
    # Called only from the listener's background thread. No event loop is kept
    # alive while idle, and no media library is loaded before a media command.
    return asyncio.run(_change(kind))
