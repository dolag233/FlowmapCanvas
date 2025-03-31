import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow
from localization import translator
from app_settings import app_settings

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
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
    window.show()
    
    # 开始应用程序事件循环
    sys.exit(app.exec_())