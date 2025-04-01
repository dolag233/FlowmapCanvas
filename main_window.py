import os
from PyQt5.QtWidgets import (
    QAction, QMainWindow, QWidget, QDockWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QHBoxLayout, QSlider, QFileDialog, QMessageBox, QGroupBox, QGridLayout, QCheckBox, 
    QDoubleSpinBox, QSpinBox, QColorDialog, QWIDGETSIZE_MAX, QDesktopWidget
)
from PyQt5.QtCore import Qt, QPointF, QSize, QTimer, QPoint, QObject, pyqtSignal as Signal
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QSurfaceFormat, QPen, QBrush, QColor, QPainter, QImage, QPalette, QFont
from opengl_canvas import FlowmapCanvas
from command_manager import CommandManager
from commands import BrushStrokeCommand, ParameterChangeCommand
from localization import translator, Language
from brush_cursor import BrushCursorWidget
from app_settings import app_settings
from ui_components import MenuBuilder
from panel_manager import PanelManager
import numpy as np


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.command_mgr = CommandManager()
        self.is_in_brush_adjustment = False  # 添加标记，用于判断是否正在调整笔刷属性

        # 创建UI更新钩子
        self.command_mgr.undo_stack_changed = lambda: self.update_command_stack_ui()
        self.command_mgr.redo_stack_changed = lambda: self.update_command_stack_ui()
        
        # 创建菜单构建器
        self.menu_builder = MenuBuilder(self)
        
        # 创建面板管理器
        self.panel_manager = PanelManager(self)

        # 加载应用设置
        app_settings.load_settings()

        self.setWindowTitle(translator.tr("app_title"))
        self.setGeometry(100, 100, 1280, 720)
        
        # 初始化OpenGL画布
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 2)
        fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
        fmt.setSamples(4)
        QSurfaceFormat.setDefaultFormat(fmt)
        
        self.canvas_widget = FlowmapCanvas()
        self.canvas_widget.setMinimumSize(800, 600)
        self.setCentralWidget(self.canvas_widget)
        # 记录当前鼠标位置用于笔刷预览
        self.current_mouse_pos = QPointF(0, 0)
        self.canvas_widget.setMouseTracking(True)
        self.canvas_widget.mouseMoveNonDrawing.connect(self.update_brush_preview)

        # 在开始绘制和结束绘制时处理撤销/重做
        self.canvas_widget.drawingStarted.connect(self.on_drawing_started)
        self.canvas_widget.drawingFinished.connect(self.on_drawing_finished)

        # 连接OpenGL初始化完成信号，仅在初始化完成后加载背景图像
        self.canvas_widget.opengl_initialized.connect(self.try_load_default_background)

        # 连接背景图像加载完成信号，调整窗口比例
        self.canvas_widget.base_image_loaded.connect(self.adjust_window_aspect_ratio)
        
        # 连接笔刷属性变化信号
        self.canvas_widget.brush_properties_changed.connect(self.update_brush_properties_ui)

        # 初始化各个UI组件
        self.init_menu_bar()
        self.init_param_panel()

        # 初始化绘制区域的笔刷预览指示器
        self.setup_canvas_brush_cursor()
        
        # 添加事件过滤器捕获Alt键状态
        self.canvas_widget.installEventFilter(self)
        
        # 应用保存的设置
        high_res_action = self.menu_builder.get_action("high_res_mode")
        if high_res_action:
            high_res_action.setChecked(app_settings.high_resolution_mode)
        
        seamless_checkbox = self.panel_manager.get_control("seamless_checkbox")
        if seamless_checkbox:
            seamless_checkbox.setChecked(app_settings.seamless_mode)
            
        preview_checkbox = self.panel_manager.get_control("preview_repeat_checkbox")
        if preview_checkbox:
            preview_checkbox.setChecked(app_settings.preview_repeat)
        
        # 应用主题样式
        self.apply_modern_style()

    def try_load_default_background(self):
        """尝试加载默认底图（仅在OpenGL初始化完成后执行）"""
        default_bg_path = "background.png"
        if os.path.exists(default_bg_path):
            self.canvas_widget.load_base_image(default_bg_path)
            self.status_bar.showMessage(translator.tr("default_background_loaded", path=default_bg_path), 3000)

    def on_drawing_started(self):
        """绘制开始时保存当前状态用于撤销并更新笔刷状态"""
        self.current_flowmap_data = self.canvas_widget.flowmap_data.copy()
        if hasattr(self, 'brush_cursor'):
            self.brush_cursor.set_drawing_state(True)

    def on_drawing_finished(self):
        """绘制结束时创建并执行撤销命令并更新笔刷状态"""
        # 检查是否有实际的绘制变化
        if np.array_equal(self.current_flowmap_data, self.canvas_widget.flowmap_data):
            # 数据完全相同，不需要创建撤销命令
            if hasattr(self, 'brush_cursor'):
                self.brush_cursor.set_drawing_state(False)
            return
            
        # 创建并执行命令
        stroke_cmd = BrushStrokeCommand(self.canvas_widget, self.current_flowmap_data)
        stroke_cmd.execute()
        self.command_mgr.execute_command(stroke_cmd)
        
        # 主动发出flowmap更新信号，确保UI更新
        self.canvas_widget.flowmap_updated.emit()
        
        # 强制更新UI状态（直接调用而不是依赖回调）
        self.update_command_stack_ui()

        if hasattr(self, 'brush_cursor'):
            self.brush_cursor.set_drawing_state(False)

    def update_brush_preview(self, pos):
        """更新笔刷预览圆圈"""
        self.current_mouse_pos = pos

    def init_menu_bar(self):
        """初始化菜单栏"""
        # 使用菜单构建器创建菜单
        self.menu_builder.build_menus()
        
        # 初始化状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage(translator.tr("brush_status", size=40, strength=0.5))
        
        # 检测当前系统主题并应用对应的样式
        self.is_dark_mode = self.detect_system_theme()
        self.apply_modern_style()
        
        # OpenGL初始化检查
        if not self.canvas_widget.isValid():
            self.status_bar.showMessage(translator.tr("opengl_error"), 5000)

    def detect_system_theme(self):
        """检测系统是否为深色模式 - 仅为兼容性保留，现在使用app_settings"""
        return app_settings._detect_system_theme()

    def toggle_theme(self):
        """切换深色/浅色模式"""
        app_settings.toggle_theme()
        self.apply_modern_style()
        theme_name = translator.tr("dark_theme") if app_settings.is_dark_mode else translator.tr("light_theme")
        self.status_bar.showMessage(translator.tr("theme_changed", theme=theme_name), 2000)

    def toggle_high_res_mode(self, checked):
        """切换高精度模式"""
        texture_size = app_settings.toggle_high_res_mode(checked)
        self.canvas_widget.set_texture_size(*texture_size)
        
        if checked:
            self.status_bar.showMessage(translator.tr("high_res_enabled"), 2000)
        else:
            self.status_bar.showMessage(translator.tr("standard_res_enabled"), 2000)
        
        # 保存设置
        app_settings.save_settings()

    def init_param_panel(self):
        """初始化参数面板"""
        self.panel_manager.create_parameter_panel()
        
        # 设置fill_color初始值
        self.fill_color = (0.5, 0.5)

    def choose_fill_color(self):
        """打开颜色选择对话框选择填充颜色"""
        # 将[0,1]范围的颜色转换为[0,255]范围用于QColorDialog
        r = int(self.fill_color[0] * 255)
        g = int(self.fill_color[1] * 255)
        
        # 创建初始颜色
        initial_color = QColor(r, g, 0)
        
        # 打开颜色选择对话框
        color = QColorDialog.getColor(initial_color, self, translator.tr("choose_fill_color"))
        
        if color.isValid():
            # 将[0,255]范围的颜色转换回[0,1]范围
            self.fill_color = (color.red() / 255.0, color.green() / 255.0)
            
            # 更新颜色按钮样式
            color_btn = self.panel_manager.get_control("color_button")
            if color_btn:
                color_btn.setStyleSheet(f"background-color: rgba({color.red()}, {color.green()}, 0, 255); border-radius: 4px;")
            
            self.status_bar.showMessage(translator.tr("fill_color_set", r=self.fill_color[0], g=self.fill_color[1]), 2000)

    def fill_canvas(self):
        """使用当前选择的颜色填充整个flowmap"""
        r_value, g_value = self.fill_color
        self.canvas_widget.fill_flowmap(r_value, g_value)
        self.status_bar.showMessage(translator.tr("canvas_filled", r=r_value, g=g_value), 3000)

    def on_brush_size_changed(self, value):
        """处理笔刷大小变化"""
        old_value = self.canvas_widget.brush_radius
        self.canvas_widget.brush_radius = value
        
        # 更新UI标签
        self.panel_manager.update_brush_size_label(value)
        self.status_bar.showMessage(translator.tr("brush_status", 
                                               size=value, 
                                               strength=self.canvas_widget.brush_strength))

        # 更新画布上的笔刷光标
        self.update_canvas_brush_radius(value)

        # 仅当不是通过Alt键调整时才创建命令用于撤销/重做
        if not self.is_in_brush_adjustment:
            cmd = ParameterChangeCommand(self.canvas_widget, "brush_radius", old_value, value)
            self.command_mgr.execute_command(cmd)

    def on_flow_strength_changed(self, value):
        """处理流动强度变化"""
        strength = value / 100.0  # 转换为 0-1 范围
        old_value = self.canvas_widget.brush_strength
        self.canvas_widget.brush_strength = strength
        
        # 更新UI标签
        self.panel_manager.update_flow_strength_label(strength)
        self.status_bar.showMessage(translator.tr("brush_status", 
                                               size=int(self.canvas_widget.brush_radius), 
                                               strength=strength))
        
        # 仅当不是通过Alt键调整时才创建命令用于撤销/重做
        if not self.is_in_brush_adjustment:
            cmd = ParameterChangeCommand(self.canvas_widget, "brush_strength", old_value, strength)
            self.command_mgr.execute_command(cmd)

    def on_flow_speed_changed(self, value):
        """处理流动速度变化"""
        speed = value / 100.0
        self.canvas_widget.flow_speed = speed
        
        # 更新UI标签
        self.panel_manager.update_flow_speed_label(speed)
        self.status_bar.showMessage(translator.tr("flow_speed_changed", value=speed), 2000)

    def on_flow_distortion_changed(self, value):
        """处理流动距离变化"""
        distortion = value / 100.0
        self.canvas_widget.flow_distortion = distortion
        
        # 更新UI标签
        self.panel_manager.update_flow_distortion_label(distortion)
        self.status_bar.showMessage(translator.tr("flow_distance_changed", value=distortion), 2000)

    # 实现导入方法
    def import_background(self):
        """处理导入背景图像的功能"""
        # 设置支持的图片格式过滤器
        image_filter = translator.tr("image_files")
        path, _ = QFileDialog.getOpenFileName(self, translator.tr("select_background"), '', image_filter)
        if path:
            self.canvas_widget.load_base_image(path)
            self.status_bar.showMessage(translator.tr("background_loaded", path=path), 3000)

    def export_flowmap(self):
        """处理导出流动图的功能，支持多种格式"""
        # 创建带有过滤器的文件对话框
        image_filter = f"{translator.tr('tga_files')};;{translator.tr('png_files')};;{translator.tr('jpg_files')};;{translator.tr('bmp_files')}"
        path, selected_filter = QFileDialog.getSaveFileName(self, translator.tr("export_flowmap"), '', image_filter)
        if not path:
            return

        from PyQt5.QtWidgets import QInputDialog, QComboBox, QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QHBoxLayout, QSpinBox, QCheckBox

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(translator.tr("export_settings"))
        dialog.setMinimumWidth(350)  # 设置最小宽度，避免对话框太窄
        layout = QVBoxLayout()
        
        # 获取当前纹理大小
        current_width, current_height = self.canvas_widget.texture_size
        
        # 计算原始纹理宽高比
        original_aspect_ratio = current_width / current_height
        
        # 创建分辨率分组框
        res_group = QGroupBox(translator.tr("export_resolution"))
        res_layout = QVBoxLayout()
        res_group.setLayout(res_layout)
        
        # 添加预设分辨率选择框
        preset_layout = QHBoxLayout()
        preset_label = QLabel(translator.tr("preset_resolution"))
        preset_label.setFixedWidth(100)  # 固定标签宽度，使UI整齐
        
        preset_combo = QComboBox()
        presets = [translator.tr("custom_size"), '512x512', '1024x1024', '2048x2048', '4096x4096']
        preset_combo.addItems(presets)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(preset_combo)
        res_layout.addLayout(preset_layout)
        
        # 创建宽高输入区域
        dims_layout = QHBoxLayout()
        
        # 宽度输入框
        width_label = QLabel(translator.tr("width_label"))
        width_label.setFixedWidth(50)
        width_spinbox = QSpinBox()
        width_spinbox.setRange(1, 8192)
        width_spinbox.setValue(current_width)
        width_spinbox.setSingleStep(1)
        width_spinbox.setMinimumWidth(80)
        
        # 高度输入框
        height_label = QLabel(translator.tr("height_label"))
        height_label.setFixedWidth(50)
        height_spinbox = QSpinBox()
        height_spinbox.setRange(1, 8192)
        height_spinbox.setValue(current_height)
        height_spinbox.setSingleStep(1)
        height_spinbox.setMinimumWidth(80)
        
        # 添加到水平布局
        dims_layout.addWidget(width_label)
        dims_layout.addWidget(width_spinbox)
        dims_layout.addWidget(height_label)
        dims_layout.addWidget(height_spinbox)
        
        res_layout.addLayout(dims_layout)
        
        # 添加锁定长宽比复选框 - 使用水平布局使复选框位于中间
        lock_layout = QHBoxLayout()
        aspect_lock_checkbox = QCheckBox(translator.tr("lock_aspect_ratio"))
        # 如果是自定义尺寸，默认选中锁定长宽比
        aspect_lock_checkbox.setChecked(True)
        lock_layout.addStretch(1)
        lock_layout.addWidget(aspect_lock_checkbox)
        lock_layout.addStretch(1)
        res_layout.addLayout(lock_layout)
        
        # 添加分辨率组到主布局
        layout.addWidget(res_group)
        
        # 根据当前分辨率设置选择框的默认值
        if current_width == current_height:
            if current_width == 512:
                preset_combo.setCurrentIndex(1)
            elif current_width == 1024:
                preset_combo.setCurrentIndex(2)
            elif current_width == 2048:
                preset_combo.setCurrentIndex(3)
            elif current_width == 4096:
                preset_combo.setCurrentIndex(4)
            else:
                preset_combo.setCurrentIndex(0)  # 自定义
        else:
            preset_combo.setCurrentIndex(0)  # 自定义
        
        # 创建其他设置组
        other_group = QGroupBox(translator.tr("other_settings"))
        other_layout = QVBoxLayout()
        other_group.setLayout(other_layout)
        
        # 插值方法选择
        interp_layout = QHBoxLayout()
        interp_label = QLabel(translator.tr("scale_interpolation"))
        interp_label.setFixedWidth(130)
        
        interp_combo = QComboBox()
        interp_combo.addItems([translator.tr("bilinear"), translator.tr("nearest_neighbor")])
        
        interp_layout.addWidget(interp_label)
        interp_layout.addWidget(interp_combo)
        other_layout.addLayout(interp_layout)
        
        # 添加API模式选择
        api_layout = QHBoxLayout()
        api_label = QLabel(translator.tr("coordinate_system"))
        api_label.setFixedWidth(130)
        
        api_combo = QComboBox()
        api_combo.addItems(["OpenGL", "DirectX"])
        api_combo.setCurrentIndex(0)  # 默认OpenGL
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(api_combo)
        other_layout.addLayout(api_layout)
        
        # 添加其他设置组到主布局
        layout.addWidget(other_group)
        
        # 当调整输入值时保持长宽比
        def update_height_from_width():
            if aspect_lock_checkbox.isChecked() and preset_combo.currentIndex() == 0:
                # 根据宽高比计算新的高度
                new_width = width_spinbox.value()
                new_height = int(round(new_width / original_aspect_ratio))
                
                # 避免递归调用
                height_spinbox.blockSignals(True)
                height_spinbox.setValue(new_height)
                height_spinbox.blockSignals(False)
                
        def update_width_from_height():
            if aspect_lock_checkbox.isChecked() and preset_combo.currentIndex() == 0:
                # 根据宽高比计算新的宽度
                new_height = height_spinbox.value()
                new_width = int(round(new_height * original_aspect_ratio))
                
                # 避免递归调用
                width_spinbox.blockSignals(True)
                width_spinbox.setValue(new_width)
                width_spinbox.blockSignals(False)
        
        # 连接信号
        width_spinbox.valueChanged.connect(update_height_from_width)
        height_spinbox.valueChanged.connect(update_width_from_height)
        
        # 切换预设分辨率时的处理
        def on_preset_changed(index):
            # 调整数值框信号状态
            width_spinbox.blockSignals(True)
            height_spinbox.blockSignals(True)
            
            if index == 0:  # 自定义
                # 恢复为纹理原始尺寸
                width_spinbox.setValue(current_width)
                height_spinbox.setValue(current_height)
                aspect_lock_checkbox.setEnabled(True)  # 启用长宽比锁定
            else:
                # 当选择预设尺寸时，宽高相等（正方形贴图）
                size = int(preset_combo.currentText().split('x')[0])
                width_spinbox.setValue(size)
                height_spinbox.setValue(size)
                aspect_lock_checkbox.setEnabled(False)  # 禁用长宽比锁定（因为预设总是正方形）
            
            # 恢复信号连接
            width_spinbox.blockSignals(False)
            height_spinbox.blockSignals(False)
            
        preset_combo.currentIndexChanged.connect(on_preset_changed)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # 完成对话框设置
        dialog.setLayout(layout)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            # 获取用户设置的分辨率
            width = width_spinbox.value()
            height = height_spinbox.value()
            target_size = (width, height)
            
            interp_method = interp_combo.currentText()
            use_bilinear = interp_method == translator.tr("bilinear")
            
            # 获取当前选择的API模式
            api_mode = api_combo.currentText().lower()
            
            # 暂时切换到选定的API模式
            original_api_mode = self.canvas_widget.graphics_api_mode
            self.canvas_widget.set_graphics_api_mode(api_mode)
            
            # 导出
            self.canvas_widget.export_flowmap(path, target_size, use_bilinear)
            
            # 导出后恢复原来的API模式
            self.canvas_widget.set_graphics_api_mode(original_api_mode)
            
            self.status_bar.showMessage(translator.tr("flowmap_exported", 
                                                     path=path, 
                                                     res=f"{width}x{height}", 
                                                     interp=interp_method, 
                                                     api=api_mode), 5000)

    def update_command_stack_ui(self):
        """更新撤销/重做按钮状态"""
        self.menu_builder.update_action_states()

    def setup_canvas_brush_cursor(self):
        """设置画布上的笔刷光标预览，确保与实际位置和大小相符"""
        # 确保先删除已存在的笔刷预览实例
        if hasattr(self, 'brush_cursor') and self.brush_cursor:
            self.brush_cursor.hide()
            self.brush_cursor.deleteLater()
            
        # 创建一个透明的叠加层widget
        self.brush_cursor = BrushCursorWidget(self.canvas_widget)
        self.brush_cursor.resize(self.canvas_widget.size())
        self.brush_cursor.radius = self.canvas_widget.brush_radius
        self.brush_cursor.show()
        
        # 连接信号
        self.canvas_widget.mouse_moved.connect(self.brush_cursor.set_position)
        self.canvas_widget.resized.connect(self.handle_canvas_resize)

    def handle_canvas_resize(self):
        """当画布大小改变时更新笔刷光标大小"""
        self.brush_cursor.resize(self.canvas_widget.size())
        self.brush_cursor.update()

    def hide_brush_cursor(self):
        """这个方法已弃用,留空以维护兼容性"""
        pass

    def show_brush_cursor(self):
        """这个方法已弃用,留空以维护兼容性"""
        pass

    def update_canvas_brush_radius(self, radius):
        """更新笔刷半径"""
        if hasattr(self, 'brush_cursor'):
            self.brush_cursor.set_radius(radius)

    def on_seamless_changed(self, state):
        """处理四方连续贴图选项变更"""
        enabled = state == Qt.Checked
        self.canvas_widget.set_seamless_mode(enabled)
        app_settings.set_seamless_mode(enabled)
        app_settings.save_settings()
        
        status = translator.tr("enabled") if enabled else translator.tr("disabled")
        self.status_bar.showMessage(translator.tr("seamless_status", status=status), 2000)

    def on_speed_sensitivity_changed(self, value):
        """处理速度灵敏度滑块变化"""
        sensitivity = value / 100.0  # 转换为 0-1 范围
        self.canvas_widget.speed_sensitivity = sensitivity
        self.speed_sensitivity_label.setText(f"{translator.tr('speed_sensitivity')}: {sensitivity:.2f}")
        self.status_bar.showMessage(translator.tr("sensitivity_changed", value=sensitivity), 2000)

    def on_preview_repeat_changed(self, state):
        """处理预览重复模式变更"""
        enabled = state == Qt.Checked
        self.canvas_widget.preview_repeat = enabled
        app_settings.set_preview_repeat(enabled)
        app_settings.save_settings()
        
        self.canvas_widget.update()
        status = translator.tr("enabled") if enabled else translator.tr("disabled")
        self.status_bar.showMessage(translator.tr("preview_mode", status=status), 2000)

    def adjust_window_aspect_ratio(self, width, height):
        """初始化窗口比例以匹配底图比例，并强制保持等比例缩放"""
        if width <= 0 or height <= 0:
            print("无效的纹理尺寸")
            return
            
        # 计算图像的宽高比
        image_aspect_ratio = width / height
        
        # 记录图像纵横比
        self.canvas_widget.texture_original_aspect_ratio = image_aspect_ratio
        
        # 获取屏幕尺寸，用于计算合适的窗口大小
        screen_size = QDesktopWidget().availableGeometry()
        screen_width = screen_size.width() * 0.8  # 使用屏幕宽度的80%
        screen_height = screen_size.height() * 0.8  # 使用屏幕高度的80%
        
        # 计算图像的理想显示尺寸 (包括控制面板的宽度)
        control_panel_width = 250  # 估计的控制面板宽度
        
        # 根据屏幕大小和图像比例计算合适的窗口大小
        if image_aspect_ratio > 1.0:  # 横向图像
            # 以宽度为基准
            if screen_width > 1200 + control_panel_width:
                window_width = 1200 + control_panel_width
            else:
                window_width = int(screen_width)
            window_height = int((window_width - control_panel_width) / image_aspect_ratio) + 80  # 加上菜单和状态栏的空间
        else:  # 纵向图像
            # 以高度为基准
            if screen_height > 900:
                window_height = 900
            else:
                window_height = int(screen_height)
            window_width = int(window_height * image_aspect_ratio) + control_panel_width
        
        # 设置最小尺寸限制
        min_canvas_width = 400
        min_canvas_height = int(min_canvas_width / image_aspect_ratio)
        total_min_width = min_canvas_width + control_panel_width
        self.setMinimumSize(total_min_width, min_canvas_height + 50)  # 50 为菜单和状态栏高度
        
        # 将窗口尺寸设置为合适的大小
        self.resize(window_width, window_height)
        
        # 关键：设置canvas的固定纵横比，保证等比缩放
        self.canvas_widget.setFixedHeight(int((self.canvas_widget.width()) / image_aspect_ratio))
        
        # 立即更新预览窗口大小
        self.canvas_widget.update_preview_size()
        
        # 更新窗口的纵横比状态和绘制区域
        self.canvas_widget.update_aspect_ratio()
        self.canvas_widget.update()
        
        print(f"窗口初始化为 {window_width}x{window_height}，图像比例: {image_aspect_ratio:.2f}")

    def apply_modern_style(self):
        """应用现代化样式"""
        qss, shortcut_color = app_settings.get_theme_stylesheet()
        self.setStyleSheet(qss)
        
        # 设置快捷键标签为浅色
        shortcut_labels = self.panel_manager.get_shortcut_labels()
        for label in shortcut_labels:
            label.setStyleSheet(f"color: {shortcut_color};")

    def eventFilter(self, obj, event):
        """过滤事件以捕获Alt键状态"""
        if obj == self.canvas_widget:
            # 处理键盘事件
            if event.type() == event.KeyPress and event.key() == Qt.Key_Alt:
                if hasattr(self, 'brush_cursor'):
                    self.brush_cursor.set_adjusting_state(True)
            elif event.type() == event.KeyRelease and event.key() == Qt.Key_Alt:
                if hasattr(self, 'brush_cursor'):
                    self.brush_cursor.set_adjusting_state(False)
                    
        # 继续传递事件
        return super().eventFilter(obj, event)

    def update_brush_properties_ui(self, radius, strength):
        """更新UI上显示的笔刷属性"""
        # 设置标记，表示正在通过Alt键调整笔刷属性
        self.is_in_brush_adjustment = True
        
        # 更新笔刷大小滑块和标签，但不触发valueChanged信号
        brush_size_slider = self.panel_manager.get_control("brush_size_slider")
        if brush_size_slider:
            brush_size_slider.blockSignals(True)
            brush_size_slider.setValue(int(radius))
            brush_size_slider.blockSignals(False)
            
        self.panel_manager.update_brush_size_label(int(radius))
        
        # 更新笔刷强度滑块和标签，但不触发valueChanged信号
        flow_strength_slider = self.panel_manager.get_control("flow_strength_slider")
        if flow_strength_slider:
            flow_strength_slider.blockSignals(True)
            flow_strength_slider.setValue(int(strength * 100))
            flow_strength_slider.blockSignals(False)
            
        self.panel_manager.update_flow_strength_label(strength)
        
        # 更新笔刷预览光标大小
        if hasattr(self, 'brush_cursor'):
            self.brush_cursor.set_radius(radius)
            
        # 重置标记
        self.is_in_brush_adjustment = False

    def keyPressEvent(self, event):
        """处理主窗口的键盘事件"""
        # 使用组合键Ctrl+Z进行撤销
        if event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
            if self.command_mgr.can_undo():
                self.command_mgr.undo()
                # 更新UI状态
                self.update_command_stack_ui()
        
        # 使用组合键Ctrl+Shift+Z进行重做
        elif event.key() == Qt.Key_Z and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            if self.command_mgr.can_redo():
                self.command_mgr.redo()
                # 更新UI状态
                self.update_command_stack_ui()
        else:
            # 对于其他键盘事件，调用父类方法
            super().keyPressEvent(event)

    def toggle_language(self):
        """切换界面语言"""
        new_language = translator.toggle_language()
        
        # 更新语言切换菜单项的文本
        language_action = self.menu_builder.get_action("toggle_language")
        if language_action:
            if new_language == Language.CHINESE:
                language_action.setText("Switch to English/切换到英文")
            else:
                language_action.setText("切换到中文/Switch to Chinese")
        
        # 更新窗口标题
        self.setWindowTitle(translator.tr("app_title"))
        
        # 清除旧的UI元素
        self.menuBar().clear()  # 清除菜单栏
        
        # 删除旧的笔刷预览实例
        if hasattr(self, 'brush_cursor') and self.brush_cursor:
            self.brush_cursor.hide()
            self.brush_cursor.deleteLater()
            self.brush_cursor = None
        
        # 清除停靠窗口
        for dock in self.findChildren(QDockWidget):
            self.removeDockWidget(dock)
            dock.deleteLater()
            
        # 重建UI
        self.init_menu_bar()
        self.init_param_panel()
        
        # 重新设置笔刷预览
        self.setup_canvas_brush_cursor()
        
        # 更新状态栏
        self.status_bar.showMessage(translator.tr("brush_status", 
                                                 size=int(self.canvas_widget.brush_radius), 
                                                 strength=self.canvas_widget.brush_strength))
        
        # 应用样式
        self.apply_modern_style()

