# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

hiddenimports = [
    "qasync",
]

a = Analysis(
    ["packaging/pyinstaller_entry.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/zhoutomo_client/resources", "zhoutomo_client/resources"),
        (
            "src/zhoutomo_client/processing/legacy/*.mat",
            "zhoutomo_client/processing/legacy",
        ),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="ZhouTomo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="src/zhoutomo_client/resources/icons/logo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ZhouTomo",
)
