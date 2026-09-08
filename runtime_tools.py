import os
import shutil
import sys
from pathlib import Path


def resource_root():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _candidate_fio_paths():
    env_path = os.environ.get("FIO_BENCHMARK_FIO")
    if env_path:
        yield Path(env_path)

    appdir = os.environ.get("APPDIR")
    if appdir:
        appdir_path = Path(appdir)
        yield appdir_path / "usr" / "bin" / "fio"
        yield appdir_path / "usr" / "bin" / "fio.exe"

    root = resource_root()
    tools = root / "tools" / "fio"

    yield tools / "fio.exe"
    yield tools / "fio"

    if tools.exists():
        for name in ("fio.exe", "fio"):
            for path in tools.rglob(name):
                yield path


def find_fio():
    for candidate in _candidate_fio_paths():
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue

    found = shutil.which("fio")
    if found:
        return Path(found).resolve()

    if os.name == "nt":
        found = shutil.which("fio.exe")
        if found:
            return Path(found).resolve()

    return None


def configure_runtime_environment():
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    fio_path = find_fio()
    if fio_path is None:
        return None

    os.environ["FIO_BENCHMARK_FIO"] = str(fio_path)

    fio_dir = str(fio_path.parent)
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []

    if fio_dir not in path_parts:
        os.environ["PATH"] = fio_dir + os.pathsep + current_path

    if os.name != "nt":
        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        ld_parts = current_ld.split(os.pathsep) if current_ld else []
        if fio_dir not in ld_parts:
            os.environ["LD_LIBRARY_PATH"] = (
                fio_dir + (os.pathsep + current_ld if current_ld else "")
            )

    return fio_path
