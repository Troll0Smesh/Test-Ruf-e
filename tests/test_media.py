import asyncio
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis_pc.media import _change


class AsyncValue:
    def __init__(self, value):
        self.value = value

    def __await__(self):
        async def finish():
            return self.value
        return finish().__await__()


class MediaTests(unittest.TestCase):
    def run_command(self, kind, status, *, accepted=True):
        session = Mock()
        session.get_playback_info.return_value = SimpleNamespace(
            playback_status=status,
            controls=SimpleNamespace(is_pause_enabled=True, is_play_enabled=True),
        )
        session.try_pause_async.return_value = AsyncValue(accepted)
        session.try_play_async.return_value = AsyncValue(accepted)
        manager = Mock()
        manager.get_current_session.return_value = session
        api = SimpleNamespace(
            GlobalSystemMediaTransportControlsSessionManager=SimpleNamespace(request_async=lambda: AsyncValue(manager)),
            GlobalSystemMediaTransportControlsSessionPlaybackStatus=SimpleNamespace(PLAYING=4, PAUSED=5, STOPPED=3),
        )
        with patch.dict(sys.modules, {"winrt": Mock(), "winrt.windows": Mock(),
                                      "winrt.windows.media": Mock(), "winrt.windows.media.control": api}):
            result = asyncio.run(_change(kind))
        return result, session

    def test_pause_twice_does_not_resume(self):
        message, session = self.run_command("media_pause", 5)
        self.assertIn("уже на паузе", message)
        session.try_pause_async.assert_not_called()
        session.try_play_async.assert_not_called()

    def test_play_when_playing_does_not_pause(self):
        message, session = self.run_command("media_play", 4)
        self.assertIn("уже идёт", message)
        session.try_play_async.assert_not_called()
        session.try_pause_async.assert_not_called()

    def test_explicit_transitions(self):
        _, session = self.run_command("media_pause", 4)
        session.try_pause_async.assert_called_once_with()
        session.try_play_async.assert_not_called()
        _, session = self.run_command("media_play", 5)
        session.try_play_async.assert_called_once_with()
        session.try_pause_async.assert_not_called()


if __name__ == "__main__":
    unittest.main()
