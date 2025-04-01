@echo off
echo 启动FlowmapCanvas打包工具(命令行)...
echo =================================

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

REM 设置控制台编码为UTF-8，避免中文乱码
chcp 65001 > nul

REM 运行命令行打包工具
"%PYTHON_PATH%" console_packager.py

pause 