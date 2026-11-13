"""Lightweight native desktop window. All Tk calls stay on its main thread."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty
import sys
import tkinter as tk
from tkinter import ttk

from .desktop import Listener, input_devices, load_settings, save_settings

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

        content = tk.Frame(self.root, bg=BG, padx=28)
        content.pack(fill="both", expand=True)
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
        footer.pack(side="bottom", fill="x", before=content)
        self.label(footer, "Аудио остаётся на вашем компьютере", 9, MUTED).pack(side="left")
        self.label(footer, "Windows 10 / 11  •  v0.3.0", 9, MUTED).pack(side="right")

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
            save_settings({"device": self.device_var.get(), "silence": silence, "dry_run": self.dry_run.get()})
        except OSError as error:
            self.log(f"Не удалось сохранить настройки: {error}")
        self.last_error = False
        self.busy = True
        self.controls(False)
        self.toggle.configure(text="Остановить", state="normal")
        self.status.configure(text="Подготовка…", fg=TEXT)
        self.hint.configure(text="Загружаю распознавание")
        self.listener.start(device=self.devices.get(self.device_var.get()), silence=silence, dry_run=self.dry_run.get())

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
