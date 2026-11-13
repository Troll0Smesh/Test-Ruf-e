"""Verified, explicit download of the small Russian Vosk model."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

MODEL_NAME = "vosk-model-small-ru-0.22"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_SHA256 = "961d5ff98a17f4aa6de69864d0aa71fa5bac682301d2b5d17a3f24c5c99a46d4"


def default_model_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "jarvis-pc" / MODEL_NAME


def model_exists(path: Path) -> bool:
    return all((path / item).is_file() for item in (
        "am/final.mdl", "conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst",
    ))


def download_model(destination: Path) -> None:
    destination = destination.expanduser().resolve()
    if model_exists(destination):
        return
    if destination.exists():
        raise ValueError(f"В {destination} уже есть файлы, но модель неполная. Укажите другой --model.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".jarvis-download-", dir=destination.parent) as work:
        archive = Path(work) / "model.zip"
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, archive.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 64 * 1024 * 1024:
                    raise ValueError("Сервер вернул файл неожиданного размера")
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise ValueError("SHA-256 модели не совпадает. Файл не будет использован.")
        unpacked = Path(work) / "unpacked"
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                path = Path(entry.filename)
                if path.is_absolute() or ".." in path.parts or path.parts[0] != MODEL_NAME:
                    raise ValueError("Небезопасный путь в архиве модели")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Ссылки в архиве модели не разрешены")
            package.extractall(unpacked)
        source = unpacked / MODEL_NAME
        if not model_exists(source):
            raise ValueError("В архиве нет необходимых файлов модели")
        shutil.move(str(source), str(destination))
