# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['/root/project/github/public-repository/ObtainHub/obtainhub/main.py'],
    pathex=['/root/project/github/public-repository/ObtainHub'],
    binaries=[],
    datas=[
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/config.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/state.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/logger.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/exceptions.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/github_client.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/asset_matcher.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/downloader.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/installer.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/core/self_updater.py', 'obtainhub/core'),
        ('/root/project/github/public-repository/ObtainHub/obtainhub/utils/helpers.py', 'obtainhub/utils'),
    ],
    hiddenimports=[
        'obtainhub.core.config',
        'obtainhub.core.state',
        'obtainhub.core.logger',
        'obtainhub.core.exceptions',
        'obtainhub.core.github_client',
        'obtainhub.core.asset_matcher',
        'obtainhub.core.downloader',
        'obtainhub.core.installer',
        'obtainhub.core.self_updater',
        'obtainhub.utils.helpers',
        'requests',
        'urllib3',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ohub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    icon='',
    onefile=True,
)
