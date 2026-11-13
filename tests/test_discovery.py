import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from jarvis_pc.actions import Actions, ActionError
from jarvis_pc.audio import amplify
from jarvis_pc.discovery import available_targets, discover_apps, discover_windows, discover_browser_bookmarks
from jarvis_pc.intents import Action, command_phrases, parse_command


class AutomaticTargetsTests(unittest.TestCase):
    def test_youtube_and_other_sites_need_no_saved_name(self):
        self.assertEqual(parse_command("Открой YouTube"), Action("open_site", "youtube"))
        self.assertEqual(parse_command("открой ютуб"), Action("open_site", "ютуб"))
        self.assertEqual(parse_command("открой сайт Википедия"), Action("open_site", "википедия"))
        self.assertEqual(parse_command("открой сайт example точка com"), Action("open_url", "https://example.com/"))
        self.assertIn("открой ютуб", command_phrases())
        self.assertIsNone(parse_command("открой сайт неизвестный"))

    def test_site_opens_expected_url(self):
        with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.webbrowser.open", return_value=True) as browser:
            Actions().execute(parse_command("открой ютуб"))
            browser.assert_called_once_with("https://www.youtube.com/")

    def test_open_url_rejects_non_web_scheme(self):
        with self.assertRaises(ValueError):
            Actions().execute(Action("open_url", "javascript:alert(1)"))

    def test_start_menu_and_open_windows_are_discovered(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            folder = base / "Roaming/Microsoft/Windows/Start Menu/Programs"
            folder.mkdir(parents=True)
            (folder / "Google Chrome.lnk").touch()
            (folder / "Uninstall Google Chrome.lnk").touch()
            with patch.object(sys, "platform", "win32"), \
                 patch.dict(os.environ, {"APPDATA": str(base / "Roaming"), "PROGRAMDATA": str(base / "ProgramData"), "WINDIR": str(base / "Windows")}), \
                 patch("jarvis_pc.actions.visible_windows", return_value=[(1, "Video - Google Chrome"), (2, "Notes - Блокнот")]):
                targets = available_targets()
            self.assertEqual(targets["windows"]["гугл хром"], "Video - Google Chrome")
            self.assertEqual(targets["apps"]["хром"], str(folder / "Google Chrome.lnk"))
            self.assertEqual(parse_command("сверни окно гугл хром", targets), Action("minimize_named", "гугл хром"))
            self.assertEqual(parse_command("запусти хром", targets), Action("open_app", "хром"))

    def test_ambiguous_window_alias_is_omitted(self):
        with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.visible_windows", return_value=[
            (1, "First - Google Chrome"), (2, "Second - Google Chrome")]):
            self.assertNotIn("хром", discover_windows())

    def test_user_name_overrides_detected_name(self):
        with patch.object(sys, "platform", "win32"), patch("jarvis_pc.actions.visible_windows", return_value=[]), \
             patch("jarvis_pc.discovery.discover_apps", return_value={"браузер": "C:/Browser.exe"}):
            targets = available_targets({"apps": {"браузер": "D:/MyBrowser.exe"}})
        self.assertEqual(targets["apps"]["браузер"], "D:/MyBrowser.exe")

    def test_chromium_bookmarks_are_available_without_jarvis_setup(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "Google/Chrome/User Data/Default"
            profile.mkdir(parents=True)
            (profile / "Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {
                "children": [{"name": "Мой форум", "url": "https://forum.example.org/"},
                             {"name": "Плохая ссылка", "url": "javascript:alert(1)"}]}}}), encoding="utf-8")
            with patch.object(sys, "platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": root}):
                sites = discover_browser_bookmarks()
            self.assertEqual(sites, {"мой форум": "https://forum.example.org/"})


class MicrophoneGainTests(unittest.TestCase):
    def test_amplifies_quiet_pcm_and_clamps_loud_samples(self):
        from array import array

        frame = array("h", [1000, -1000, 30000, -30000, 0]).tobytes()
        self.assertEqual(list(array("h", amplify(frame, 2.0))), [2000, -2000, 32767, -32768, 0])
        self.assertEqual(amplify(frame, 1.0), frame)


if __name__ == "__main__":
    unittest.main()
