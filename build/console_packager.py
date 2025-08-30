"""
FlowmapCanvas 打包工具 - 命令行版本
提供命令行界面进行应用程序打包，不依赖GUI库
"""

import os
import sys
import shutil
import subprocess
import platform
import time
from pathlib import Path

# 是否启用颜色输出（Windows可能不支持）
ENABLE_COLOR = not (platform.system() == "Windows")

def clear_screen():
    """清除控制台屏幕"""
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

def print_header():
    """打印标题栏"""
    clear_screen()
    print("=" * 70)
    print("                       FlowmapCanvas 打包工具 v1.0")
    print("=" * 70)
    print()

def get_project_root():
    """获取项目根目录"""
    # 当前脚本所在目录的上级目录
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def print_color(text, color_code):
    """打印彩色文本"""
    # Windows 控制台下可能不支持ANSI颜色码
    if ENABLE_COLOR:
        # 颜色码: 31(红) 32(绿) 33(黄) 34(蓝) 35(紫) 36(青) 37(白)
        print(f"\033[{color_code}m{text}\033[0m")
    else:
        # Windows下不使用颜色
        print(text)

def print_success(text):
    """打印成功消息"""
    if ENABLE_COLOR:
        print_color(text, 32)  # 绿色
    else:
        print(f"[成功] {text}")

def print_error(text):
    """打印错误消息"""
    if ENABLE_COLOR:
        print_color(text, 31)  # 红色
    else:
        print(f"[错误] {text}")

def print_warning(text):
    """打印警告消息"""
    if ENABLE_COLOR:
        print_color(text, 33)  # 黄色
    else:
        print(f"[警告] {text}")

def print_log(message, level="INFO"):
    """打印带时间戳的日志"""
    timestamp = time.strftime("%H:%M:%S")
    
    if level == "INFO":
        print(f"[{timestamp}] {message}")
    elif level == "ERROR":
        if ENABLE_COLOR:
            print_error(f"[{timestamp}] ERROR: {message}")
        else:
            print(f"[{timestamp}] [错误] {message}")
    elif level == "WARNING":
        if ENABLE_COLOR:
            print_warning(f"[{timestamp}] WARNING: {message}")
        else:
            print(f"[{timestamp}] [警告] {message}")
    elif level == "SUCCESS":
        if ENABLE_COLOR:
            print_success(f"[{timestamp}] SUCCESS: {message}")
        else:
            print(f"[{timestamp}] [成功] {message}")

def check_resources(project_root):
    """检查必要的资源文件是否存在"""
    resources_to_check = [
        "flow_shader.glsl",
        "preview_shader.glsl",
        "background.png",
        "style.qss",
        "img",
        "main.py",
        "requirements.txt"
    ]
    
    print_log("检查资源文件...")
    all_found = True
    missing = []
    
    for res in resources_to_check:
        res_path = os.path.join(project_root, res)
        exists = os.path.exists(res_path)
        
        if exists:
            print_log(f"√ {res}")
        else:
            print_warning(f"× {res} - 找不到此资源")
            all_found = False
            missing.append(res)
    
    if all_found:
        print_success("\n所有资源文件都已找到！")
        return True
    else:
        print_error(f"\n缺少资源文件: {', '.join(missing)}")
        print_warning("警告: 缺少资源文件可能会导致打包失败或程序运行异常。")
        
        while True:
            choice = input("\n是否仍要继续? (y/n): ").strip().lower()
            if choice in ('y', 'yes'):
                return True
            elif choice in ('n', 'no'):
                return False
            else:
                print("无效选择，请输入 'y' 或 'n'")

def get_user_options():
    """获取用户配置选项"""
    options = {}
    
    # 应用名称
    options['app_name'] = "FlowmapCanvas"
    name = input(f"应用名称 [{options['app_name']}]: ").strip()
    if name:
        options['app_name'] = name
    
    # 单文件模式
    while True:
        onefile = input("是否打包为单个可执行文件? (y/n) [n]: ").strip().lower()
        if onefile in ('y', 'yes'):
            options['onefile'] = True
            break
        elif onefile in ('', 'n', 'no'):
            options['onefile'] = False
            break
        else:
            print("无效选择，请输入 'y' 或 'n'")
    
    # 是否显示控制台
    while True:
        console = input("是否显示控制台窗口? (y/n) [n]: ").strip().lower()
        if console in ('y', 'yes'):
            options['console'] = True
            break
        elif console in ('', 'n', 'no'):
            options['console'] = False
            break
        else:
            print("无效选择，请输入 'y' 或 'n'")
    
    # 调试模式
    while True:
        debug = input("是否启用调试模式? (y/n) [n]: ").strip().lower()
        if debug in ('y', 'yes'):
            options['debug'] = True
            break
        elif debug in ('', 'n', 'no'):
            options['debug'] = False
            break
        else:
            print("无效选择，请输入 'y' 或 'n'")
    
    return options

def copy_resources(dist_dir, project_root):
    """复制资源文件到打包目录"""
    resources = [
        "flow_shader.glsl",
        "background.png",
        "style.qss",
        "app_settings.json"
    ]
    
    # 确保目录存在
    img_dir = os.path.join(dist_dir, "img")
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
    
    # 复制根目录资源
    for res in resources:
        src_path = os.path.join(project_root, res)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(dist_dir, res))
            print_log(f"已复制: {res}")
        else:
            print_warning(f"警告: 找不到资源 {res}")
    
    # 复制img目录下的所有文件
    img_src_dir = os.path.join(project_root, "img")
    if os.path.exists(img_src_dir):
        for file in os.listdir(img_src_dir):
            src_path = os.path.join(img_src_dir, file)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, os.path.join(img_dir, file))
                print_log(f"已复制: img/{file}")

def get_hidden_imports():
    """获取需要手动指定的隐藏导入"""
    return [
        "PyQt5.QtPrintSupport",
        "numpy.random",
        "OpenGL.platform.win32",
        "OpenGL.arrays.ctypesarrays",
        "OpenGL.arrays.numpymodule",
        "OpenGL.converters",
        "OpenGL.arrays.ctypespointers"
    ]

def install_pyinstaller(python_path):
    """安装PyInstaller"""
    print_log("正在安装PyInstaller...")
    
    try:
        # 确保pip是最新的
        subprocess.check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
        # 安装PyInstaller
        subprocess.check_call([python_path, "-m", "pip", "install", "pyinstaller"])
        print_success("PyInstaller安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"安装PyInstaller失败: {e}")
        return False

def build_package(options, project_root):
    """构建打包命令并执行"""
    # Python解释器路径
    python_path = os.path.join(project_root, "env", "Python", "python.exe")
    
    # 验证Python路径
    if not os.path.exists(python_path):
        print_error(f"Python解释器不存在: {python_path}")
        return False
    
    # 检查PyInstaller是否安装
    try:
        # 检查PyInstaller是否可用
        check_cmd = [python_path, "-c", "import PyInstaller"]
        subprocess.check_call(check_cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print_warning("未检测到PyInstaller，正在尝试安装...")
        if not install_pyinstaller(python_path):
            return False
    
    # 准备PyInstaller命令行参数
    cmd = [
        python_path, "-m", "PyInstaller",
        "--name", options['app_name'],
        "--clean",
        "--noconfirm",
    ]
    
    # 单文件/目录选项
    if options['onefile']:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # 控制台窗口选项
    if not options['console']:
        cmd.append("--windowed")
    
    # 调试选项
    if options['debug']:
        cmd.append("--debug=all")
    
    # 输出目录
    dist_path = os.path.join(project_root, "dist")
    cmd.extend(["--distpath", dist_path])
    
    # 图标
    icon_path = os.path.join(project_root, "img", "icon.ico")
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
    
    # 添加必要的数据文件
    sep = ";" if platform.system() == "Windows" else ":"
    data_files = [
        "flow_shader.glsl",
        "background.png",
        "style.qss",
        "app_settings.json"
    ]
    
    for data_file in data_files:
        file_path = os.path.join(project_root, data_file)
        if os.path.exists(file_path):
            cmd.extend(["--add-data", f"{file_path}{sep}{data_file}"])
    
    # 添加图片文件夹
    img_dir = os.path.join(project_root, "img")
    if os.path.exists(img_dir):
        cmd.extend(["--add-data", f"{img_dir}{sep}img"])
    
    # 添加隐藏导入
    for hidden_import in get_hidden_imports():
        cmd.extend(["--hidden-import", hidden_import])
    
    # 添加主脚本
    cmd.append(os.path.join(project_root, "main.py"))
    
    # 显示命令
    print_log("执行PyInstaller命令:")
    print(" ".join(cmd))
    print()
    
    # 设置环境变量PYTHONIOENCODING以处理输出编码问题
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"
    
    # 执行命令
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=project_root,
            env=my_env
        )
        
        # 显示输出
        for line in process.stdout:
            print(line.strip())
        
        # 等待完成
        process.wait()
        
        if process.returncode == 0:
            print_success("\n打包成功!")
            
            # 定位输出目录
            app_dir = os.path.join(dist_path, options['app_name'])
            if not os.path.exists(app_dir) and options['onefile']:
                app_dir = dist_path
            
            # 创建启动脚本
            if not options['onefile']:
                bat_path = os.path.join(app_dir, "start.bat")
                with open(bat_path, "w") as f:
                    f.write(f"@echo off\necho 正在启动 {options['app_name']}...\nstart {options['app_name']}.exe\n")
                print_log(f"创建启动脚本: {bat_path}", "SUCCESS")
            
            print_success(f"\n应用程序已打包到: {app_dir}")
            return True
        else:
            print_error("\n打包失败，请检查上述错误信息。")
            return False
    except FileNotFoundError as e:
        print_error(f"\n找不到文件: {e}")
        print_error("请确保PyInstaller正确安装，或尝试手动运行以下命令:")
        print(f"{python_path} -m pip install pyinstaller")
        return False
    except Exception as e:
        print_error(f"\n执行命令时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_header()
    project_root = get_project_root()
    
    print(f"项目根目录: {project_root}")
    python_path = os.path.join(project_root, "env", "Python", "python.exe")
    print(f"Python环境: {python_path}")
    print()
    
    # 检查Python环境
    if not os.path.exists(python_path):
        print_error(f"找不到Python环境: {python_path}")
        print_error("请确保项目包含正确的Python环境路径。")
        input("\n按 Enter 键退出...")
        return 1
    
    # 检查资源
    if not check_resources(project_root):
        input("\n按 Enter 键退出...")
        return 1
    
    print("\n" + "=" * 70)
    print("配置打包选项")
    print("=" * 70)
    
    # 获取用户选项
    options = get_user_options()
    
    print("\n" + "=" * 70)
    print("开始打包过程")
    print("=" * 70 + "\n")
    
    # 构建并执行
    success = build_package(options, project_root)
    
    if success:
        print_success("\n打包已成功完成！")
    else:
        print_error("\n打包过程中出现错误。")
    
    input("\n按 Enter 键退出...")
    return 0 if success else 1

if __name__ == "__main__":
    try:
        # 设置控制台输出编码
        if platform.system() == "Windows":
            # 尝试设置控制台编码为UTF-8
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)  # 65001 是 UTF-8 的代码页
            except:
                pass
            
            # 设置环境变量
            os.environ["PYTHONIOENCODING"] = "utf-8"
        
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n打包过程被用户中断。")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按 Enter 键退出...")
        sys.exit(1) 