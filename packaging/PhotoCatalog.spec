# -*- mode: python ; coding: utf-8 -*-
"""
PhotoCatalog.spec — PyInstaller build recipe for the PhotoCatalog GUI.

Produces a --onedir build (folder with PhotoCatalog.exe plus dependencies)
that Inno Setup then wraps into a setup installer. Onedir startup is much
faster than onefile and makes debugging the shipped build easier.

Build from the project root:
    pyinstaller packaging/PhotoCatalog.spec --noconfirm --clean

Outputs:
    build/PhotoCatalog/           (intermediate)
    dist/PhotoCatalog/            (final folder to ship)
    dist/PhotoCatalog/PhotoCatalog.exe

The Images/ folder is bundled so the app can find the camera icon,
the Claude symbol, and the wireframe (future use).
"""
from pathlib import Path

# Paths are resolved relative to this spec file so builds work from any CWD.
SPEC_DIR = Path(SPECPATH).resolve()          # noqa: F821 - provided by PyInstaller
PROJECT_ROOT = SPEC_DIR.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
IMAGES_DIR = PROJECT_ROOT / "Images"
ICON_PATH = IMAGES_DIR / "photocatalog.ico"

block_cipher = None


a = Analysis(
    [str(SCRIPTS_DIR / "run_gui.py")],
    pathex=[str(SCRIPTS_DIR)],
    binaries=[],
    datas=[
        # (source, dest-folder-relative-to-app-root)
        (str(IMAGES_DIR), "Images"),
    ],
    # Face recognition is optional; keep it discoverable if the user later
    # installs the dependency alongside the packaged app. For now we simply
    # don't force-include it so the build stays lean.
    hiddenimports=[
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim Qt modules we don't use to cut ~40–60 MB from the build.
    excludes=[
        "PyQt6.Qt3DAnimation", "PyQt6.Qt3DCore", "PyQt6.Qt3DExtras",
        "PyQt6.Qt3DInput", "PyQt6.Qt3DLogic", "PyQt6.Qt3DRender",
        "PyQt6.QtBluetooth", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
        "PyQt6.QtDesigner", "PyQt6.QtHelp", "PyQt6.QtLocation",
        "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtNetworkAuth", "PyQt6.QtNfc", "PyQt6.QtOpenGL",
        "PyQt6.QtOpenGLWidgets", "PyQt6.QtPdf", "PyQt6.QtPdfWidgets",
        "PyQt6.QtPositioning", "PyQt6.QtQml", "PyQt6.QtQuick",
        "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets", "PyQt6.QtRemoteObjects",
        "PyQt6.QtScxml", "PyQt6.QtSensors", "PyQt6.QtSerialBus",
        "PyQt6.QtSerialPort", "PyQt6.QtSpatialAudio", "PyQt6.QtSql",
        "PyQt6.QtStateMachine", "PyQt6.QtSvg", "PyQt6.QtSvgWidgets",
        "PyQt6.QtTest", "PyQt6.QtTextToSpeech", "PyQt6.QtWebChannel",
        "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebSockets", "PyQt6.QtXml",
        # Other heavy modules we don't need
        "tkinter", "matplotlib", "numpy.testing", "scipy",
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
    [],
    exclude_binaries=True,
    name="PhotoCatalog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX compression breaks PyQt6 DLLs — leave off
    console=False,             # hide console window for a polished GUI feel
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PhotoCatalog",
)
