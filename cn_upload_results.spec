# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for building the standalone CN Upload Results executable.

Generates a single-file GUI executable that bundles the Python runtime, dependencies,
and the required `.env` configuration file so the end user only needs to double-click
the resulting `CNUploadResults.exe`.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

_spec_source = globals().get("__file__") or os.environ.get("PYI_SPEC_PATH")
if _spec_source:
    project_root = Path(_spec_source).resolve().parent
else:
    project_root = Path.cwd().resolve()
env_file = project_root / ".env"
datas = [(str(env_file), ".")] if env_file.is_file() else []

hidden_imports: list[str] = []
hidden_imports += collect_submodules("supabase")
hidden_imports += collect_submodules("postgrest")
hidden_imports += collect_submodules("httpx")


a = Analysis(
    ["src/cn_upload_results/__main__.py"],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CNUploadResults",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
