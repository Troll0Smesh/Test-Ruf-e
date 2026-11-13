# Сборка установщика

`build_windows.py` собирает **настоящий Windows x64 установщик NSIS**, а не
переименованный Linux executable. Внутри — официальный CPython 3.12.10 x64
из NuGet, официальный Tcl/Tk MSI с python.org, Windows wheels зависимостей,
исходники интерфейса и русская модель Vosk. Системный Python не используется.

Сборка возможна на Linux: нужны Python с pip, `nsis >= 3.11` и `msitools`.
В Debian это пакеты `nsis`, `msitools`, `python3-pip`. Виртуальное окружение:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pip
.venv/bin/python packaging/build_windows.py
```

Результат: `dist/Jarvis-Setup-0.4.0-x64.exe` и SHA-256 рядом. Сборщик скачивает
модель сам. Для существующей проверенной модели: `--model /path/to/model`.
Параметры `--cache` и `--output` меняют каталоги временных данных и результата.
Каталог `<cache>/payload` пересоздаётся при каждой сборке; не храните там свои файлы.

Windows binaries CPython/Tcl проверяются по закреплённому SHA-256.
Windows wheels получаются из PyPI по закреплённым версиям в
`requirements-windows.txt`; `srt` собирается в универсальный Python wheel.
Имена и SHA-256 wheels сохраняются в `BUILD-MANIFEST.json` внутри приложения.
Проверка SHA-256 скачанной модели находится в `jarvis_pc/model.py`.
TLS и проверка пакетов APT не отключаются.

`Jarvis.exe` — маленький нативный x64 launcher, запускающий комплектный
`runtime/pythonw.exe -I app/launcher.py`. Изолированный режим не использует
системный PYTHONPATH или пользовательские site-packages. Launcher задаёт пути
комплектного Tcl/Tk и предотвращает запуск второго экземпляра помощника.

Установка — только для текущего пользователя, без повышения прав, в
`%LOCALAPPDATA%\Programs\JarvisPC`. Установщик создаёт ярлыки и запись удаления.
Он откажется перезаписывать папку без маркера собственного приложения.
При обновлении/удалении запущенный помощник нужно сначала закрыть.

Тесты интерфейса на Linux запускаются с X-дисплеем:

```sh
DISPLAY=:99 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

В текущей облачной среде интерфейс проверен под Xvfb. Без дисплея GUI-тесты
будут **пропущены**, а не подтверждены. Проверки Windows API используют моки;
их успех не означает проверку реального микрофона или блокировки Windows.
Установщик пока не подписан сертификатом издателя.
