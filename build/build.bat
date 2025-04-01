@echo off
echo FlowmapCanvas 打包工具
echo =====================

REM 使用项目自带的Python环境
set PYTHON_PATH=..\env\Python\python.exe

REM 检查Python环境
if not exist "%PYTHON_PATH%" (
    echo 错误：找不到项目Python环境 %PYTHON_PATH%
    echo 请确保在正确路径下运行此脚本，并已安装项目环境。
    pause
    exit /b 1
)

echo 使用Python环境: %PYTHON_PATH%

REM 运行打包脚本
echo 开始打包过程...
"%PYTHON_PATH%" build_executable.py

if %ERRORLEVEL% NEQ 0 (
    echo 打包过程中出现错误，请查看上面的输出。
) else (
    echo 打包完成！
)

pause 