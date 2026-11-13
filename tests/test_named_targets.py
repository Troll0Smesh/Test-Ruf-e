import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis_pc.actions import Actions, ActionError
from jarvis_pc.intents import Action, command_phrases, parse_command
from jarvis_pc.targets import clean_targets


TARGETS = {
    "windows": {"браузер": "Mozilla Firefox"},
    "apps": {"блокнот": "C:\\Windows\\notepad.exe"},
    "sites": {"новости": "https://example.org/news"},
}


class NamedTargetsTests(unittest.TestCase):
    def test_named_commands_are_in_recognizer_grammar(self):
        cases = {
            "сверни окно браузер": Action("minimize_named", "браузер"),
            "разверни браузер": Action("restore_named", "браузер"),
            "запусти приложение блокнот": Action("open_app", "блокнот"),
            "открой сайт новости": Action("open_site", "новости"),
        }
        for phrase, expected in cases.items():
            self.assertEqual(parse_command(phrase, TARGETS), expected)
            self.assertIn(phrase, command_phrases(TARGETS))
            self.assertIsNone(parse_command(phrase), phrase)

    def test_invalid_saved_targets_are_ignored(self):
        data = {"sites": {"новости": "javascript:alert(1)", "поиск": "https://example.org"},
                "apps": {"терминал": "cmd /c bad"}, "windows": {"": "Firefox"}}
        self.assertEqual(clean_targets(data), {"windows": {}, "apps": {}, "sites": {"поиск": "https://example.org"}})

    def test_targeted_window_acts_on_matching_handle(self):
        with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.visible_windows", return_value=[(17, "Other"), (42, "Mozilla Firefox")]), \
             patch("jarvis_pc.actions._user32") as user32:
            actions = Actions(TARGETS)
            actions.execute(Action("minimize_named", "браузер"))
            user32.return_value.ShowWindow.assert_called_with(42, 6)
            actions.execute(Action("restore_named", "браузер"))
            user32.return_value.ShowWindow.assert_called_with(42, 3)
            user32.return_value.SetForegroundWindow.assert_called_with(42)

    def test_ambiguous_window_does_not_minimize(self):
        with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.visible_windows", return_value=[(1, "Firefox One"), (2, "Firefox Two")]), \
             patch("jarvis_pc.actions._user32") as user32:
            with self.assertRaisesRegex(ActionError, "несколько"):
                Actions({**TARGETS, "windows": {"браузер": "Firefox"}}).execute(Action("minimize_named", "браузер"))
            user32.return_value.ShowWindow.assert_not_called()

    def test_application_and_site_use_saved_values(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "notepad.exe"
            path.touch()
            targets = {**TARGETS, "apps": {"блокнот": str(path)}}
            with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.os.startfile", create=True) as start, \
                 patch("jarvis_pc.actions.webbrowser.open", return_value=True) as browser:
                actions = Actions(targets)
                actions.execute(Action("open_app", "блокнот"))
                actions.execute(Action("open_site", "новости"))
                start.assert_called_once_with(str(path))
                browser.assert_called_once_with("https://example.org/news")


if __name__ == "__main__":
    unittest.main()
