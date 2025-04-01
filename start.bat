@echo off
echo 正在启动FlowmapCanvas...

REM 使用项目自带的Python环境
set PYTHON_PATH=env\Python\python.exe

REM 检查Python环境
if not exist "%PYTHON_PATH%" (
    echo 错误：找不到项目Python环境 %PYTHON_PATH%
    echo 请确保在正确路径下运行此脚本，并已安装项目环境。
    pause
    exit /b 1
)

echo 使用Python环境: %PYTHON_PATH%

"%PYTHON_PATH%" main.py
pause 