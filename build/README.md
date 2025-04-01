# FlowmapCanvas 打包指南

本文档提供了如何将FlowmapCanvas从Python源代码打包为独立可执行文件的详细说明。

## 打包前准备

确保您的系统满足以下要求：

1. 项目中已包含Python环境（位于`env/Python`目录）
2. 已安装所有必要的依赖项（参见`requirements.txt`）
3. 确保所有资源文件可用：
   - `flow_shader.glsl`
   - `background.png`
   - `style.qss`
   - `img/`目录下的所有图像文件

## 快速打包方法

**方法1: 使用命令行打包工具（推荐）**

直接双击运行`package_console.bat`文件，它会自动：
1. 使用项目中的Python环境（`env/Python/python.exe`）
2. 启动交互式命令行界面
3. 引导您完成打包过程
4. 创建最终的可执行文件

**方法2: 使用批处理脚本**

直接双击运行`build.bat`文件，它会使用默认配置进行打包：
1. 使用项目中的Python环境（`env/Python/python.exe`）
2. 自动安装必要的依赖项（包括PyInstaller）
3. 运行打包脚本
4. 创建最终的可执行文件

**方法3: 手动运行Python脚本**

1. 打开命令提示符或PowerShell
2. 运行命令：`env\Python\python.exe build_executable.py`

## 打包后的文件

打包完成后，您将在`dist/FlowmapCanvas/`目录下找到以下文件和目录：

```
FlowmapCanvas/
├── FlowmapCanvas.exe    # 主可执行文件
├── start.bat            # 启动批处理文件
├── flow_shader.glsl     # 着色器文件
├── background.png       # 默认背景图像
├── style.qss           # 样式表
├── app_settings.json    # 应用程序设置
├── img/                 # 图像资源目录
└── [其他PyInstaller生成的DLL和依赖文件]
```

## 分发方法

要分发您的应用程序，只需将整个`dist/FlowmapCanvas/`目录压缩为ZIP文件，然后分享给用户。用户只需解压缩并运行`start.bat`或直接运行`FlowmapCanvas.exe`即可启动程序。

## 故障排除

如果在打包过程中遇到问题：

1. **确保使用正确的Python环境**：
   ```
   打包工具应使用项目中的Python环境：env\Python\python.exe
   ```

2. **乱码问题**：如果命令行窗口显示乱码，可以尝试以下解决方案：
   - 在命令提示符中执行：`chcp 65001`（设置UTF-8编码）
   - 修改控制台属性，字体选择支持中文的字体（如"新宋体"或"Consolas"）
   - 打包工具已优化处理编码问题，应可正常显示

3. **缺少依赖项**：确保所有依赖项都已正确安装。
   ```
   env\Python\python.exe -m pip install -r requirements.txt
   ```

4. **找不到资源文件**：确保资源文件位于正确位置，或者修改打包脚本中的路径。

5. **PyInstaller错误**：如果遇到"系统找不到指定的文件"错误，请尝试手动安装PyInstaller：
   ```
   env\Python\python.exe -m pip install --upgrade pip
   env\Python\python.exe -m pip install pyinstaller
   ```

6. **运行时错误**：如果打包后的程序无法运行，尝试启用调试模式重新打包以获取更详细的调试信息。

## 自定义打包选项

您可以通过以下方式自定义打包选项：

1. **使用命令行工具**：运行`package_console.bat`，可以通过交互式界面进行配置。

2. **编辑脚本**：修改`build_executable.py`或`console_packager.py`文件来自定义打包参数。

可自定义的主要选项：
- **打包模式**：单文件(`--onefile`)或目录模式(`--onedir`)
- **控制台窗口**：是否显示控制台窗口
- **调试模式**：启用详细调试信息
- **自定义图标**：在`img`目录中放置`icon.ico`文件

## 技术说明

此打包解决方案使用PyInstaller，它通过以下方式工作：

1. 分析Python代码以找出所有必要的依赖项
2. 收集这些依赖项和资源文件
3. 创建一个包含Python解释器和所有依赖项的可执行文件或目录
4. 确保程序在没有安装Python的计算机上也能运行

PyInstaller不会将Python代码编译为本机代码，而是将其与Python解释器打包在一起。 