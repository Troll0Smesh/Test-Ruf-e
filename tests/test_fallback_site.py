import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis_pc.cli import fallback_site_action
from jarvis_pc.intents import Action


class FakeRecognizer:
    def __init__(self, text, confidence):
        self.text = text
        self.confidence = confidence

    def SetWords(self, enabled):
        pass

    def AcceptWaveform(self, audio):
        return False

    def FinalResult(self):
        return json.dumps({"text": self.text, "result": [
            {"word": word, "conf": self.confidence} for word in self.text.split()]})


class FallbackSiteTests(unittest.TestCase):
    def recognize(self, text, confidence=0.95):
        module = SimpleNamespace(KaldiRecognizer=lambda model, rate: FakeRecognizer(text, confidence))
        with patch.dict(sys.modules, {"vosk": module}):
            return fallback_site_action(object(), bytes(960))

    def test_spoken_domain_opens_only_with_full_wake(self):
        self.assertEqual(self.recognize("джарвис открой сайт example точка com"),
                         Action("open_url", "https://example.com/"))
        self.assertIsNone(self.recognize("открой сайт example точка com"))

    def test_unrelated_and_uncertain_commands_do_not_open_browser(self):
        self.assertIsNone(self.recognize("джарвис заблокируй экран"))
        self.assertIsNone(self.recognize("джарвис открой сайт example точка com", 0.5))


if __name__ == "__main__":
    unittest.main()
