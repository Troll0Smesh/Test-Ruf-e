"""Small, deterministic Russian command grammar; no cloud or language model."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


ActionKind = Literal[
    "volume_set", "volume_change", "mute", "unmute",
    "minimize_window", "minimize_all", "lock",
]


@dataclass(frozen=True, slots=True)
class Action:
    kind: ActionKind
    value: int | None = None


_SMALL = (
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять", "одиннадцать", "двенадцать",
    "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS = {
    20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят",
    60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят", 90: "девяносто",
}


def _number_words(value: int) -> str:
    if value < 20:
        return _SMALL[value]
    if value == 100:
        return "сто"
    tens, ones = divmod(value, 10)
    return _TENS[tens * 10] + (" " + _SMALL[ones] if ones else "")


_NUMBERS = {_number_words(n): n for n in range(101)}
_NUMBERS.update({"нуль": 0, "одна": 1, "две": 2})


def normalize_text(text: str) -> str:
    """Normalize recognizer output without removing negations or other words."""
    text = text.lower().replace("ё", "е").replace("%", " процентов ")
    text = re.sub(r"[.,!?;:]", " ", text)
    return " ".join(text.split())


def _number(text: str) -> int | None:
    text = re.sub(r"\s+процент(?:а|ов)?$", "", text)
    if re.fullmatch(r"[0-9]{1,3}", text):
        value = int(text)
        return value if value <= 100 else None
    return _NUMBERS.get(text)


def parse_command(text: str) -> Action | None:
    """Parse an entire command, returning None for unsupported/ambiguous text.

    The wake word belongs to the listening state machine and must be removed
    before calling this function. No substring matching is used: extra words,
    negations and multiple commands cannot accidentally execute an action.
    """
    text = normalize_text(text)
    if text.startswith("пожалуйста "):
        text = text[len("пожалуйста "):]
    if text.endswith(" пожалуйста"):
        text = text[:-len(" пожалуйста")]

    fixed: dict[str, ActionKind] = {
        "выключи звук": "mute",
        "отключи звук": "mute",
        "убери звук": "mute",
        "включи звук": "unmute",
        "верни звук": "unmute",
        "сверни окно": "minimize_window",
        "сверни активное окно": "minimize_window",
        "сверни текущее окно": "minimize_window",
        "сверни все окна": "minimize_all",
        "покажи рабочий стол": "minimize_all",
        "заблокируй компьютер": "lock",
        "заблокируй ноутбук": "lock",
        "заблокируй ноут": "lock",
        "заблокируй экран": "lock",
    }
    if text in fixed:
        return Action(fixed[text])

    match = re.fullmatch(r"(?:(?:сделай|давай) )?(громче|тише)(?: на (.+))?", text)
    if match:
        amount = 10 if match[2] is None else _number(match[2])
        if amount is not None:
            return Action("volume_change", amount if match[1] == "громче" else -amount)
        return None

    match = re.fullmatch(r"(увеличь|повысь|прибавь|уменьши|понизь|убавь) громкость(?: на (.+))?", text)
    if match:
        amount = 10 if match[2] is None else _number(match[2])
        if amount is not None:
            direction = 1 if match[1] in {"увеличь", "повысь", "прибавь"} else -1
            return Action("volume_change", direction * amount)
        return None

    match = re.fullmatch(r"(?:(?:установи|поставь|сделай) )?громкость (?:на )?(.+)", text)
    if match:
        amount = _number(match[1])
        if amount is not None:
            return Action("volume_set", amount)
    return None


def command_phrases() -> list[str]:
    """Canonical spoken forms for a constrained offline recognizer grammar."""
    phrases = [
        "выключи звук", "отключи звук", "убери звук", "включи звук", "верни звук",
        "сверни окно", "сверни активное окно", "сверни текущее окно",
        "сверни все окна", "покажи рабочий стол", "заблокируй компьютер",
        "заблокируй ноутбук", "заблокируй ноут", "заблокируй экран",
        "громче", "тише", "сделай громче", "сделай тише",
        "увеличь громкость", "уменьши громкость",
    ]
    for value in range(101):
        words = _number_words(value)
        phrases.extend([
            f"громкость {words}", f"громкость на {words} процентов",
            f"установи громкость {words} процентов", f"поставь громкость {words} процентов",
            f"сделай громкость {words} процентов",
            f"громче на {words} процентов", f"тише на {words} процентов",
            f"увеличь громкость на {words} процентов", f"уменьши громкость на {words} процентов",
        ])
    return phrases
