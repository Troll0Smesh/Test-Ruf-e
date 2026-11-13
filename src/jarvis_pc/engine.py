"""Streaming state machine, independent of microphones and operating systems."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol

from .intents import Action, parse_command


class Recognizer(Protocol):
    def AcceptWaveform(self, audio: bytes) -> bool: ...
    def Result(self) -> str: ...
    def PartialResult(self) -> str: ...
    def FinalResult(self) -> str: ...
    def Reset(self) -> None: ...


WAKE = re.compile(r"\b(?:джарвис|джервис)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Settings:
    silence_seconds: float = 0.8
    command_timeout: float = 10.0
    min_confidence: float = 0.75
    min_wake_confidence: float = 0.3

    def __post_init__(self) -> None:
        if not 0.3 <= self.silence_seconds <= 3.0:
            raise ValueError("Пауза должна быть от 0.3 до 3 секунд")
        if self.command_timeout <= self.silence_seconds:
            raise ValueError("Тайм-аут должен быть больше паузы")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("Уверенность должна быть от 0 до 1")
        if not 0 <= self.min_wake_confidence <= 1:
            raise ValueError("Уверенность активации должна быть от 0 до 1")


class Assistant:
    """One shared acoustic model; transcript exists only while activated.

    Pass exactly one audio frame with its VAD result and duration to feed().
    Wake detection uses partial results so a command may follow without a pause.
    Execution always waits for silence and the recognizer's final result.
    """

    def __init__(
        self,
        recognizer: Recognizer,
        execute: Callable[[Action], object],
        notify: Callable[[str], object] = print,
        settings: Settings = Settings(),
        targets: dict | None = None,
    ) -> None:
        self.recognizer = recognizer
        self.execute = execute
        self.notify = notify
        self.settings = settings
        self.targets = targets
        self.clock = 0.0
        self.active = False
        self.wake_confirmed = False
        self.started = 0.0
        self.idle_started = 0.0
        self.last_voice = 0.0
        self.speech_pending = False
        self.parts: list[str] = []
        self.confidences: list[float] = []
        self.wake_scores: list[float] = []

    def reset(self) -> None:
        self.recognizer.Reset()
        self.active = False
        self.wake_confirmed = False
        self.speech_pending = False
        self.parts.clear()
        self.confidences.clear()
        self.wake_scores.clear()
        self.idle_started = self.clock

    def _append(self, result: dict) -> None:
        self.parts.append(result.get("text", ""))
        for word in result.get("result", []):
            scores = self.wake_scores if WAKE.fullmatch(word.get("word", "")) else self.confidences
            scores.append(float(word["conf"]))

    def feed(self, audio: bytes, is_speech: bool, duration: float = 0.03) -> None:
        self.clock += duration
        accepted = self.recognizer.AcceptWaveform(audio)
        result = json.loads(
            self.recognizer.Result() if accepted else self.recognizer.PartialResult()
        )
        text = result.get("text" if accepted else "partial", "")

        if not self.active:
            # Require wake word at the beginning: a mention inside a sentence
            # must not arm the assistant.
            match = WAKE.match(text.strip())
            if not match:
                if accepted:
                    self.idle_started = self.clock
                elif self.clock - self.idle_started >= 20:
                    self.reset()  # bound decoder state during continuous noise
                return
            self.active = True
            self.started = self.clock
            self.last_voice = self.clock
            self.speech_pending = True
            self.notify("Слушаю…")

        if accepted:
            self._append(result)
        if is_speech:
            self.last_voice = self.clock
            self.speech_pending = True

        if self.clock - self.started >= self.settings.command_timeout:
            self.notify("Время команды истекло. Скажите «Джарвис» снова.")
            self.reset()
            return
        if not self.speech_pending or self.clock - self.last_voice < self.settings.silence_seconds:
            return

        self._append(json.loads(self.recognizer.FinalResult()))
        self.recognizer.Reset()
        transcript = " ".join(self.parts).strip()
        match = WAKE.match(transcript)
        confidence = min(self.confidences, default=0.0)
        if match:
            if min(self.wake_scores, default=0.0) < self.settings.min_wake_confidence:
                self.notify("Слово активации распознано неуверенно.")
                self.reset()
                return
            self.wake_confirmed = True
        command = transcript[match.end():].strip() if match else transcript
        self.speech_pending = False

        # A tentative partial wake must also survive final recognition.
        if not self.wake_confirmed:
            self.notify("Слово активации не подтверждено.")
            self.reset()
            return

        if not command:
            # "Джарвис" <pause> "сверни окно" is supported as well.
            self.parts.clear()
            self.confidences.clear()
            self.wake_scores.clear()
            return

        action = parse_command(command, self.targets) if confidence >= self.settings.min_confidence else None
        self.reset()  # disarm BEFORE the side effect; at most one action per wake
        if action is None:
            self.notify("Команда не распознана уверенно. Скажите «Джарвис» и повторите.")
            return
        try:
            message = self.execute(action)
            if message:
                self.notify(str(message))
        except Exception as error:
            self.notify(f"Не удалось выполнить команду: {error}")
