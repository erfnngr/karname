# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('data', 'data'), ('assets', 'assets'), ('web', 'web')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc_data',
        'doctest',
        'xmlrpc',
        'test',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2',
        'PySide6.QtQml',
        'PySide6.QtQuick3D',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        'PySide6.QtCharts',
        'PySide6.QtGraphs',
        'PySide6.QtGraphsWidgets',
        'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtLocation',
        'PySide6.QtPositioning',
        'PySide6.QtSensors',
        'PySide6.QtBluetooth',
        'PySide6.QtSerialPort',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSql',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtStateMachine',
        'PySide6.QtTextToSpeech',
        'PySide6.QtTest',
        'PySide6.QtNfc',
        'PySide6.QtWebSockets',
        'PySide6.QtHttpServer',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtUiTools',
        'PySide6.QtXml',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
    ],
    noarchive=False,
    optimize=1,
)

# Trim unused QtWebEngine/QML/3D/multimedia/locale bloat and duplicate assets
# so Karname.exe stays compact without touching core runtime features.
_UNUSED_QT_DLL_PREFIXES = (
    'qt63d',
    'qt6quick3d',
    'qt6charts',
    'qt6graphs',
    'qt6datavisualization',
    'qt6multimedia',
    'qt6location',
    'qt6shadertools',
    'qt6quickcontrols2',
    'qt6quicktemplates2',
    'qt6quickdialogs2',
    'qt6quickparticles',
    'qt6quickeffects',
    'qt6spatialaudio',
    'qt6scxml',
    'qt6remoteobjects',
    'qt6labs',
    'qt6test',
    'qt6sql',
    'qt6sensors',
    'qt6bluetooth',
    'qt6serialport',
    'qt6websockets',
    'qt6httpserver',
    'qt6texttospeech',
    'qt6designer',
    'qt6help',
    'qt6uitools',
)
_UNUSED_PLUGIN_DIRS = (
    'pyside6/plugins/qmltooling/',
    'pyside6/plugins/qmlls/',
    'pyside6/plugins/renderers/',
    'pyside6/plugins/geometryloaders/',
    'pyside6/plugins/sceneparsers/',
    'pyside6/plugins/assetimporters/',
    'pyside6/plugins/multimedia/',
    'pyside6/plugins/position/',
    'pyside6/plugins/sensors/',
    'pyside6/plugins/sqldrivers/',
    'pyside6/plugins/texttospeech/',
    'pyside6/plugins/webview/',
    'pyside6/plugins/virtualkeyboard/',
    'pyside6/plugins/designer/',
    'pyside6/plugins/help/',
)


def _keep_bundle_entry(entry):
    dest = entry[0].replace('\\', '/').lower()
    if dest.startswith('pyside6/qml/'):
        return False
    if dest in {
        'web/react-design/ocean.png',
        'web/react-design/karname-watermark.png',
    }:
        return False
    if dest.endswith('qtwebengine_devtools_resources.pak'):
        return False
    if dest.endswith('v8_context_snapshot.debug.bin'):
        return False
    if '/qtwebengine_locales/' in dest:
        return dest.endswith('/en-us.pak') or dest.endswith('/fa.pak')
    if dest.startswith('pyside6/translations/') and dest.endswith('.qm'):
        return dest.endswith('_en.qm') or dest.endswith('_fa.qm')
    if any(dest.startswith(prefix) for prefix in _UNUSED_PLUGIN_DIRS):
        return False
    base = dest.rsplit('/', 1)[-1]
    if base.endswith('.dll') and any(base.startswith(p) for p in _UNUSED_QT_DLL_PREFIXES):
        return False
    return True


a.binaries = [item for item in a.binaries if _keep_bundle_entry(item)]
a.datas = [item for item in a.datas if _keep_bundle_entry(item)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Karname',
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
    icon=['assets/karname.ico'],
)
