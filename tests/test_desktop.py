import json
from pathlib import Path
from queue import Empty
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from jarvis_pc.desktop import Listener, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_invalid_settings_fall_back(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "settings.json"
            self.assertEqual(load_settings(p)["silence"], 0.8)
            for data in ["broken", "[]", '{"silence":99,"dry_run":"false","device":2}']:
                p.write_text(data)
                self.assertEqual(load_settings(p), {"device": "", "silence": 0.8, "dry_run": False,
                                                    "targets": {"windows": {}, "apps": {}, "sites": {}}})

    def test_round_trip_unicode(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "nested" / "settings.json"
            settings = {"device": "Микрофон", "silence": 1.2, "dry_run": True,
                        "targets": {"windows": {"браузер": "Firefox"}, "apps": {}, "sites": {}}}
            save_settings(settings, p)
            self.assertEqual(load_settings(p), settings)
            self.assertFalse(p.with_suffix(".tmp").exists())


class ListenerTests(unittest.TestCase):
    def test_stop_and_restart_dont_overlap_workers(self):
        listener = Listener()
        entered = Event()
        def listen(*args):
            entered.set()
            listener.stop_event.wait(2)
        with patch("jarvis_pc.desktop.model_exists", return_value=True), patch.object(listener, "_listen", side_effect=listen):
            listener.start(dry_run=True)
            self.assertTrue(entered.wait(2))
            with self.assertRaises(RuntimeError):
                listener.start(dry_run=True)
            listener.stop()
            listener.thread.join(2)
            self.assertFalse(listener.running)
            entered.clear()
            listener.start(dry_run=True)
            self.assertTrue(entered.wait(2))
            self.assertFalse(listener.stop_event.is_set())
            listener.stop()
            listener.thread.join(2)
            self.assertFalse(listener.running)

    def test_worker_reports_error_and_terminates(self):
        listener = Listener()
        with patch("jarvis_pc.desktop.model_exists", return_value=True), patch.object(listener, "_listen", side_effect=RuntimeError("Нет микрофона")):
            listener.start(dry_run=True)
            listener.thread.join(2)
        events = []
        while not listener.events.empty():
            events.append(listener.events.get_nowait())
        self.assertIn(("error", "Нет микрофона"), events)
        self.assertEqual(events[-1][0], "stopped")

    def test_stop_during_prepare_skips_model_loading(self):
        listener = Listener()
        def downloading(*args):
            listener.stop()
        with patch("jarvis_pc.desktop.model_exists", return_value=False), patch("jarvis_pc.desktop.download_model", side_effect=downloading), patch.object(listener, "_listen") as listen:
            listener.start(dry_run=True)
            listener.thread.join(2)
            listen.assert_not_called()

    def test_event_queue_is_bounded(self):
        listener = Listener()
        for n in range(500):
            listener.emit("level", n)
        self.assertEqual(listener.events.qsize(), 100)

    def test_windows_worker_initializes_matching_com_apartment(self):
        listener = Listener()
        with patch("jarvis_pc.desktop.sys.platform", "win32"), patch("ctypes.OleDLL", create=True) as ole, patch("jarvis_pc.desktop.model_exists", return_value=True), patch.object(listener, "_listen"):
            listener.start(dry_run=True)
            listener.thread.join(2)
            ole.return_value.CoInitializeEx.assert_called_once_with(None, 2)
            ole.return_value.CoUninitialize.assert_called_once()
