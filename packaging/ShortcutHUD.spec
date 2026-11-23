# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the ShortcutHUD portable Windows bundle (onedir)."""

import os

# Windows 10/11 自带 ICU（System32\icuuc.dll，符号无版本后缀），PySide6 的 Qt6Core 正是
# 按这套符号链接的。构建机的 PATH 里如果有 conda/其它 ICU 发行版，PyInstaller 会把
# 带 `_73` 版本后缀符号的 icuuc.dll / icudt*.dll 一起收进来，导致打包版启动即
# `ImportError: DLL load failed while importing QtWidgets` (ERROR_PROC_NOT_FOUND, 127)。
_DROPPED_ICU_PREFIXES = ("icuuc", "icuin", "icudt", "icuio")


def _drop_bundled_icu(binaries):
    kept = []
    for entry in binaries:
        name = os.path.basename(entry[0]).lower()
        if name.startswith(_DROPPED_ICU_PREFIXES) and name.endswith(".dll"):
            print(f"[spec] dropping bundled ICU library: {entry[0]}")
            continue
        kept.append(entry)
    return kept


a = Analysis(
    ["../main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

a.binaries = _drop_bundled_icu(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShortcutHUD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="../assets/app_icon.ico",
    version="../packaging/version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ShortcutHUD",
)
