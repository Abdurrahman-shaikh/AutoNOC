# AutoNOC.spec
# PyInstaller spec file — controls exactly what gets bundled into the EXE.
#
# Why a spec file instead of command line flags?
# - More reliable, version-controlled, reproducible builds
# - Handles hidden imports that PyInstaller misses automatically
# - Correctly bundles config/ as a data folder
# - Sets the EXE name, icon, and console mode in one place
#
# To rebuild manually on a Windows machine:
#   pip install pyinstaller
#   pyinstaller AutoNOC.spec

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hiddenimports=[
    # pandas internals
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.timedeltas',
    'pandas._libs.skiplist',
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    # openpyxl internals
    'openpyxl.cell._writer',
    'et_xmlfile',
    # selenium internals
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.support.expected_conditions',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.common.by',
],

block_cipher = None

# Collect all hidden imports that PyInstaller won't find automatically.
# These are packages that are imported dynamically at runtime.
hidden_imports = (
    collect_submodules('selenium')        +
    collect_submodules('webdriver_manager') +
    collect_submodules('pandas')          +
    collect_submodules('openpyxl')        +
    collect_submodules('pkg_resources')   +
    [
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'webdriver_manager.chrome',
        'openpyxl.styles',
        'openpyxl.utils',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.skiplist',
    ]
)

# Data files to bundle INSIDE the EXE (read-only defaults).
# config/config.json is bundled as a fallback default —
# on first run the EXE copies it next to itself so the user can edit it.
# src/ is bundled so Python can import the modules from inside the EXE.
datas = [
    ('config',            'config'),   # bundles config/config.json
    ('src',               'src'),      # bundles all src/*.py modules
    ('generate_dummy_csv.py', '.'),    # bundled for --test mode
]

# Also collect any data files that pandas/openpyxl need internally
datas += collect_data_files('openpyxl')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AutoNOC',               # output filename: AutoNOC.exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                     # compress with UPX to reduce EXE size
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,                 # keep console window — needed for menus/input
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
