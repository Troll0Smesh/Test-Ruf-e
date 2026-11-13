"""Entry used by the bundled pythonw.exe (isolated mode, no system Python)."""
import ctypes
import os
from pathlib import Path
import sys

base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base / "app"))
os.environ["TCL_LIBRARY"] = str(base / "runtime" / "tcl" / "tcl8.6")
os.environ["TK_LIBRARY"] = str(base / "runtime" / "tcl" / "tk8.6")

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
kernel.CreateMutexW.restype = ctypes.c_void_p
mutex = kernel.CreateMutexW(None, False, "Local\\JarvisPC.Desktop")
if not mutex:
    raise ctypes.WinError(ctypes.get_last_error())
if ctypes.get_last_error() == 183:
    ctypes.windll.user32.MessageBoxW(None, "Джарвис уже запущен. Откройте его окно на панели задач.", "Джарвис", 0x40)
    sys.exit(0)
try:
    from jarvis_pc.gui import main
    main()
except Exception as error:
    ctypes.windll.user32.MessageBoxW(None, str(error), "Не удалось запустить Джарвис", 0x10)
    sys.exit(1)
finally:
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle(mutex)
