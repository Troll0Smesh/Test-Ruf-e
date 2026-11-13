import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from jarvis_pc.audio import FRAME_BYTES, run_wav
from jarvis_pc.cli import main
from jarvis_pc.engine import Settings


class CliAudioTests(unittest.TestCase):
    def test_text_dry_run_has_no_native_side_effects(self):
        with patch("jarvis_pc.actions._user32", side_effect=AssertionError), patch("jarvis_pc.actions._endpoint", side_effect=AssertionError), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--dry-run", "--text", "громкость 50"]), 0)
            self.assertIn("volume_set 50", output.getvalue())

    def test_unknown_text_fails(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(main(["--dry-run", "--text", "не заблокируй ноутбук"]), 1)

    def test_wav_frames_are_padded_and_endpoint_gets_silence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "clip.wav"
            with wave.open(str(path), "wb") as out:
                out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                out.writeframes(bytes(1000))
            assistant = Mock(settings=Settings())
            vad = Mock()
            vad.is_speech.return_value = False
            run_wav(str(path), assistant, vad)
            self.assertGreater(assistant.feed.call_count, 28)
            self.assertTrue(all(len(c.args[0]) == FRAME_BYTES for c in assistant.feed.call_args_list))

    def test_wav_rejects_wrong_sample_rate(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "clip.wav"
            with wave.open(str(path), "wb") as out:
                out.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                out.writeframes(bytes(1000))
            with self.assertRaisesRegex(ValueError, "16000"):
                run_wav(str(path), Mock(), Mock())
