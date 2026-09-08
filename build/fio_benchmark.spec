# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_root = Path(SPEC).resolve().parent.parent

datas = []
binaries = []
hiddenimports = []

for package in ("bench_fio", "fio_plot"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

datas += copy_metadata("fio-plot")
datas.append((str(project_root / "THIRD_PARTY_NOTICES.md"), "."))

if sys.platform.startswith("win"):
    fio_vendor = project_root / "vendor" / "fio" / "windows"
    if fio_vendor.exists():
        datas.append((str(fio_vendor), "tools/fio"))

a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
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
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FioBenchmark",
)
