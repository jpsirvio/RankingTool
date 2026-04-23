# =============================================================================
# RankingTool.spec — PyInstaller build specification
#
# Usage (run from the project root on Windows):
#   pyinstaller RankingTool.spec
#
# Output:
#   dist\RankingTool\RankingTool.exe   (folder-based distribution)
#
# The spec produces a one-FOLDER build (not a single .exe) because
# PyInstaller single-file builds are significantly slower to start as they
# must unpack to a temp directory on every launch.  Distribute the entire
# dist\RankingTool\ folder — users run RankingTool.exe inside it.
# =============================================================================

import sys
from pathlib import Path

block_cipher = None

# Project root is the directory that contains this spec file
ROOT = Path(SPECPATH)  # noqa: F821  (SPECPATH is injected by PyInstaller)

a = Analysis(
    # Entry point
    [str(ROOT / 'qt_app.py')],

    # Additional source paths (ranking_engine must be importable)
    pathex=[str(ROOT)],

    # Binary dependencies discovered automatically; add extras here if needed
    binaries=[],

    # Non-Python data files to bundle (projects folder excluded — it is
    # created at runtime next to the .exe by the app itself)
    datas=[],

    # Hidden imports that PyInstaller's static analysis may miss
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.sip',
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],

    # Modules to exclude to keep the bundle smaller
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'test',
        'unittest',
    ],

    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],

    # Do NOT include everything in the .exe itself (one-folder mode)
    exclude_binaries=True,

    name='RankingTool',

    # Set to True to suppress the console window on Windows.
    # Keep False during development so you can see error output.
    console=False,

    # Windows-specific metadata
    version_file=None,   # create a version_file.txt if you need file properties
    icon=None,           # replace with 'icon.ico' if you have one

    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,            # compress with UPX if available (reduces size ~30%)
    upx_exclude=[],
    runtime_tmpdir=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RankingTool',   # output folder name under dist\
)
