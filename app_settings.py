"""
应用程序设置模块 - 管理应用程序的全局设置和主题

该模块负责：
1. 管理应用程序主题（深色/浅色）
2. 生成样式表
3. 提供全局设置访问
"""

from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QApplication
import json
import os

class AppSettings:
    """应用程序设置管理器"""
    
    def __init__(self):
        # 初始化默认值
        self.is_dark_mode = self._detect_system_theme()
        self.high_resolution_mode = False
        self.texture_size = (1024, 1024)
        self.seamless_mode = False
        self.preview_repeat = False
        
    def _detect_system_theme(self):
        """检测系统是否为深色模式"""
        palette = QApplication.palette()
        return palette.color(QPalette.Window).lightness() < 128
        
    def toggle_theme(self):
        """切换深色/浅色模式"""
        self.is_dark_mode = not self.is_dark_mode
        return self.is_dark_mode
        
    def toggle_high_res_mode(self, enabled):
        """切换高精度模式"""
        self.high_resolution_mode = enabled
        self.texture_size = (2048, 2048) if enabled else (1024, 1024)
        return self.texture_size
    
    def set_seamless_mode(self, enabled):
        """设置无缝模式"""
        self.seamless_mode = enabled
        
    def set_preview_repeat(self, enabled):
        """设置预览重复模式"""
        self.preview_repeat = enabled
        
    def get_theme_stylesheet(self):
        """生成主题样式表"""
        if self.is_dark_mode:
            # 深色模式样式
            background_color = "#2D2D30"
            text_color = "#FFFFFF"
            control_background = "#3E3E42"
            highlight_color = "#007ACC"
            border_color = "#555555"
            menu_background = "#2D2D30"
            menu_selected = "#3E3E42"
            shortcut_color = "#888888"
        else:
            # 浅色模式样式
            background_color = "#F5F5F5"
            text_color = "#333333"
            control_background = "#FFFFFF"
            highlight_color = "#007ACC"
            border_color = "#DDDDDD"
            menu_background = "#F5F5F5"
            menu_selected = "#E5E5E5"
            shortcut_color = "#999999"
            
        # 构建样式表
        qss = f"""
        QMainWindow, QDialog, QDockWidget, QMessageBox {{
            background-color: {background_color};
            color: {text_color};
        }}
        
        QLabel {{
            color: {text_color};
        }}
        
        QMenuBar {{
            background-color: {menu_background};
            color: {text_color};
        }}
        
        QMenuBar::item {{
            background-color: transparent;
        }}
        
        QMenuBar::item:selected {{
            background-color: {menu_selected};
        }}
        
        QMenu {{
            background-color: {menu_background};
            color: {text_color};
            border: 1px solid {border_color};
        }}
        
        QMenu::item:selected {{
            background-color: {menu_selected};
        }}
        
        QPushButton {{
            background-color: {control_background};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 5px;
            border-radius: 2px;
        }}
        
        QPushButton:hover {{
            background-color: {highlight_color};
            color: white;
        }}
        
        QGroupBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            margin-top: 0.5em;
            padding-top: 0.5em;
            color: {text_color};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }}
        
        QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {control_background};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 1px 18px 1px 3px;
            border-radius: 2px;
        }}
        
        QSlider::groove:horizontal {{
            background: {control_background};
            height: 8px;
            border-radius: 4px;
        }}
        
        QSlider::handle:horizontal {{
            background: {highlight_color};
            width: 16px;
            margin: -4px 0;
            border-radius: 8px;
        }}
        
        QCheckBox {{
            color: {text_color};
        }}
        
        QCheckBox::indicator {{
            width: 13px;
            height: 13px;
        }}
        
        QStatusBar {{
            background-color: {background_color};
            color: {text_color};
        }}
        """
        
        return qss, shortcut_color
        
    def load_settings(self):
        """从配置文件加载设置"""
        try:
            if os.path.exists("app_settings.json"):
                with open("app_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.is_dark_mode = settings.get("is_dark_mode", self.is_dark_mode)
                    self.high_resolution_mode = settings.get("high_resolution_mode", self.high_resolution_mode)
                    self.seamless_mode = settings.get("seamless_mode", self.seamless_mode)
                    self.preview_repeat = settings.get("preview_repeat", self.preview_repeat)
                    
                    if self.high_resolution_mode:
                        self.texture_size = (2048, 2048)
        except Exception as e:
            print(f"加载设置出错: {e}")
    
    def save_settings(self):
        """保存设置到配置文件"""
        try:
            settings = {
                "is_dark_mode": self.is_dark_mode,
                "high_resolution_mode": self.high_resolution_mode,
                "seamless_mode": self.seamless_mode,
                "preview_repeat": self.preview_repeat
            }
            
            with open("app_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置出错: {e}")
            
# 创建全局设置实例
app_settings = AppSettings() 