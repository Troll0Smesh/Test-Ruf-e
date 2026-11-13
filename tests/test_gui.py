"""Run under an X display (e.g. xvfb-run) or on Windows with Tk installed."""
from queue import Queue
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from jarvis_pc.gui import JarvisWindow


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.listener = Mock(events=Queue(), running=False)
        self.settings = patch("jarvis_pc.gui.save_settings")
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.app = JarvisWindow(self.root, listener=self.listener,
                                enumerate_devices=lambda: [("Микрофон", 3)])

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_start_stop_and_controls(self):
        self.app.device_var.set("Микрофон")
        self.app.silence_var.set("1,2")
        self.app.toggle_listening()
        self.listener.start.assert_called_once_with(device=3, silence=1.2, dry_run=self.app.dry_run.get(),
                                                     targets=self.app.settings["targets"])
        self.assertEqual(str(self.app.device_box["state"]), "disabled")
        self.app.toggle_listening()
        self.listener.stop.assert_called_once()
        self.app.poll()
        self.assertFalse(self.app.busy)
        self.assertEqual(str(self.app.device_box["state"]), "readonly")

    def test_failure_is_visible_and_allows_retry(self):
        self.app.toggle_listening()
        self.listener.events.put(("error", "Микрофон отключён"))
        self.app.poll()
        self.assertEqual(self.app.status["text"], "Не удалось запустить")
        self.assertIn("Микрофон отключён", self.app.journal.get("1.0", "end"))
        self.assertEqual(str(self.app.toggle["state"]), "normal")

    def test_invalid_pause_does_not_start(self):
        self.app.silence_var.set("nan")
        self.app.toggle_listening()
        self.listener.start.assert_not_called()

    def test_history_stays_bounded(self):
        for n in range(300):
            self.app.log(str(n))
        self.assertLessEqual(int(self.app.journal.index("end-1c").split(".")[0]), 100)

    def test_close_requests_worker_stop(self):
        self.listener.running = True
        self.app.close()
        self.listener.stop.assert_called_once()
        self.assertTrue(self.app.closing)

    def test_commands_tab_and_named_site(self):
        self.assertEqual(self.app.tabs.tab(1, "text"), "Функции и команды")
        self.app.target_kind.set("Сайт")
        self.app._target_kind_changed()
        self.app.target_alias.insert(0, "Новости")
        self.app.target_value.set("https://example.org")
        self.app.save_target()
        self.assertEqual(self.app.settings["targets"]["sites"]["новости"], "https://example.org")
        self.assertIn("новости", self.app.target_list.get(0))
