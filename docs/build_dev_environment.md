## Build Development Environment

This guide explains how to set up a full development environment from source and how to build the app.

1) Python (full installation)
- Install a complete Python 3.9+ environment.
- The project expects the interpreter at `env/Python/python.exe` relative to the project root. Install Python into that folder or ensure your full Python lives there.

2) Python modules
Run using the interpreter under `env/Python`:
```
env\Python\python.exe -m pip install --upgrade pip
env\Python\python.exe -m pip install -r requirements.txt
```

3) FBX2glTF converter
- Download the FBX2glTF binary from GitHub Releases.
- Place the binary in the project root (same level as `main.py`).
- The filename must be exactly `FBX2glTF` (Windows: `FBX2glTF.exe`). No environment variable or PATH required.

4) Run and build
- Run from source:
```
env\Python\python.exe main.py
```
- Build (PyInstaller):
```
env\Python\python.exe build/build_executable.py
```
The build script copies required resources and, if present, the `FBX2glTF` binary into `dist/FlowmapCanvas/`.

---

## 构建开发环境

本指南说明如何从源码搭建完整的开发环境并进行打包构建。

1) Python（完整安装）
- 需要安装完整的 Python 3.9+ 环境。
- 项目约定解释器位于项目根目录下的 `env/Python/python.exe`，请将完整的 Python 安装到该目录。

2) 安装依赖
使用 `env/Python` 下的解释器执行：
```
env\Python\python.exe -m pip install --upgrade pip
env\Python\python.exe -m pip install -r requirements.txt
```

3) FBX2glTF 转换器
- 从 GitHub Releases 下载 FBX2glTF 可执行文件。
- 将可执行文件放到项目根目录（与 `main.py` 同级）。
- 文件名必须严格为 `FBX2glTF`（Windows 为 `FBX2glTF.exe`）。无需设置环境变量或 PATH。

4) 运行与打包
- 从源码运行：
```
env\Python\python.exe main.py
```
- 打包（PyInstaller）：
```
env\Python\python.exe build/build_executable.py
```
打包脚本会复制必要的资源，如果检测到 `FBX2glTF`，也会将其复制到 `dist/FlowmapCanvas/`。


