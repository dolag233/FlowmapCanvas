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
        self._is_dark_mode = self._detect_system_theme()
        self._high_resolution_mode = False
        self._texture_size = (1024, 1024)
        self._seamless_mode = False
        self._preview_repeat = False
        self._invert_r_channel = False
        self._invert_g_channel = False
        
    @property
    def is_dark_mode(self):
        return self._is_dark_mode
        
    @property
    def high_resolution_mode(self):
        return self._high_resolution_mode
        
    @property
    def texture_size(self):
        return self._texture_size
        
    @property
    def seamless_mode(self):
        return self._seamless_mode
        
    @property
    def preview_repeat(self):
        return self._preview_repeat
        
    @property
    def invert_r_channel(self):
        return self._invert_r_channel
        
    @property
    def invert_g_channel(self):
        return self._invert_g_channel
        
    def _detect_system_theme(self):
        """检测系统是否为深色模式"""
        palette = QApplication.palette()
        return palette.color(QPalette.Window).lightness() < 128
        
    def toggle_theme(self):
        """切换深色/浅色模式"""
        self._is_dark_mode = not self._is_dark_mode
        return self._is_dark_mode
        
    def toggle_high_res_mode(self, enabled):
        """切换高精度模式"""
        self._high_resolution_mode = enabled
        self._texture_size = (2048, 2048) if enabled else (1024, 1024)
        return self._texture_size
    
    def set_seamless_mode(self, enabled):
        """设置无缝模式"""
        self._seamless_mode = enabled
        
    def set_preview_repeat(self, enabled):
        """设置预览重复模式"""
        self._preview_repeat = enabled
        
    def set_invert_r_channel(self, enabled):
        """设置R通道反转状态"""
        self._invert_r_channel = enabled
        
    def set_invert_g_channel(self, enabled):
        """设置G通道反转状态"""
        self._invert_g_channel = enabled
        
    def get_theme_stylesheet(self):
        """生成主题样式表"""
        if self._is_dark_mode:
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
                    # 使用 get 方法提供默认值
                    self._is_dark_mode = settings.get("is_dark_mode", self._is_dark_mode)
                    self._high_resolution_mode = settings.get("high_resolution_mode", self._high_resolution_mode)
                    self._seamless_mode = settings.get("seamless_mode", self._seamless_mode)
                    self._preview_repeat = settings.get("preview_repeat", self._preview_repeat)
                    self._invert_r_channel = settings.get("invert_r_channel", self._invert_r_channel)
                    self._invert_g_channel = settings.get("invert_g_channel", self._invert_g_channel)
                    
                    if self._high_resolution_mode:
                        self._texture_size = (2048, 2048)
        except Exception as e:
            print(f"加载设置出错: {e}")
            # 出错时保持默认值
    
    def save_settings(self):
        """保存设置到配置文件"""
        try:
            settings = {
                "is_dark_mode": self._is_dark_mode,
                "high_resolution_mode": self._high_resolution_mode,
                "seamless_mode": self._seamless_mode,
                "preview_repeat": self._preview_repeat,
                "invert_r_channel": self._invert_r_channel,
                "invert_g_channel": self._invert_g_channel
            }
            
            with open("app_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置出错: {e}")
            
# 创建全局设置实例
app_settings = AppSettings() 