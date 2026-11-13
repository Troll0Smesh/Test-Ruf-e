"""Command-line entry point; native/model imports are deliberately lazy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .actions import Actions, DryRunActions
from .engine import Assistant, Settings
from .intents import command_phrases, parse_command
from .model import default_model_path, download_model, model_exists


def build_recognizer(model_path: Path):
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    phrases = command_phrases() + ["отмена", "не надо", "не выполняй команду"]
    grammar = phrases + ["[unk]", "джарвис", "джервис"]
    for wake in ("джарвис", "джервис"):
        grammar.extend(wake + " " + phrase for phrase in phrases)
    model = Model(str(model_path))
    recognizer = KaldiRecognizer(model, 16000, json.dumps(grammar, ensure_ascii=False))
    recognizer.SetWords(True)
    return model, recognizer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Джарвис — локальный помощник для Windows 10/11")
    parser.add_argument("--model", type=Path, default=default_model_path(), help="Путь к русской модели Vosk")
    parser.add_argument("--download-model", action="store_true", help="Скачать модель (~44 МБ), проверить SHA-256 и выйти")
    parser.add_argument("--dry-run", action="store_true", help="Распознавать, но не выполнять действия")
    parser.add_argument("--list-devices", action="store_true", help="Показать аудиоустройства и выйти")
    parser.add_argument("--device", help="Номер или название микрофона")
    parser.add_argument("--silence", type=float, default=0.8, help="Пауза конца команды, секунд (0.3–3, по умолчанию 0.8)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Выполнить команду текстом без слова активации (проверка обработчиков)")
    source.add_argument("--wav", help="Вместо микрофона прочитать WAV PCM16 mono 16 kHz со словом активации")
    args = parser.parse_args(argv)
    try:
        if args.download_model:
            print("Подготовка русской модели Vosk (~44 МБ при первой загрузке)…")
            download_model(args.model)
            print(f"Модель готова: {args.model}")
            return 0
        if args.list_devices:
            import sounddevice as sd
            print(sd.query_devices())
            return 0
        actions = DryRunActions() if args.dry_run else Actions()
        if args.text is not None:
            action = parse_command(args.text)
            if action is None:
                raise ValueError("Неизвестная команда. Пример: --text 'громкость 50'")
            print(actions.execute(action))
            return 0
        if sys.platform != "win32" and not args.dry_run:
            raise ValueError("Эта версия управляет Windows 10/11. Для проверки на другой ОС используйте --dry-run.")
        settings = Settings(silence_seconds=args.silence)
        args.model = args.model.expanduser()
        if not model_exists(args.model):
            raise ValueError("Русская модель не найдена. Сначала выполните jarvis --download-model (с тем же --model, если он задан).")
        import webrtcvad
        from .audio import listen, run_wav
        model, recognizer = build_recognizer(args.model)
        assistant = Assistant(recognizer, actions.execute, settings=settings)
        vad = webrtcvad.Vad(2)
        if args.wav:
            run_wav(args.wav, assistant, vad)
        else:
            device = int(args.device) if args.device and args.device.isdecimal() else args.device
            listen(assistant, vad, device)
        return 0
    except KeyboardInterrupt:
        print("\nДжарвис остановлен.")
        return 0
    except Exception as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
