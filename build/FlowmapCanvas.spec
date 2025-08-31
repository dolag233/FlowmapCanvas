# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\Repositories\\FlowmapCanvas\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('E:\\Repositories\\FlowmapCanvas\\shaders/flow_shader.glsl', 'shaders/flow_shader.glsl'), ('E:\\Repositories\\FlowmapCanvas\\shaders/preview_shader.glsl', 'shaders/preview_shader.glsl'), ('E:\\Repositories\\FlowmapCanvas\\shaders/overlay_shader.glsl', 'shaders/overlay_shader.glsl'), ('E:\\Repositories\\FlowmapCanvas\\shaders/uv_wire_vs.glsl', 'shaders/uv_wire_vs.glsl'), ('E:\\Repositories\\FlowmapCanvas\\shaders/uv_wire_ps.glsl', 'shaders/uv_wire_ps.glsl'), ('E:\\Repositories\\FlowmapCanvas\\background.png', 'background.png'), ('E:\\Repositories\\FlowmapCanvas\\style.qss', 'style.qss'), ('E:\\Repositories\\FlowmapCanvas\\app_settings.json', 'app_settings.json'), ('E:\\Repositories\\FlowmapCanvas\\FlowmapCanvas.ico', 'FlowmapCanvas.ico')],
    hiddenimports=['PyQt5.QtPrintSupport', 'numpy.random', 'OpenGL.platform.win32', 'OpenGL.arrays.ctypesarrays', 'OpenGL.arrays.numpymodule', 'OpenGL.converters', 'OpenGL.arrays.ctypespointers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FlowmapCanvas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:\\Repositories\\FlowmapCanvas\\FlowmapCanvas.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FlowmapCanvas',
)
