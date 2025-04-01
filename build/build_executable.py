import os
import sys
import shutil
import subprocess
import platform
import time

def ensure_path_exists(path):
    """确保路径存在，如果不存在则创建"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")

def copy_resources(dist_dir):
    """复制所需资源文件到打包目录"""
    resources = [
        "flow_shader.glsl",
        "background.png",
        "style.qss",
        "app_settings.json"
    ]
    
    # 可能需要创建的子目录
    ensure_path_exists(os.path.join(dist_dir, "img"))
    
    # 复制根目录资源
    for res in resources:
        if os.path.exists(res):
            shutil.copy2(res, os.path.join(dist_dir, res))
            print(f"已复制: {res}")
        else:
            print(f"警告: 找不到资源 {res}")
    
    # 复制img目录下的所有文件
    if os.path.exists("img"):
        for file in os.listdir("img"):
            src_path = os.path.join("img", file)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, os.path.join(dist_dir, "img", file))
                print(f"已复制: {src_path}")

def check_pyinstaller(python_path):
    """检查PyInstaller是否已安装，如果没有则安装"""
    try:
        # 尝试导入PyInstaller
        result = subprocess.run(
            [python_path, "-c", "import PyInstaller; print(PyInstaller.__version__)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print(f"PyInstaller已安装，版本: {result.stdout.strip()}")
            return True
        else:
            print("PyInstaller未安装，正在安装...")
            # 安装PyInstaller
            subprocess.check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.check_call([python_path, "-m", "pip", "install", "pyinstaller"])
            print("PyInstaller安装成功")
            return True
    except Exception as e:
        print(f"PyInstaller检查或安装失败: {e}")
        return False

def get_hidden_imports():
    """获取可能需要手动指定的隐藏导入"""
    return [
        "PyQt5.QtPrintSupport",
        "numpy.random",
        "OpenGL.platform.win32",
        "OpenGL.arrays.ctypesarrays",
        "OpenGL.arrays.numpymodule",
        "OpenGL.converters",
        "OpenGL.arrays.ctypespointers"
    ]

def main():
    # 切换到项目根目录
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 获取项目根目录
    project_root = os.getcwd()
    print(f"项目根目录: {project_root}")
    
    # 设置Python解释器路径
    python_path = os.path.join(project_root, "env", "Python", "python.exe")
    print(f"Python路径: {python_path}")
    
    # 检查Python解释器是否存在
    if not os.path.exists(python_path):
        print(f"错误: 找不到Python解释器 {python_path}")
        print("请确保项目包含正确的Python环境路径。")
        return 1
    
    # 检查PyInstaller
    if not check_pyinstaller(python_path):
        print("错误: 无法安装或验证PyInstaller，请尝试手动安装。")
        print(f"命令: {python_path} -m pip install pyinstaller")
        return 1
    
    # 准备PyInstaller命令行参数
    app_name = "FlowmapCanvas"
    main_script = "main.py"
    icon_path = "img/icon.ico" if os.path.exists("img/icon.ico") else ""
    
    # 构建命令列表
    cmd = [
        python_path, "-m", "PyInstaller",
        "--name", app_name,
        "--onedir",  # 创建目录而不是单文件
        "--windowed",  # 不显示控制台窗口
        "--noconfirm",  # 覆盖输出目录
        "--clean",  # 清理临时文件
    ]
    
    # 添加图标
    if icon_path:
        cmd.extend(["--icon", icon_path])
    
    # 添加隐藏导入
    for hidden_import in get_hidden_imports():
        cmd.extend(["--hidden-import", hidden_import])
    
    # 添加必要的数据文件
    sep = ";" if platform.system() == "Windows" else ":"
    data_files = [
        "flow_shader.glsl",
        "background.png",
        "style.qss",
        "app_settings.json"
    ]
    
    for data_file in data_files:
        if os.path.exists(data_file):
            cmd.extend(["--add-data", f"{data_file}{sep}{data_file}"])
    
    # 添加图片文件夹
    if os.path.exists("img"):
        cmd.extend(["--add-data", f"img{sep}img"])
    
    # 添加主脚本
    cmd.append(main_script)
    
    # 输出命令
    print("执行 PyInstaller 命令:")
    print(" ".join(cmd))
    
    # 设置环境变量以处理输出编码问题
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"
    
    # 如果是Windows，尝试设置控制台编码
    if platform.system() == "Windows":
        try:
            subprocess.run(["chcp", "65001"], check=False)  # 设置代码页为UTF-8
        except:
            pass
    
    # 执行打包命令
    try:
        # 使用subprocess.run而不是check_call可以更好地处理错误
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=my_env
        )
        
        # 输出结果
        print(result.stdout)
        
        if result.returncode == 0:
            print(f"\n打包成功! 可执行文件已创建在 'dist/{app_name}/' 目录中")
            
            # 复制额外资源
            dist_dir = os.path.join("dist", app_name)
            copy_resources(dist_dir)
            
            # 创建启动脚本
            with open(os.path.join(dist_dir, "start.bat"), "w") as f:
                f.write(f"@echo off\necho 正在启动{app_name}...\nstart {app_name}.exe\n")
            
            print("已创建启动脚本: start.bat")
            print(f"\n所有文件已准备就绪，可以通过运行 'dist/{app_name}/start.bat' 启动程序")
            return 0
        else:
            print(f"\n打包失败，返回代码: {result.returncode}")
            print("可能的原因:")
            print("1. PyInstaller未正确安装")
            print("2. 找不到所需的资源文件")
            print("3. Python环境存在问题")
            print("\n尝试解决方案:")
            print(f"  - 手动运行: {python_path} -m pip install --upgrade pyinstaller")
            print("  - 检查资源文件是否存在")
            return 1
            
    except FileNotFoundError as e:
        print(f"\n错误: 找不到文件 - {e}")
        print("请确保Python路径正确，并已安装PyInstaller")
        return 1
    except Exception as e:
        print(f"\n打包过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        # 如果是Windows，尝试提前设置控制台编码
        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)  # 65001 是 UTF-8 的代码页
            except:
                pass
        
        # 设置环境变量
        os.environ["PYTHONIOENCODING"] = "utf-8"
        
        # 执行主程序
        exit_code = main()
        print("\n按 Enter 键退出...")
        input()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n打包过程被用户中断。")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n按 Enter 键退出...")
        input()
        sys.exit(1) 