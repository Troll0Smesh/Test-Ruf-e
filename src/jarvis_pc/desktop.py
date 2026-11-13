"""Desktop settings and a stoppable worker. No Tk or ASR import at startup."""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path
from queue import Full, Queue
import sys
from threading import Event, Thread

from .model import MODEL_NAME, default_model_path, download_model, model_exists
from .targets import clean_targets
from .discovery import available_targets


def settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config"))
    return base / "jarvis-pc" / "settings.json"


def load_settings(path: Path | None = None) -> dict:
    defaults = {"device": "", "silence": 0.8, "gain": 1.7, "dry_run": False, "targets": clean_targets(None)}
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return defaults
        if isinstance(data.get("device"), str):
            defaults["device"] = data["device"][:500]
        silence = data.get("silence")
        if type(silence) in (int, float) and 0.3 <= silence <= 3:
            defaults["silence"] = silence
        if type(data.get("dry_run")) is bool:
            defaults["dry_run"] = data["dry_run"]
        if type(data.get("gain")) in (int, float) and 1 <= data["gain"] <= 3:
            defaults["gain"] = data["gain"]
        defaults["targets"] = clean_targets(data.get("targets"))
    except (OSError, ValueError):
        pass
    return defaults


def save_settings(settings: dict, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def application_model() -> Path:
    bundled = Path(__file__).resolve().parents[2] / "models" / MODEL_NAME
    return bundled if model_exists(bundled) else default_model_path()


def input_devices() -> list[tuple[str, int]]:
    import sounddevice as sd
    hosts = sd.query_hostapis()
    return [
        (f"{d['name']} · {hosts[d['hostapi']]['name']} [{i}]", i)
        for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0
    ]


class Listener:
    def __init__(self) -> None:
        self.events: Queue[tuple[str, object]] = Queue(maxsize=100)
        self.stop_event = Event()
        self.thread: Thread | None = None

    def emit(self, kind: str, value: object) -> None:
        try:
            self.events.put_nowait((kind, value))
        except Full:
            # Keep UI traffic bounded; state is also inferred from worker life.
            pass

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, *, device=None, silence=0.8, gain=1.7, dry_run=False, targets=None) -> None:
        if self.running:
            raise RuntimeError("Прослушивание уже запущено")
        self.stop_event.clear()
        self.thread = Thread(target=self._run, args=(device, silence, gain, dry_run, clean_targets(targets)), daemon=True, name="Jarvis-listener")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self, device, silence, gain, dry_run, targets) -> None:
        com = None
        com_initialized = False
        try:
            if sys.platform != "win32" and not dry_run:
                raise RuntimeError("Управление компьютером доступно только в Windows. Включите режим проверки.")
            if sys.platform == "win32":
                import ctypes
                com = ctypes.OleDLL("ole32")
                # Match comtypes' default STA when pycaw is imported later.
                com.CoInitializeEx(None, 2)
                com_initialized = True
            self.emit("state", "Подготовка модели…")
            model_path = application_model()
            if not model_exists(model_path):
                self.emit("state", "Загрузка модели · 44 МБ…")
                download_model(model_path)
            if self.stop_event.is_set():
                return
            self._listen(model_path, device, silence, gain, dry_run, targets)
        except Exception as error:
            self.emit("error", str(error))
        finally:
            if com_initialized:
                com.CoUninitialize()
            gc.collect()
            self.emit("stopped", "Прослушивание остановлено")

    def _listen(self, model_path, device, silence, gain, dry_run, targets) -> None:
        from .actions import Actions, DryRunActions
        from .audio import listen
        from .cli import build_recognizer, fallback_site_action
        from .engine import Assistant, Settings
        import webrtcvad

        live_targets = available_targets(targets)
        model, recognizer = build_recognizer(model_path, live_targets)
        if self.stop_event.is_set():
            return
        actions = DryRunActions() if dry_run else Actions(live_targets)

        def notify(message):
            self.emit("message", message)
            if message.startswith("Микрофон включён"):
                self.emit("state", "Ожидаю «Джарвис»")
            elif message == "Слушаю…":
                self.emit("state", "Слушаю команду…")
            else:
                self.emit("state", "Ожидаю «Джарвис»")

        assistant = Assistant(recognizer, actions.execute, notify, Settings(silence_seconds=silence), live_targets,
                              lambda audio, current: fallback_site_action(model, audio, current))

        def refresh_catalogue():
            from .cli import recognizer_grammar

            updated = available_targets(targets)
            if updated != assistant.targets:
                recognizer.Reset()
                recognizer.SetGrammar(recognizer_grammar(updated))
                recognizer.SetWords(True)
                assistant.targets = updated
                if not dry_run:
                    actions.targets = updated
                self.emit("message", "Список окон, приложений и сайтов обновлён")

        listen(assistant, webrtcvad.Vad(1), device, self.stop_event,
               lambda v: self.emit("level", v), gain=gain, refresh=refresh_catalogue)
