# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_root = Path(SPEC).resolve().parent.parent

datas = []
binaries = []
hiddenimports = []


def collect_package(package_name):
    package_datas, package_binaries, package_hidden = collect_all(package_name)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hidden)


collect_package("bench_fio")
collect_package("fio_plot")
collect_package("PIL")

hiddenimports += [
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "_tkinter",
    "PIL.Image",
    "PIL.PngImagePlugin",
    "matplotlib.backends.backend_agg",
    "mpl_toolkits.mplot3d",
    "numpy",
    "pyparsing",
    "rich",
]

datas += copy_metadata("fio-plot")
datas += copy_metadata("Pillow")
datas.append((str(project_root / "THIRD_PARTY_NOTICES.md"), "."))

if sys.platform.startswith("win"):
    fio_vendor = project_root / "vendor" / "fio" / "windows"
    if not fio_vendor.exists():
        raise RuntimeError("vendor/fio/windows não existe durante o build.")
    datas.append((str(fio_vendor), "tools/fio"))

a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        "matplotlib": {
            "backends": ["Agg"],
        },
    },
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FioBenchmark",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FioBenchmark",
)
