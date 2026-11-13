import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from jarvis_pc.model import MODEL_NAME, download_model, model_exists


def archive_bytes(extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name in ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst"):
            z.writestr(f"{MODEL_NAME}/{name}", "test")
        if extra:
            z.writestr(extra, "bad")
    return stream.getvalue()


class ModelTests(unittest.TestCase):
    def test_verified_download_and_repeat(self):
        data = archive_bytes()
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "model"
            with patch("jarvis_pc.model.urllib.request.urlopen", return_value=io.BytesIO(data)) as request, patch("jarvis_pc.model.MODEL_SHA256", hashlib.sha256(data).hexdigest()):
                download_model(dest)
                self.assertTrue(model_exists(dest))
                download_model(dest)
                request.assert_called_once()

    def test_wrong_hash_never_extracts(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "model"
            with patch("jarvis_pc.model.urllib.request.urlopen", return_value=io.BytesIO(b"corrupted")):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    download_model(dest)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_traversal_rejected_even_with_valid_hash(self):
        data = archive_bytes("../escape")
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "model"
            with patch("jarvis_pc.model.urllib.request.urlopen", return_value=io.BytesIO(data)), patch("jarvis_pc.model.MODEL_SHA256", hashlib.sha256(data).hexdigest()):
                with self.assertRaisesRegex(ValueError, "Небезопасный"):
                    download_model(dest)
            self.assertFalse(dest.exists())

    def test_existing_partial_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "model"
            dest.mkdir()
            (dest / "user-file").write_text("keep")
            with self.assertRaisesRegex(ValueError, "неполная"):
                download_model(dest)
            self.assertEqual((dest / "user-file").read_text(), "keep")
