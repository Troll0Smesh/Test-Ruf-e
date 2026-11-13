"""Build a real x64 Windows installer on Linux using official Windows binaries.

Requires Python/pip, msiextract, makensis on PATH. No Wine or cross compiled
Python is used: CPython and its extensions come from official binary packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jarvis_pc.model import MODEL_NAME, download_model, model_exists

ARTIFACTS = {
    "python.3.12.10.nupkg": (
        "https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg",
        "0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8",
    ),
    "tcltk.msi": (
        "https://www.python.org/ftp/python/3.12.10/amd64/tcltk.msi",
        "55c96ffad69b1c834aa52e11b9ce41637a178ba6ad6607e83956044834276e2a",
    ),
}


def sha(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def fetch(cache: Path, name: str) -> Path:
    url, expected = ARTIFACTS[name]
    path = cache / name
    if not path.exists():
        temporary = path.with_suffix(".download")
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        temporary.replace(path)
    if sha(path) != expected:
        raise ValueError(f"Checksum mismatch: {path}")
    return path


def unpack_wheel(wheel: Path, destination: Path):
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("Unsafe wheel path")
        z.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "build" / "windows-cache")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--model", type=Path, help="Existing verified small Russian model (otherwise downloaded)")
    args = parser.parse_args()
    cache, output = args.cache.resolve(), args.output.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    makensis, msiextract = shutil.which("makensis"), shutil.which("msiextract")
    if not makensis or not msiextract:
        parser.error("Install NSIS and msitools (makensis/msiextract) first")
    payload = cache / "payload"
    if payload.exists():
        shutil.rmtree(payload)  # disposable build directory, never a checkout
    payload.mkdir()
    runtime = payload / "runtime"
    runtime.mkdir()
    with zipfile.ZipFile(fetch(cache, "python.3.12.10.nupkg")) as z:
        for entry in z.infolist():
            if entry.filename.startswith("tools/") and not entry.is_dir():
                relative = Path(entry.filename).relative_to("tools")
                if ".." in relative.parts:
                    raise ValueError("Unsafe runtime path")
                target = runtime / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(entry))
    subprocess.run([msiextract, "-C", str(runtime), str(fetch(cache, "tcltk.msi"))], check=True, stdout=subprocess.DEVNULL)
    wheels = cache / "wheels"
    wheels.mkdir(exist_ok=True)
    # srt has only an sdist; build its platform independent wheel locally.
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), "srt==3.5.3"], check=True)
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--dest", str(wheels), "--find-links", str(wheels),
        "--platform", "win_amd64", "--python-version", "312", "--implementation", "cp", "--abi", "cp312",
        "--only-binary=:all:", "-r", str(ROOT / "packaging" / "requirements-windows.txt"),
    ], check=True)
    site = runtime / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    for wheel in sorted(wheels.glob("*.whl")):
        if not (wheel.name.endswith("none-any.whl") or "win_amd64" in wheel.name):
            raise ValueError(f"Non-Windows wheel in cache: {wheel.name}")
        unpack_wheel(wheel, site)
    model = args.model or cache / MODEL_NAME
    if not args.model:
        download_model(model)
    if not model_exists(model):
        raise ValueError("Incomplete model")
    shutil.copytree(model, payload / "models" / MODEL_NAME)
    shutil.copytree(ROOT / "src" / "jarvis_pc", payload / "app" / "jarvis_pc", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy(ROOT / "packaging" / "launcher.py", payload / "app" / "launcher.py")
    shutil.copy(ROOT / "LICENSE", payload / "LICENSE")
    # Remove standard library test suites, headers and build tools from runtime.
    for directory in ("include", "libs", "Scripts", "Lib/test", "Lib/ensurepip", "Lib/idlelib", "Lib/tkinter/test"):
        shutil.rmtree(runtime / directory, ignore_errors=True)
    manifest = {"version": "0.4.2", "python": "3.12.10", "architecture": "x64", "sources": ARTIFACTS,
                "wheels": {p.name: sha(p) for p in sorted(wheels.glob("*.whl"))}}
    (payload / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for script in ("launcher.nsi", "installer.nsi"):
        subprocess.run([makensis, f"-DPAYLOAD={payload}", f"-DOUTPUT={output}", str(ROOT / "packaging" / script)], check=True)
    installer = output / "Jarvis-Setup-0.4.2-x64.exe"
    installer.with_suffix(".exe.sha256").write_text(f"{sha(installer)}  {installer.name}\n", encoding="ascii")
    print(f"Built {installer} ({installer.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
