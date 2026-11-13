"""16 kHz mono PCM, fixed-size frames, bounded producer queue."""

from __future__ import annotations

from queue import Empty, Full, Queue
from threading import Event
from typing import TYPE_CHECKING
import wave
import time

if TYPE_CHECKING:
    from .engine import Assistant

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


def run_wav(path: str, assistant: Assistant, vad) -> None:
    with wave.open(path, "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, SAMPLE_RATE, "NONE"):
            raise ValueError("Нужен WAV PCM16, моно, 16000 Гц")
        while frame := source.readframes(FRAME_SAMPLES):
            frame = frame.ljust(FRAME_BYTES, b"\0")
            assistant.feed(frame, vad.is_speech(frame, SAMPLE_RATE))
        # A file need not contain trailing silence. Flush the same endpoint
        # logic as live input, rather than executing incomplete partial text.
        for _ in range(int((assistant.settings.silence_seconds + 2) * 1000 / FRAME_MS)):
            frame = bytes(FRAME_BYTES)
            assistant.feed(frame, vad.is_speech(frame, SAMPLE_RATE))


def listen(assistant: Assistant, vad, device: int | str | None = None, stop_event: Event | None = None, on_level=None) -> None:
    import sounddevice as sd

    frames: Queue[bytes] = Queue(maxsize=32)  # <= 0.96 s, ~31 KB PCM
    overflow = Event()
    stop_event = stop_event or Event()

    def callback(indata, count, timing, status) -> None:
        if status:
            overflow.set()
        try:
            frames.put_nowait(bytes(indata))
        except Full:
            overflow.set()

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, device=device,
        dtype="int16", channels=1, callback=callback,
    ):
        assistant.notify("Микрофон включён. Скажите «Джарвис».")
        last_frame = time.monotonic()
        level_frames = 0
        while not stop_event.is_set():
            if overflow.is_set():
                # Audio loss can change command meaning: discard the entire
                # current command and wait for a fresh wake word.
                assistant.reset()
                while True:
                    try:
                        frames.get_nowait()
                    except Empty:
                        break
                overflow.clear()
                assistant.notify("Пропуск аудио. Повторите команду со слова «Джарвис».")
            try:
                frame = frames.get(timeout=0.1)
            except Empty:
                if time.monotonic() - last_frame >= 2:
                    raise RuntimeError("Микрофон перестал передавать аудио") from None
                continue
            last_frame = time.monotonic()
            if stop_event.is_set():
                break
            if overflow.is_set():
                continue
            if len(frame) != FRAME_BYTES:
                assistant.reset()
                continue
            level_frames += 1
            if on_level is not None and level_frames % 6 == 0:
                peak = max(abs(sample) for sample in memoryview(frame).cast("h")) / 32768
                on_level(peak)
            assistant.feed(frame, vad.is_speech(frame, SAMPLE_RATE))
