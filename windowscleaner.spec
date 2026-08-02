# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — build with: pyinstaller windowscleaner.spec"""

block_cipher = None

# Keep the frozen EXE lean: do NOT collect_all("rich") (pulls IPython/numpy).
# GUI path only needs tkinter + stdlib; CLI optionally uses rich/click.

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "windowscleaner",
        "windowscleaner.ui.gui",
        "windowscleaner.ui.cli",
        "windowscleaner.modules",
        "windowscleaner.modules.temp_files",
        "windowscleaner.modules.recycle_bin",
        "windowscleaner.modules.browser_caches",
        "windowscleaner.modules.gpu_caches",
        "windowscleaner.modules.caches",
        "windowscleaner.modules.logs",
        "windowscleaner.modules.tracking",
        "windowscleaner.modules.network_cache",
        "windowscleaner.modules.privacy",
        "windowscleaner.modules.telemetry_services",
        "windowscleaner.modules.bloatware",
        "windowscleaner.modules.item_info",
        "click",
        "rich",
        "rich.console",
        "rich.table",
        "rich.panel",
        "rich.progress",
        "rich.text",
        "rich.box",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "psutil",
        "IPython",
        "ipython",
        "numpy",
        "pandas",
        "pytest",
        "jedi",
        "parso",
        "matplotlib",
        "PIL",
        "Pillow",
        "scipy",
        "torch",
        "tensorflow",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WindowsCleaner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
