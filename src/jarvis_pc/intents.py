"""Small, deterministic Russian command grammar; no cloud or language model."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


ActionKind = Literal[
    "volume_set", "volume_change", "mute", "unmute",
    "minimize_window", "minimize_all", "lock", "media_pause", "media_play",
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
    # A common transposition in typed commands; spoken recognition uses громче.
    text = re.sub(r"\bгрочме\b", "громче", text)

    if text in _MEDIA_PHRASES:
        return Action(_MEDIA_PHRASES[text])

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

    match = re.fullmatch(r"(?:(?:сделай|давай) )?(?:(?:звук|громкость) )?(громче|тише)(?: (?:на )?(.+))?", text)
    if match:
        amount = 10 if match[2] is None else _number(match[2])
        if amount is not None:
            return Action("volume_change", amount if match[1] == "громче" else -amount)
        return None

    match = re.fullmatch(r"(увеличь|повысь|прибавь|добавь|подними|уменьши|понизь|убавь|снизь) (?:громкость|звук)(?: на (.+))?", text)
    if match:
        amount = 10 if match[2] is None else _number(match[2])
        if amount is not None:
            direction = 1 if match[1] in {"увеличь", "повысь", "прибавь", "добавь", "подними"} else -1
            return Action("volume_change", direction * amount)
        return None

    match = re.fullmatch(r"(?:(?:установи|поставь|сделай|выставь|установить) )?(?:громкость|звук|уровень громкости|уровень звука) (?:на )?(.+)", text)
    if match:
        amount = _number(match[1])
        if amount is not None:
            return Action("volume_set", amount)
    return None


_MEDIA_PHRASES: dict[str, ActionKind] = {}
for phrase in ["пауза", "на паузу", "поставь паузу", "поставь на паузу", "приостанови", "останови", "сделай паузу"]:
    _MEDIA_PHRASES[phrase] = "media_pause"
for noun in ["музыку", "видео", "проигрыватель", "воспроизведение", "трек", "песню"]:
    for phrase in [f"поставь {noun} на паузу", f"приостанови {noun}", f"останови {noun}"]:
        _MEDIA_PHRASES[phrase] = "media_pause"
    for phrase in [f"продолжи {noun}", f"продолжить {noun}", f"возобнови {noun}", f"возобновить {noun}", f"включи {noun}", f"запусти {noun}"]:
        _MEDIA_PHRASES[phrase] = "media_play"
for phrase in ["продолжи", "продолжить", "продолжай", "возобнови", "возобновить", "возобнови воспроизведение", "сними с паузы", "убери паузу", "снять с паузы"]:
    _MEDIA_PHRASES[phrase] = "media_play"


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
    phrases.extend(_MEDIA_PHRASES)
    for verb in ["увеличь", "повысь", "прибавь", "добавь", "подними", "уменьши", "понизь", "убавь", "снизь"]:
        for noun in ["звук", "громкость"]:
            phrases.append(f"{verb} {noun}")
    for value in range(101):
        words = _number_words(value)
        phrases.extend([
            f"громкость {words}", f"громкость на {words} процентов",
            f"установи громкость {words} процентов", f"поставь громкость {words} процентов",
            f"сделай громкость {words} процентов",
            f"громче на {words} процентов", f"тише на {words} процентов",
            f"увеличь громкость на {words} процентов", f"уменьши громкость на {words} процентов",
        ])
        # Representative phrases cover the ASR bigrams without enumerating
        # every equivalent combination and bloating the recognition graph.
        phrases.extend([
            f"звук {words}", f"звук на {words}", f"установи звук на {words} процентов",
            f"выставь уровень звука на {words}", f"установить уровень громкости {words}",
            f"сделай звук громче на {words}", f"сделай звук тише на {words}",
            f"громче на {words}", f"тише на {words}",
            f"прибавь звук на {words}", f"убавь звук на {words}",
        ])
    phrases += ["пожалуйста " + p for p in list(_MEDIA_PHRASES)]
    # The small model lacks the imperative "возобнови". Keep it for typed
    # commands, but use "возобновить" in speech; never reduce it to a bare noun.
    return [p for p in dict.fromkeys(phrases) if "возобнови" not in p.split()]
