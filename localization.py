"""
本地化模块 - 支持多语言界面
目前支持: 中文 (zh_CN) 和 英文 (en_US)
"""

import os
import json
from enum import Enum

class Language(Enum):
    """支持的语言枚举"""
    CHINESE = "zh_CN"
    ENGLISH = "en_US"

# 翻译字典 - 包含所有需要翻译的UI文本
# 格式: { key: { "zh_CN": "中文", "en_US": "English" } }
TRANSLATIONS = {
    # 菜单项
    "menu_file": {"zh_CN": "文件", "en_US": "File"},
    "menu_edit": {"zh_CN": "编辑", "en_US": "Edit"},
    "menu_settings": {"zh_CN": "设置", "en_US": "Settings"},
    "menu_viewport": {"zh_CN": "视口", "en_US": "Viewport"},
    
    # 文件菜单项
    "import_background": {"zh_CN": "导入底图", "en_US": "Import Background"},
    "import_flowmap": {"zh_CN": "导入流向贴图", "en_US": "Import Flowmap"},
    "export_flowmap": {"zh_CN": "导出流向贴图", "en_US": "Export Flowmap"},
    "import_guide_overlay": {"zh_CN": "导入参考贴图", "en_US": "Import Reference Overlay"},
    "toggle_3d_view": {"zh_CN": "显示3D视口", "en_US": "Show 3D Viewport"},
    "import_3d_model": {"zh_CN": "导入3D模型", "en_US": "Import 3D Model"},
    
    # 编辑菜单项
    "undo": {"zh_CN": "撤销", "en_US": "Undo"},
    "redo": {"zh_CN": "重做", "en_US": "Redo"},
    
    # 设置菜单项
    "toggle_theme": {"zh_CN": "切换深色/浅色模式", "en_US": "Toggle Dark/Light Mode"},
    "high_res_mode": {"zh_CN": "高精度模式 (2048x2048)", "en_US": "High Resolution Mode (2048x2048)"},
    
    # 窗口标题
    "app_title": {"zh_CN": "Flowmap Canvas", "en_US": "Flowmap Canvas"},
    
    # 笔刷参数组
    "brush_parameters": {"zh_CN": "笔刷参数", "en_US": "Brush Parameters"},
    "brush_size": {"zh_CN": "笔刷大小", "en_US": "Brush Size"},
    "flow_strength": {"zh_CN": "流动强度", "en_US": "Flow Strength"},
    "speed_sensitivity": {"zh_CN": "压感灵敏度", "en_US": "Pressure Sensitivity"},
    
    # 模式设置组
    "mode_settings": {"zh_CN": "模式设置", "en_US": "Mode Settings"},
    "enable_seamless": {"zh_CN": "启用四方连续贴图", "en_US": "Enable Seamless Tiling"},
    "enable_preview_repeat": {"zh_CN": "启用预览重复模式", "en_US": "Enable Preview Repeat Mode"},
    
    # 流动效果控制组
    "flow_effect_control": {"zh_CN": "流动效果控制", "en_US": "Flow Effect Control"},
    "flow_speed": {"zh_CN": "流动速度", "en_US": "Flow Speed"},
    "flow_distance": {"zh_CN": "流动距离", "en_US": "Flow Distance"},
    "base_scale": {"zh_CN": "底图缩放", "en_US": "Base Scale"},
    "uv_set_selection": {"zh_CN": "UV集选择", "en_US": "UV Set Selection"},
    "uv_set": {"zh_CN": "UV集", "en_US": "UV Set"},
    "overlay_settings": {"zh_CN": "参考贴图", "en_US": "Reference Overlay"},
    "overlay_opacity": {"zh_CN": "透明度", "en_US": "Opacity"},
    "uv_overlay": {"zh_CN": "模型UV", "en_US": "Mesh UV"},
    "uv_opacity": {"zh_CN": "不透明度", "en_US": "Opacity"},
    "uv_line_width": {"zh_CN": "线条宽度", "en_US": "Line Width"},
    
    # 按钮
    "fill_canvas": {"zh_CN": "填充画布", "en_US": "Fill Canvas"},
    
    # 快捷键组
    "shortcuts": {"zh_CN": "快捷键", "en_US": "Shortcuts"},
    "shortcuts_2d": {"zh_CN": "快捷键", "en_US": "Shortcuts"},
    "shortcuts_3d": {"zh_CN": "快捷键", "en_US": "Shortcuts"},
    "shortcut_left_click": {"zh_CN": "左键: 绘制流向", "en_US": "Left Click: Draw Flow"},
    "shortcut_right_click": {"zh_CN": "右键: 擦除(恢复中性值)", "en_US": "Right Click: Erase (Reset to Neutral)"},
    "shortcut_middle_drag": {"zh_CN": "中键拖动: 移动视图", "en_US": "Middle Click+Drag: Pan View"},
    "shortcut_wheel": {"zh_CN": "滚轮: 缩放视图", "en_US": "Wheel: Zoom View"},
    "shortcut_space_f": {"zh_CN": "空格/F: 重置视图", "en_US": "Space/F: Reset View"},
    "shortcut_s_drag": {"zh_CN": "S+拖动: 调整笔刷大小和强度", "en_US": "S+Drag: Adjust Brush Size and Strength"},
    "shortcut_alt_rotate": {"zh_CN": "Alt+左键拖动: 旋转视图", "en_US": "Alt+Left Drag: Rotate View"},
    
    # 状态消息
    "ready": {"zh_CN": "就绪", "en_US": "Ready"},
    "brush_status": {"zh_CN": "笔刷大小: {size}px | 强度: {strength}", "en_US": "Brush Size: {size}px | Strength: {strength}"},
    "theme_changed": {"zh_CN": "已切换至{theme}模式", "en_US": "Switched to {theme} Mode"},
    "dark_theme": {"zh_CN": "深色", "en_US": "Dark"},
    "light_theme": {"zh_CN": "浅色", "en_US": "Light"},
    "high_res_enabled": {"zh_CN": "已启用高精度模式 (2048x2048)", "en_US": "High Resolution Mode Enabled (2048x2048)"},
    "standard_res_enabled": {"zh_CN": "已切换为标准精度模式 (1024x1024)", "en_US": "Standard Resolution Mode Enabled (1024x1024)"},
    "seamless_status": {"zh_CN": "四方连续贴图已切换为: {status}", "en_US": "Seamless Tiling: {status}"},
    "enabled": {"zh_CN": "启用", "en_US": "Enabled"},
    "disabled": {"zh_CN": "禁用", "en_US": "Disabled"},
    "sensitivity_changed": {"zh_CN": "压感灵敏度已调整为: {value:.2f}", "en_US": "Pressure sensitivity set to: {value:.2f}"},
    "preview_mode": {"zh_CN": "预览重复模式: {status}", "en_US": "Preview Repeat Mode: {status}"},
    "fill_color_set": {"zh_CN": "填充颜色已设置为: ({r}, {g})", "en_US": "Fill Color Set to: ({r}, {g})"},
    "canvas_filled": {"zh_CN": "已用颜色 ({r}, {g}) 填充画布", "en_US": "Canvas Filled with Color ({r}, {g})"},
    "background_loaded": {"zh_CN": "已加载底图: {path}", "en_US": "Background Loaded: {path}"},
    "default_background_loaded": {"zh_CN": "已加载默认底图: {path}", "en_US": "Default Background Loaded: {path}"},
    "flowmap_exported": {"zh_CN": "Flowmap已导出至: {path} (分辨率: {res}, 使用{interp}, API模式: {api})", "en_US": "Flowmap Exported to: {path} (Resolution: {res}, Using {interp}, API Mode: {api})"},
    "flowmap_imported": {"zh_CN": "Flowmap已导入: {path} (分辨率: {res})", "en_US": "Flowmap Imported: {path} (Resolution: {res})"},
    
    # 对话框标题和选项
    "export_settings": {"zh_CN": "导出设置", "en_US": "Export Settings"},
    "import_settings": {"zh_CN": "导入设置", "en_US": "Import Settings"},
    "export_resolution": {"zh_CN": "导出分辨率:", "en_US": "Export Resolution:"},
    "import_resolution": {"zh_CN": "导入分辨率:", "en_US": "Import Resolution:"},
    "scale_interpolation": {"zh_CN": "缩放插值:", "en_US": "Scale Interpolation:"},
    "bilinear": {"zh_CN": "双线性", "en_US": "Bilinear"},
    "nearest_neighbor": {"zh_CN": "最近邻", "en_US": "Nearest Neighbor"},
    "channel_inversion": {"zh_CN": "通道翻转:", "en_US": "Flip Channel:"},
    "channel_orientation": {"zh_CN": "通道朝向:", "en_US": "Channel Orientation:"},
    "invert_r_channel": {"zh_CN": "翻转R通道", "en_US": "Flip R"},
    "invert_g_channel": {"zh_CN": "翻转G通道", "en_US": "Flip G"},
    "coordinate_system": {"zh_CN": "坐标系模式:", "en_US": "Coordinate System:"},
    "choose_fill_color": {"zh_CN": "选择填充颜色", "en_US": "Choose Fill Color"},
    "select_background": {"zh_CN": "选择底图", "en_US": "Select Background"},
    "select_flowmap": {"zh_CN": "选择Flowmap", "en_US": "Select Flowmap"},
    "image_files": {"zh_CN": "图像文件 (*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff)", "en_US": "Image files (*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff)"},
    "flowmap_files": {"zh_CN": "Flowmap文件 (*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff)", "en_US": "Flowmap files (*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff)"},
    "preset_resolution": {"zh_CN": "预设分辨率:", "en_US": "Preset Resolution:"},
    "custom_size": {"zh_CN": "自定义尺寸", "en_US": "Custom Size"},
    "width_label": {"zh_CN": "宽度:", "en_US": "Width:"},
    "height_label": {"zh_CN": "高度:", "en_US": "Height:"},
    "lock_aspect_ratio": {"zh_CN": "锁定长宽比", "en_US": "Lock Aspect Ratio"},
    "other_settings": {"zh_CN": "其他设置", "en_US": "Other Settings"},
    "tga_files": {"zh_CN": "TGA文件 (*.tga)", "en_US": "TGA files (*.tga)"},
    "png_files": {"zh_CN": "PNG文件 (*.png)", "en_US": "PNG files (*.png)"},
    "jpg_files": {"zh_CN": "JPG文件 (*.jpg *.jpeg)", "en_US": "JPG files (*.jpg *.jpeg)"},
    "bmp_files": {"zh_CN": "BMP文件 (*.bmp)", "en_US": "BMP files (*.bmp)"},
    
    # 导入相关消息
    "import_success": {"zh_CN": "Flowmap导入成功", "en_US": "Flowmap imported successfully"},
    "import_failed": {"zh_CN": "Flowmap导入失败", "en_US": "Failed to import flowmap"},
    "invalid_image_format": {"zh_CN": "无效的图像格式", "en_US": "Invalid image format"},
    "image_too_large": {"zh_CN": "图像尺寸过大", "en_US": "Image size too large"},
    "image_too_small": {"zh_CN": "图像尺寸过小", "en_US": "Image size too small"},
    "current_channel_orientation": {"zh_CN": "当前通道朝向: R={r_orient}, G={g_orient}", "en_US": "Current channel orientation: R={r_orient}, G={g_orient}"},
    "r_channel_normal": {"zh_CN": "正常", "en_US": "Normal"},
    "r_channel_inverted": {"zh_CN": "反转", "en_US": "Inverted"},
    "g_channel_normal": {"zh_CN": "正常", "en_US": "Normal"},
    "g_channel_inverted": {"zh_CN": "反转", "en_US": "Inverted"},
}

class Translator:
    """翻译管理器类，负责提供翻译服务"""
    
    def __init__(self):
        self.current_language = Language.CHINESE  # 默认为中文
        
        # 尝试从配置文件加载用户首选语言
        self._load_preferences()
    
    def _load_preferences(self):
        """从配置文件加载用户首选语言"""
        try:
            if os.path.exists("app_settings.json"):
                with open("app_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    if "language" in settings:
                        lang_str = settings["language"]
                        for lang in Language:
                            if lang.value == lang_str:
                                self.current_language = lang
                                break
        except Exception as e:
            print(f"加载语言首选项时出错: {e}")
    
    def _save_preferences(self):
        """保存用户首选语言到配置文件"""
        try:
            settings = {}
            if os.path.exists("app_settings.json"):
                with open("app_settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            
            settings["language"] = self.current_language.value
            
            with open("app_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存语言首选项时出错: {e}")
    
    def set_language(self, language):
        """设置当前语言"""
        if isinstance(language, Language):
            self.current_language = language
            self._save_preferences()
        else:
            raise ValueError("Language must be a Language enum value")
    
    def toggle_language(self):
        """切换语言 (中文 <-> 英文)"""
        if self.current_language == Language.CHINESE:
            self.current_language = Language.ENGLISH
        else:
            self.current_language = Language.CHINESE
        self._save_preferences()
        return self.current_language
    
    def tr(self, key, **kwargs):
        """翻译指定的key，可选替换参数"""
        if key not in TRANSLATIONS:
            return key  # 如果没有找到翻译，返回原始key
        
        lang_str = self.current_language.value
        if lang_str not in TRANSLATIONS[key]:
            # 如果当前语言没有对应翻译，尝试使用中文
            lang_str = Language.CHINESE.value
        
        text = TRANSLATIONS[key][lang_str]
        
        # 如果有替换参数，使用format进行替换
        if kwargs:
            try:
                return text.format(**kwargs)
            except:
                return text
        
        return text

# 创建全局翻译器实例
translator = Translator() 