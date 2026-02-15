# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('rammap.ico', '.')],
    hiddenimports=['psutil', 'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused standard library modules
        'unittest', 'test', 'tests',
        'distutils', 'setuptools', 'pkg_resources',
        'asyncio', 'concurrent', 'multiprocessing',
        'xml', 'xmlrpc', 'pydoc', 'doctest',
        'email', 'html', 'http', 'urllib',
        'sqlite3', 'bz2', 'lzma',
        # Exclude tkinter modules you're not using
        # NOTE: tkinter.commondialog removed because messagebox depends on it
        'tkinter.dnd', 'tkinter.colorchooser',
        'tkinter.filedialog', 'tkinter.font', 'tkinter.scrolledtext',
        'tkinter.simpledialog', 'tkinter.tix',
        # Exclude other unnecessary modules
        'matplotlib', 'numpy', 'pandas',
        'IPython', 'jupyter', 'notebook',
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
    name='windows-rammap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Remove debug symbols to reduce size
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # This prevents the console window from appearing
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,  # Request admin privileges in the manifest
    icon='rammap.ico',  # Application icon
)
