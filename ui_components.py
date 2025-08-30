"""
UI组件模块 - 负责创建和管理主界面的UI组件

包含：
1. 菜单处理器 - 创建和管理主窗口菜单
2. UI事件处理逻辑
"""

from PyQt5.QtWidgets import QAction, QMenu, QMenuBar
from PyQt5.QtCore import Qt, QObject
from localization import translator

class MenuBuilder:
    """菜单创建器 - 负责构建应用程序的菜单"""
    
    def __init__(self, main_window):
        """
        初始化菜单创建器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.actions = {}
    
    def build_menus(self):
        """构建所有菜单并返回菜单栏"""
        menubar = self.main_window.menuBar()
        menubar.clear()
        
        # 文件菜单
        file_menu = menubar.addMenu(translator.tr("menu_file"))
        self._build_file_menu(file_menu)
        
        # 编辑菜单
        edit_menu = menubar.addMenu(translator.tr("menu_edit"))
        self._build_edit_menu(edit_menu)
        
        # 设置菜单
        settings_menu = menubar.addMenu(translator.tr("menu_settings"))
        self._build_settings_menu(settings_menu)

        # 视口菜单
        viewport_menu = menubar.addMenu(translator.tr("menu_viewport"))
        self._build_viewport_menu(viewport_menu)
        
        return menubar
        
    def _build_file_menu(self, menu):
        """构建文件菜单"""
        # 导入底图
        import_action = QAction(translator.tr("import_background"), self.main_window)
        import_action.triggered.connect(self.main_window.import_background)
        menu.addAction(import_action)
        
        # 导入Flowmap
        import_flowmap_action = QAction(translator.tr("import_flowmap"), self.main_window)
        import_flowmap_action.triggered.connect(self.main_window.import_flowmap)
        menu.addAction(import_flowmap_action)

        # 导入参考贴图（Indicator/Guide Overlay） - 紧随导入Flowmap之后
        import_overlay_action = QAction(translator.tr("import_guide_overlay"), self.main_window)
        import_overlay_action.triggered.connect(self.main_window.import_overlay_image)
        menu.addAction(import_overlay_action)

        # 导入3D模型
        import_model_action = QAction(translator.tr("import_3d_model"), self.main_window)
        import_model_action.triggered.connect(self.main_window.import_3d_model)
        menu.addAction(import_model_action)

        # 导出Flowmap
        export_action = QAction(translator.tr("export_flowmap"), self.main_window)
        export_action.triggered.connect(self.main_window.export_flowmap)
        menu.addAction(export_action)
        
        self.actions["import_background"] = import_action
        self.actions["import_flowmap"] = import_flowmap_action
        self.actions["import_guide_overlay"] = import_overlay_action
        self.actions["import_3d_model"] = import_model_action
        self.actions["export_flowmap"] = export_action
        
    def _build_edit_menu(self, menu):
        """构建编辑菜单"""
        # 撤销
        undo_action = QAction(translator.tr("undo"), self.main_window)
        undo_action.triggered.connect(self.main_window.command_mgr.undo)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.setEnabled(False)  # 初始状态禁用
        menu.addAction(undo_action)
        
        # 重做
        redo_action = QAction(translator.tr("redo"), self.main_window)
        redo_action.triggered.connect(self.main_window.command_mgr.redo)
        redo_action.setShortcut('Ctrl+Shift+Z')
        redo_action.setEnabled(False)  # 初始状态禁用
        menu.addAction(redo_action)
        
        self.actions["undo"] = undo_action
        self.actions["redo"] = redo_action
        
    def _build_settings_menu(self, menu):
        """构建设置菜单"""
        # 主题切换
        theme_action = QAction(translator.tr("toggle_theme"), self.main_window)
        theme_action.triggered.connect(self.main_window.toggle_theme)
        theme_action.setShortcut('Ctrl+T')
        menu.addAction(theme_action)
        
        # 高精度模式
        high_res_action = QAction(translator.tr("high_res_mode"), self.main_window)
        high_res_action.setCheckable(True)
        high_res_action.setChecked(False)
        high_res_action.triggered.connect(self.main_window.toggle_high_res_mode)
        high_res_action.setShortcut('Ctrl+H')
        menu.addAction(high_res_action)
        
        # 语言切换
        language_action = QAction("Switch to English/切换到英文", self.main_window)
        language_action.triggered.connect(self.main_window.toggle_language)
        language_action.setShortcut('Ctrl+L')
        menu.addAction(language_action)
        
        self.actions["toggle_theme"] = theme_action
        self.actions["high_res_mode"] = high_res_action
        self.actions["toggle_language"] = language_action

    def _build_viewport_menu(self, menu):
        """构建视口菜单"""
        toggle_3d_action = QAction(translator.tr("toggle_3d_view"), self.main_window)
        toggle_3d_action.setCheckable(True)
        toggle_3d_action.setChecked(False)
        toggle_3d_action.triggered.connect(self.main_window.toggle_3d_view)
        menu.addAction(toggle_3d_action)

        self.actions["toggle_3d_view"] = toggle_3d_action
        
        
    def get_action(self, name):
        """获取指定名称的操作"""
        return self.actions.get(name)
        
    def update_action_states(self):
        """更新操作状态"""
        if "undo" in self.actions:
            self.actions["undo"].setEnabled(len(self.main_window.command_mgr.undo_stack) > 0)
            
        if "redo" in self.actions:
            self.actions["redo"].setEnabled(len(self.main_window.command_mgr.redo_stack) > 0) 