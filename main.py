import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
import os
from main_window import MainWindow
from localization import translator
from app_settings import app_settings
import ctypes

def get_application_path():
    """获取应用程序路径，处理PyInstaller打包后的特殊情况"""
    if getattr(sys, 'frozen', False):
        # 如果应用程序被打包
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是直接运行脚本
        application_path = os.path.dirname(os.path.abspath(__file__))
    return application_path

# Windows任务栏图标设置
def set_taskbar_icon(icon_path):
    try:
        if sys.platform == 'win32':
            # 设置Windows任务栏图标的AppUserModel ID
            app_id = "AlexWay.FlowmapCanvas.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            
            # 尝试使用Windows API直接设置任务栏图标
            if os.path.exists(icon_path):
                # LoadImage参数: hInst, name, type, cx, cy, fuLoad
                # LR_LOADFROMFILE = 0x0010, IMAGE_ICON = 1
                icon_handle = ctypes.windll.user32.LoadImageW(
                    0, icon_path, 1, 0, 0, 0x0010)
                if icon_handle:
                    print(f"成功加载任务栏图标: {icon_path}")
                    # 尝试设置为当前进程图标
                    ctypes.windll.user32.SendMessageW(
                        ctypes.windll.kernel32.GetConsoleWindow(),
                        0x0080, 0, icon_handle)  # 0x0080 = WM_SETICON
            else:
                print(f"任务栏图标设置失败: 找不到图标文件 {icon_path}")
    except Exception as e:
        print(f"设置任务栏图标时出错: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 设置应用程序图标 - 处理打包后的路径
    app_path = get_application_path()
    icon_path = os.path.join(app_path, 'FlowmapCanvas.ico')
    
    # 如果打包路径下没找到，尝试常规路径
    if not os.path.exists(icon_path):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FlowmapCanvas.ico')
    
    # 再次检查文件是否存在并打印路径以便调试
    if os.path.exists(icon_path):
        print(f"找到图标文件: {icon_path}")
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        
        # 设置任务栏图标
        set_taskbar_icon(icon_path)
    else:
        print(f"警告: 图标文件不存在: {icon_path}")
    
    # 加载应用设置
    app_settings.load_settings()
    
    # 加载样式表
    try:
        with open('style.qss', 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"加载样式表出错: {e}")
    
    # 创建并显示主窗口
    window = MainWindow()
    
    # 为主窗口也设置图标，确保所有窗口和任务栏都显示图标
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    
    window.show()
    
    # 开始应用程序事件循环
    sys.exit(app.exec_())