"""Lightweight native desktop window. All Tk calls stay on its main thread."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty
import sys
import tkinter as tk
from tkinter import filedialog, ttk

from .desktop import Listener, input_devices, load_settings, save_settings
from .intents import command_phrases
from .targets import KINDS, LABELS, clean_alias, clean_value

BG = "#0b1019"
PANEL = "#131c29"
BORDER = "#233246"
TEXT = "#edf5ff"
MUTED = "#95a6bc"
ACCENT = "#66e2c4"
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"


class JarvisWindow:
    def __init__(self, root: tk.Tk, *, listener=None, enumerate_devices=input_devices) -> None:
        self.root = root
        self.listener = listener or Listener()
        self.enumerate_devices = enumerate_devices
        self.devices = {}
        self.busy = False
        self.closing = False
        self.last_error = False
        self.settings = load_settings()
        root.title("Джарвис")
        if sys.platform == "win32":
            root.iconbitmap(str(Path(__file__).parent / "assets" / "jarvis.ico"))
        root.geometry("960x800")
        root.minsize(900, 760)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._styles()
        self._build()
        self.refresh_devices()
        self.log("Готов к запуску. Нажмите «Включить микрофон».")
        self.root.after(100, self.poll)

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL, background=BORDER, foreground=TEXT, arrowcolor=ACCENT, bordercolor=BORDER, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=(FONT, 10))
        style.map("TCheckbutton", background=[("active", PANEL)])
        style.configure("TSpinbox", fieldbackground=PANEL, background=BORDER, foreground=TEXT, arrowcolor=ACCENT, padding=6)
        style.configure("Jarvis.Horizontal.TProgressbar", troughcolor=BORDER, background=ACCENT, borderwidth=0)
        style.configure("Jarvis.TNotebook", background=BG, borderwidth=0)
        style.configure("Jarvis.TNotebook.Tab", background=BORDER, foreground=TEXT, padding=(18, 9), font=(FONT, 10))
        style.map("Jarvis.TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", ACCENT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)

    def label(self, parent, text, size=10, color=TEXT, **kwargs):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color, font=(FONT, size), **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else BORDER,
                         fg=BG if primary else TEXT, activebackground="#8cedd6" if primary else "#34465d",
                         activeforeground=BG if primary else TEXT, relief="flat", bd=0,
                         cursor="hand2", font=(FONT, 11, "bold"), padx=16, pady=10)

    def _build(self):
        header = tk.Frame(self.root, bg=BG, padx=28, pady=20)
        header.pack(fill="x")
        self.label(header, "ДЖАРВИС", 22).pack(side="left")
        self.label(header, "ВАШ ГОЛОС. ВАШ КОМПЬЮТЕР.", 9, MUTED).pack(side="left", padx=20)
        self.label(header, "●  ЛОКАЛЬНО", 9, ACCENT).pack(side="right")

        self.tabs = ttk.Notebook(self.root, style="Jarvis.TNotebook")
        self.tabs.pack(fill="both", expand=True, padx=20)
        content = tk.Frame(self.tabs, bg=BG, padx=8, pady=12)
        self.tabs.add(content, text="Главная")
        commands = tk.Frame(self.tabs, bg=BG, padx=8, pady=12)
        self.tabs.add(commands, text="Функции и команды")
        content.columnconfigure(0, weight=1, uniform="columns")
        content.columnconfigure(1, weight=1, uniform="columns")
        left = tk.Frame(content, bg=PANEL, padx=24, pady=20, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = tk.Frame(content, bg=PANEL, padx=22, pady=20, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.label(left, "ГОЛОСОВОЙ ПОМОЩНИК", 9, MUTED).pack(anchor="w")
        orb = tk.Canvas(left, width=250, height=155, bg=PANEL, highlightthickness=0)
        orb.pack(pady=(10, 0))
        orb.create_oval(62, 8, 188, 134, outline=BORDER, width=1)
        orb.create_oval(73, 19, 177, 123, outline="#325a5d", width=2)
        self.orb_circle = orb.create_oval(88, 34, 162, 108, fill="#1a353c", outline=ACCENT, width=2)
        orb.create_text(125, 71, text="J", font=(FONT, 30, "bold"), fill=ACCENT)
        self.status = self.label(left, "Прослушивание выключено", 15)
        self.status.pack()
        self.hint = self.label(left, "Микрофон отключён", 10, MUTED)
        self.hint.pack(pady=(6, 16))
        self.toggle = self.button(left, "Включить микрофон", self.toggle_listening, True)
        self.toggle.pack(fill="x")
        self.level = ttk.Progressbar(left, maximum=100, style="Jarvis.Horizontal.TProgressbar")
        self.level.pack(fill="x", pady=(15, 4))
        self.label(left, "УРОВЕНЬ МИКРОФОНА", 8, MUTED).pack(anchor="w")
        self.label(left, "Скажите: «Джарвис, сделай тише»", 10, MUTED).pack(pady=(15, 0))

        self.label(right, "НАСТРОЙКИ", 9, MUTED).pack(anchor="w", pady=(0, 17))
        self.label(right, "Микрофон", 11).pack(anchor="w")
        self.device_var = tk.StringVar()
        self.device_box = ttk.Combobox(right, textvariable=self.device_var, state="readonly")
        self.device_box.pack(fill="x", pady=(7, 7))
        self.refresh = self.button(right, "Обновить устройства", self.refresh_devices)
        self.refresh.pack(anchor="w", pady=(0, 17))
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x")
        self.label(row, "Пауза в конце команды", 11).pack(side="left")
        self.silence_var = tk.StringVar(value=str(self.settings["silence"]))
        self.silence_box = ttk.Spinbox(row, from_=0.3, to=3.0, increment=0.1, width=4, textvariable=self.silence_var)
        self.silence_box.pack(side="right")
        self.label(right, "Секунды тишины · по умолчанию 0,8", 9, MUTED).pack(anchor="w", pady=(7, 17))
        self.dry_run = tk.BooleanVar(value=self.settings["dry_run"] or sys.platform != "win32")
        self.test_check = ttk.Checkbutton(right, text="Проверка без выполнения действий", variable=self.dry_run)
        self.test_check.pack(anchor="w")
        self.label(right, "В этом режиме команды видны в журнале,\nно громкость и окна не меняются.", 9, MUTED, justify="left").pack(anchor="w", pady=(8, 0))

        examples = tk.Frame(content, bg=BG)
        examples.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(19, 17))
        for i, (title, text) in enumerate([
            ("01  ГРОМКОСТЬ", "«Громкость на пятьдесят процентов»"),
            ("02  ОКНА", "«Сверни все окна»"),
            ("03  ВОСПРОИЗВЕДЕНИЕ", "«Поставь музыку на паузу»"),
        ]):
            card = tk.Frame(examples, bg=PANEL, padx=13, pady=13)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            examples.columnconfigure(i, weight=1)
            self.label(card, title, 9, ACCENT).pack(anchor="w")
            self.label(card, text, 9, MUTED).pack(anchor="w", pady=(7, 0))

        self.label(content, "ЖУРНАЛ КОМАНД", 9, MUTED).grid(row=2, column=0, sticky="w")
        self.journal = tk.Text(content, height=5, bg=PANEL, fg=MUTED, font=(FONT, 10),
                               wrap="word", relief="flat", padx=12, pady=8, state="disabled", takefocus=False)
        self.journal.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        content.rowconfigure(3, weight=1)
        footer = tk.Frame(self.root, bg=BG, padx=28, pady=12)
        footer.pack(side="bottom", fill="x", before=self.tabs)
        self.label(footer, "Аудио остаётся на вашем компьютере", 9, MUTED).pack(side="left")
        self.label(footer, "Windows 10 / 11  •  v0.4.2", 9, MUTED).pack(side="right")
        self._build_commands_tab(commands)

    def _build_commands_tab(self, parent):
        self.label(parent, "ВСЕ ФУНКЦИИ", 11, ACCENT).pack(anchor="w", pady=(0, 7))
        guide_frame = tk.Frame(parent, bg=BG)
        guide_frame.pack(fill="x")
        guide = tk.Text(guide_frame, height=9, bg=PANEL, fg=TEXT, font=(FONT, 10), wrap="word",
                        relief="flat", padx=13, pady=10, highlightbackground=BORDER, highlightthickness=1)
        guide.pack(side="left", fill="x", expand=True)
        guide_scroll = ttk.Scrollbar(guide_frame, command=guide.yview)
        guide_scroll.pack(side="right", fill="y")
        guide.configure(yscrollcommand=guide_scroll.set)
        guide.insert("1.0", (
            "Каждую команду начните со слова «Джарвис». Дождитесь паузы после команды.\n\n"
            "ГРОМКОСТЬ\n"
            "«Громче», «тише» — изменить на 10%. «Громче на двадцать», «убавь звук на пять» — изменить на указанное число. "
            "«Звук сорок», «громкость на пятьдесят процентов» — установить уровень от 0 до 100%. "
            "«Выключи звук», «включи звук» — выключить и включить звук.\n\n"
            "ВОСПРОИЗВЕДЕНИЕ\n"
            "«Пауза», «поставь музыку на паузу», «приостанови видео» — приостановить. "
            "«Продолжи», «продолжить воспроизведение», «сними с паузы» — продолжить. "
            "Повторная пауза не запускает воспроизведение. Работает с проигрывателями, которые поддерживают медиасессию Windows.\n\n"
            "ОКНА И СИСТЕМА\n"
            "«Сверни окно» — активное окно. «Сверни все окна», «покажи рабочий стол» — все окна. "
            "«Заблокируй ноутбук», «заблокируй экран» — блокировка Windows.\n\n"
            "ИМЕННЫЕ ОКНА, ПРИЛОЖЕНИЯ И САЙТЫ\n"
            "Добавьте имя ниже. Затем говорите «сверни окно <имя>», «разверни окно <имя>», "
            "«открой приложение <имя>» или «открой сайт <имя>». Новые имена действуют после перезапуска прослушивания."
        ))
        guide.configure(state="disabled")
        self.button(parent, "Показать полный список фраз", self.show_all_commands).pack(anchor="w", pady=(8, 0))
        self.label(parent, "ИМЕНА ДЛЯ ГОЛОСОВЫХ КОМАНД", 11, ACCENT).pack(anchor="w", pady=(15, 7))
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=PANEL, padx=12, pady=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.target_list = tk.Listbox(left, bg=PANEL, fg=TEXT, selectbackground=BORDER,
                                      font=(FONT, 10), relief="flat", exportselection=False)
        self.target_list.pack(fill="both", expand=True)
        self.target_list.bind("<<ListboxSelect>>", self._select_target)
        self.button(left, "Удалить выбранное", self.delete_target).pack(anchor="w", pady=(8, 0))
        right = tk.Frame(body, bg=PANEL, padx=12, pady=12)
        right.pack(side="left", fill="both", expand=True)
        self.label(right, "Тип", 10).pack(anchor="w")
        self.target_kind = tk.StringVar(value=LABELS["windows"])
        self.target_kind_box = ttk.Combobox(right, textvariable=self.target_kind, state="readonly", values=list(LABELS.values()))
        self.target_kind_box.pack(fill="x", pady=(4, 8))
        self.target_kind_box.bind("<<ComboboxSelected>>", lambda _: self._target_kind_changed())
        self.label(right, "Имя для голоса, например «браузер»", 10).pack(anchor="w")
        self.target_alias = ttk.Entry(right)
        self.target_alias.pack(fill="x", pady=(4, 8))
        self.target_value_label = self.label(right, "Заголовок окна", 10)
        self.target_value_label.pack(anchor="w")
        self.target_value = ttk.Combobox(right)
        self.target_value.pack(fill="x", pady=(4, 8))
        self.button(right, "Выбрать окно / файл", self.choose_target).pack(anchor="w")
        self.button(right, "Сохранить имя", self.save_target, True).pack(fill="x", pady=(10, 0))
        self._target_kind_changed()
        self._refresh_targets()

    def show_all_commands(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Все голосовые команды Джарвиса")
        dialog.geometry("690x600")
        dialog.configure(bg=BG)
        frame = tk.Frame(dialog, bg=BG, padx=15, pady=15)
        frame.pack(fill="both", expand=True)
        phrases = command_phrases(self.settings["targets"])
        self.label(frame, f"ВСЕ РАСПОЗНАВАЕМЫЕ ФРАЗЫ · {len(phrases)}", 11, ACCENT).pack(anchor="w")
        search = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=search)
        entry.pack(fill="x", pady=(10, 8))
        box = tk.Listbox(frame, bg=PANEL, fg=TEXT, selectbackground=BORDER,
                         font=(FONT, 10), relief="flat")
        box.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, command=box.yview)
        scrollbar.pack(side="right", fill="y")
        box.configure(yscrollcommand=scrollbar.set)

        def update(*_):
            query = search.get().lower().replace("ё", "е").strip()
            box.delete(0, "end")
            for phrase in phrases:
                if query in phrase:
                    box.insert("end", "Джарвис, " + phrase)

        search.trace_add("write", update)
        update()
        entry.focus_set()

    def _kind(self):
        return next(kind for kind, label in LABELS.items() if label == self.target_kind.get())

    def _target_kind_changed(self):
        kind = self._kind()
        self.target_value_label.configure(text={"windows": "Заголовок окна", "apps": "Путь к .exe или .lnk", "sites": "Адрес сайта (https://...)"}[kind])
        self.target_value["values"] = [title for _, title in self._windows()] if kind == "windows" else []

    def _windows(self):
        from .actions import visible_windows
        return visible_windows()

    def choose_target(self):
        kind = self._kind()
        if kind == "windows":
            self._target_kind_changed()
            self.target_value.focus_set()
            self.target_value.event_generate("<Down>")
        elif kind == "apps":
            path = filedialog.askopenfilename(title="Выберите приложение", filetypes=[("Приложения", "*.exe *.lnk")])
            if path:
                self.target_value.set(path)
        else:
            self.target_value.set("https://")

    def _refresh_targets(self):
        self.target_list.delete(0, "end")
        self.target_rows = []
        for kind in KINDS:
            for alias, value in sorted(self.settings["targets"][kind].items()):
                self.target_rows.append((kind, alias))
                self.target_list.insert("end", f"{LABELS[kind]} · {alias} → {value}")

    def _select_target(self, _=None):
        selected = self.target_list.curselection()
        if not selected:
            return
        kind, alias = self.target_rows[selected[0]]
        self.target_kind.set(LABELS[kind])
        self._target_kind_changed()
        self.target_alias.delete(0, "end")
        self.target_alias.insert(0, alias)
        self.target_value.set(self.settings["targets"][kind][alias])

    def _persist(self):
        save_settings({"device": self.device_var.get(), "silence": self.settings["silence"],
                       "dry_run": self.dry_run.get(), "targets": self.settings["targets"]})

    def save_target(self):
        try:
            kind = self._kind()
            alias = clean_alias(self.target_alias.get())
            value = clean_value(kind, self.target_value.get())
            self.settings["targets"][kind][alias] = value
            self._persist()
            self._refresh_targets()
            self.log(f"Имя «{alias}» сохранено. Перезапустите прослушивание для голосовой команды.")
        except (ValueError, OSError) as error:
            self.log(f"Не удалось сохранить имя: {error}")

    def delete_target(self):
        selected = self.target_list.curselection()
        if not selected:
            return
        kind, alias = self.target_rows[selected[0]]
        try:
            del self.settings["targets"][kind][alias]
            self._persist()
            self._refresh_targets()
            self.log(f"Имя «{alias}» удалено. Перезапустите прослушивание.")
        except OSError as error:
            self.log(f"Не удалось удалить имя: {error}")

    def log(self, text):
        self.journal.configure(state="normal")
        self.journal.insert("end", f"{datetime.now():%H:%M:%S}   {text}\n")
        if int(self.journal.index("end-1c").split(".")[0]) > 100:
            self.journal.delete("1.0", "2.0")
        self.journal.see("end")
        self.journal.configure(state="disabled")

    def refresh_devices(self):
        selected = self.device_var.get() or self.settings["device"]
        self.devices = {"Системный микрофон": None}
        try:
            self.devices.update(self.enumerate_devices())
            if len(self.devices) == 1:
                self.log("Микрофон не найден. Подключите его и обновите устройства.")
        except Exception as error:
            self.log(f"Не удалось найти микрофон: {error}")
        self.device_box["values"] = list(self.devices)
        self.device_var.set(selected if selected in self.devices else "Системный микрофон")

    def controls(self, enabled):
        self.device_box.configure(state="readonly" if enabled else "disabled")
        self.silence_box.configure(state="normal" if enabled else "disabled")
        self.test_check.configure(state="normal" if enabled else "disabled")
        self.refresh.configure(state="normal" if enabled else "disabled")

    def toggle_listening(self):
        if self.busy:
            self.listener.stop()
            self.status.configure(text="Остановка…")
            self.toggle.configure(state="disabled")
            return
        try:
            silence = float(self.silence_var.get().replace(",", "."))
            if not 0.3 <= silence <= 3:
                raise ValueError
        except ValueError:
            self.log("Укажите паузу от 0,3 до 3 секунд.")
            return
        try:
            self.settings["silence"] = silence
            self._persist()
        except OSError as error:
            self.log(f"Не удалось сохранить настройки: {error}")
        self.last_error = False
        self.busy = True
        self.controls(False)
        self.toggle.configure(text="Остановить", state="normal")
        self.status.configure(text="Подготовка…", fg=TEXT)
        self.hint.configure(text="Загружаю распознавание")
        self.listener.start(device=self.devices.get(self.device_var.get()), silence=silence, dry_run=self.dry_run.get(), targets=self.settings["targets"])

    def poll(self):
        for _ in range(100):
            try:
                kind, value = self.listener.events.get_nowait()
            except Empty:
                break
            if kind == "level":
                self.level["value"] = min(100, float(value) * 300)
            elif kind == "state":
                self.status.configure(text=value)
                self.hint.configure(text="Режим проверки" if self.dry_run.get() else "Одна команда после каждого обращения")
            elif kind == "error":
                self.last_error = True
                self.log(f"Ошибка: {value}")
            elif kind == "message":
                self.log(value)
        if self.busy and not self.listener.running:
            self.busy = False
            self.controls(True)
            self.toggle.configure(text="Включить микрофон", state="normal")
            self.level["value"] = 0
            self.status.configure(text="Не удалось запустить" if self.last_error else "Прослушивание выключено")
            self.hint.configure(text="Подробности в журнале" if self.last_error else "Микрофон отключён · модель освобождена")
        if self.closing and not self.listener.running:
            self.root.destroy()
            return
        self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        self.listener.stop()
        if not self.listener.running:
            self.root.destroy()
            return
        self.status.configure(text="Завершаю работу…")
        self.toggle.configure(state="disabled")
        self.controls(False)


def main():
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    JarvisWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
