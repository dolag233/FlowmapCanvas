import os
import sys
from PyQt5.QtWidgets import (
    QAction, QMainWindow, QWidget, QDockWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QHBoxLayout, QSlider, QFileDialog, QMessageBox, QGroupBox, QGridLayout, QCheckBox, 
    QDoubleSpinBox, QSpinBox, QColorDialog, QWIDGETSIZE_MAX, QDesktopWidget
)
from PyQt5.QtCore import Qt, QPointF, QSize, QTimer, QPoint, QObject, pyqtSignal as Signal
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QSurfaceFormat, QPen, QBrush, QColor, QPainter, QImage, QPalette, QFont, QIcon
from opengl_canvas import FlowmapCanvas
from command_manager import CommandManager
from commands import BrushStrokeCommand, ParameterChangeCommand
from parameter_registry import ParameterRegistry
from localization import translator, Language
from brush_cursor import BrushCursorWidget
from app_settings import app_settings
from ui_components import MenuBuilder
from panel_manager import PanelManager
from three_d_viewport import ThreeDViewport
import numpy as np
import subprocess
import tempfile


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.command_mgr = CommandManager()
        self.is_in_brush_adjustment = False  # 添加标记，用于判断是否正在调整笔刷属性
        self.param_registry = ParameterRegistry()
        self._old_param_values = {}

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
        
        # 设置窗口图标 - 处理打包后的路径
        if getattr(sys, 'frozen', False):
            # 如果应用程序被打包
            app_path = os.path.dirname(sys.executable)
        else:
            # 如果是直接运行脚本
            app_path = os.path.dirname(os.path.abspath(__file__))
            
        icon_path = os.path.join(app_path, 'FlowmapCanvas.ico')
        
        # 如果打包路径下没找到，尝试常规路径
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FlowmapCanvas.ico')
        
        if os.path.exists(icon_path):
            print(f"MainWindow: 找到图标文件: {icon_path}")
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"MainWindow: 警告: 图标文件不存在: {icon_path}")
        
        # 初始化OpenGL画布
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 2)
        fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
        fmt.setSamples(4)
        fmt.setStencilBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        
        self.canvas_widget = FlowmapCanvas()
        # 移除最小尺寸限制，让2D和3D界面可以灵活调整大小
        self.setCentralWidget(self.canvas_widget)
        
        # 使用画布自身的纵横比校正（在shader中letterbox），不再在这里锁尺寸
        
        # 启用dock嵌套，支持2D和3D并列显示及分割线调整
        try:
            self.setDockNestingEnabled(True)
        except Exception:
            pass
        # 记录当前鼠标位置用于笔刷预览
        self.current_mouse_pos = QPointF(0, 0)
        self.canvas_widget.setMouseTracking(True)
        self.canvas_widget.mouseMoveNonDrawing.connect(self.update_brush_preview)
        # 鼠标进入/离开2D画布时控制2D笔刷可见性
        try:
            self.canvas_widget.hover_entered.connect(lambda: self._set_2d_brush_visible(True))
            self.canvas_widget.hover_left.connect(lambda: self._set_2d_brush_visible(False))
        except Exception:
            pass

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

        # 注册参数（集中化 Model+UI 更新路径）
        self._register_parameters()

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

        # 3D 视口（延迟创建）
        self._three_d_dock = None
        self._three_d_widget = None
        # 在3D绘制时抑制2D笔刷响应
        self._suppress_2d_input = False

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

    def import_overlay_image(self):
        """导入参考贴图(Reference Overlay)并上传为GL纹理"""
        image_filter = translator.tr("image_files")
        path, _ = QFileDialog.getOpenFileName(self, translator.tr("import_guide_overlay"), '', image_filter)
        if not path:
            return
        success = self.canvas_widget.load_overlay_image(path)
        if success:
            self.status_bar.showMessage(translator.tr("background_loaded", path=path), 3000)
            # 显示参考贴图分组
            overlay_group = self.panel_manager.get_control("overlay_group")
            if overlay_group:
                overlay_group.setVisible(True)
        else:
            self.status_bar.showMessage(translator.tr("import_failed"), 3000)

    def set_overlay_opacity(self, opacity: float):
        self.canvas_widget.overlay_opacity = float(opacity)
        self.canvas_widget.update()

    def toggle_3d_view(self, checked):
        from PyQt5.QtWidgets import QDockWidget
        # 同步菜单动作选中状态
        self._set_action_checked_no_signal(self.menu_builder.get_action("toggle_3d_view"), bool(checked))
        if checked:
            if self._three_d_dock is None:
                self._three_d_widget = ThreeDViewport(self)
                self._three_d_widget.set_canvas(self.canvas_widget)
                # 3D绘制桥接到2D撤销栈
                try:
                    self._three_d_widget.paint_started.connect(self.on_drawing_started)
                    self._three_d_widget.paint_finished.connect(self.on_drawing_finished)
                    self._three_d_widget.paint_started.connect(lambda: self._set_2d_input_suppressed(True))
                    self._three_d_widget.paint_finished.connect(lambda: self._set_2d_input_suppressed(False))
                except Exception:
                    pass
                dock = QDockWidget('', self)  # 移除标题文字
                dock.setWidget(self._three_d_widget)
                # 允许3D dock覆盖到2D区域：支持左右和顶部区域
                dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea)
                # 不设置任何特性限制，保持默认功能以支持分割线调整和覆盖
                # dock.setFeatures() 不调用，使用默认特性
                
                # 隐藏标题栏但保留分割功能 - 设置一个空的widget作为标题栏
                empty_title_bar = QWidget()
                empty_title_bar.setFixedHeight(0)  # 设置高度为0，完全隐藏
                dock.setTitleBarWidget(empty_title_bar)
                try:
                    dock.visibilityChanged.connect(self._on_three_d_visibility_changed)
                except Exception:
                    pass
                self.addDockWidget(Qt.RightDockWidgetArea, dock)
                self._three_d_dock = dock
                # 延迟一次，用布局稳定后的分配设置初始尺寸
                QTimer.singleShot(0, self._set_initial_3d_dock_size)
            else:
                self._three_d_dock.show()
                # 再次显示时保证有一个合理的初始占比
                QTimer.singleShot(0, self._set_initial_3d_dock_size)
            # 显示UV覆盖组并启用
            uv_group = self.panel_manager.get_control("uv_group")
            if uv_group:
                uv_group.setVisible(True)
            self.canvas_widget.uv_wire_enabled = True
            # 切换到3D快捷键显示
            if hasattr(self.panel_manager, '_update_shortcut_display'):
                self.panel_manager._update_shortcut_display(True)
            # 聚焦3D（不在此处全局隐藏2D笔刷，交给enter/leave事件控制）
            try:
                self._three_d_widget.setFocus()
            except Exception:
                pass
        else:
            if self._three_d_dock is not None:
                self._three_d_dock.hide()
                self._schedule_canvas_layout_refresh()
            uv_group = self.panel_manager.get_control("uv_group")
            if uv_group:
                uv_group.setVisible(False)
            self.canvas_widget.uv_wire_enabled = False
            # 切换回2D快捷键显示
            if hasattr(self.panel_manager, '_update_shortcut_display'):
                self.panel_manager._update_shortcut_display(False)
            # 显示2D笔刷，隐藏3D笔刷
            try:
                if hasattr(self, 'brush_cursor') and self.brush_cursor:
                    self.brush_cursor.show()
                if self._three_d_widget:
                    self._three_d_widget.hide_brush_cursor()
                self._set_2d_input_suppressed(False)
            except Exception:
                pass

    def _set_initial_3d_dock_size(self):
        try:
            if not self._three_d_dock:
                return
            # 以2D画布高度为基准，初始化3D Dock宽高
            base = max(200, int(self.canvas_widget.height()))
            # 移除最小尺寸限制，让用户可以自由调整2D和3D的比例
            # 使用 resizeDocks 设置初始宽度占比
            self.resizeDocks([self._three_d_dock], [base], Qt.Horizontal)
            # 扩展主窗口总宽度，防止中心区域被挤压折叠
            current_dock_w = max(0, int(self._three_d_dock.width()))
            target_dock_w = base
            add_w = max(0, target_dock_w - current_dock_w)
            if add_w > 0:
                new_w = int(self.width() + add_w)
                new_h = max(int(self.height()), base + 80)
                self.resize(new_w, new_h)
            # 强制一次布局刷新
            self._three_d_widget.updateGeometry()
            self._schedule_canvas_layout_refresh()
        except Exception as e:
            print(f"set_initial_3d_dock_size error: {e}")

    def import_3d_model(self):
        from PyQt5.QtWidgets import QFileDialog
        from mesh_loader import load_obj
        from gltf_loader import load_gltf
        filter_str = "3D Models (*.obj *.gltf *.glb *.fbx);;" + translator.tr("image_files")
        path, _ = QFileDialog.getOpenFileName(self, translator.tr("import_3d_model"), '', filter_str)
        if not path:
            return
        # 导入后立刻打开/显示3D视口
        if self._three_d_widget is None:
            self.toggle_3d_view(True)
        else:
            if self._three_d_dock is not None:
                self._three_d_dock.show()
            # 同步菜单项勾选
            self._set_action_checked_no_signal(self.menu_builder.get_action("toggle_3d_view"), True)
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in [".gltf", ".glb"]:
                mesh = load_gltf(path)
            elif ext == ".fbx":
                glb_path = self._convert_fbx_to_gltf(path)
                if not glb_path:
                    self.status_bar.showMessage(translator.tr("import_failed"), 3000)
                    return
                mesh = load_gltf(glb_path)
            else:
                mesh = load_obj(path)
            ok = mesh is not None and mesh.positions.size > 0 and mesh.indices.size > 0
            if ok:
                self._three_d_widget.load_mesh(mesh)
                self.status_bar.showMessage(translator.tr("import_success"), 3000)
                # 推送UV数据到2D
                try:
                    # 更新UV集选择UI
                    if hasattr(mesh, 'uv_set_names') and mesh.uv_set_names:
                        self.panel_manager.update_uv_sets(mesh.uv_set_names)
                        self.selected_uv_set = 0  # 重置为第一个UV集
                    
                    # 设置默认UV覆盖数据（使用第一个UV集）
                    self.canvas_widget.set_uv_overlay_data(mesh.uvs, mesh.indices)
                    self.canvas_widget.uv_wire_enabled = True
                    self.canvas_widget.update()
                except Exception as e:
                    print(f"Failed to set UV overlay data: {e}")
            else:
                self.status_bar.showMessage(translator.tr("import_failed"), 3000)
        except Exception as e:
            print(f"Failed to load mesh: {e}")
            self.status_bar.showMessage(translator.tr("import_failed"), 3000)

    def _convert_fbx_to_gltf(self, fbx_path: str) -> str:
        """Use FBX2glTF to convert FBX to GLB; returns path to .glb or empty string on failure.

        Resolution order for the converter binary:
        1) Environment variable FBX2GLTF_PATH
        2) A local executable in the project directory or current working directory whose name contains 'fbx2gltf'
        3) Fall back to invoking 'FBX2glTF' from PATH
        """
        exe = os.environ.get("FBX2GLTF_PATH", "")
        if not exe:
            # Search local directories for a binary whose name contains 'fbx2gltf'
            try:
                search_dirs = [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
                found = ""
                for d in search_dirs:
                    try:
                        for name in os.listdir(d):
                            if "fbx2gltf" in name.lower():
                                candidate = os.path.join(d, name)
                                if os.path.isfile(candidate):
                                    found = candidate
                                    break
                        if found:
                            break
                    except Exception:
                        continue
                if found:
                    exe = found
            except Exception:
                pass
        if not exe:
            exe = "FBX2glTF"

        temp_dir = tempfile.mkdtemp(prefix="fbx2gltf_")
        out_base = os.path.join(temp_dir, "converted")
        try:
            proc = subprocess.run([exe, "-i", fbx_path, "-o", out_base, "-b"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                print(f"FBX2glTF failed (code {proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
                return ""
            glb_path = out_base + ".glb"
            if os.path.exists(glb_path):
                return glb_path
            for name in os.listdir(temp_dir):
                if name.lower().endswith('.glb'):
                    return os.path.join(temp_dir, name)
            return ""
        except FileNotFoundError:
            print("FBX2glTF not found. Place the binary in project folder, set FBX2GLTF_PATH, or add to PATH.")
            return ""

    def _schedule_canvas_layout_refresh(self):
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._refresh_canvas_layout)
        except Exception:
            try:
                self._refresh_canvas_layout()
            except Exception:
                pass

    def _refresh_canvas_layout(self):
        try:
            # 强制根据当前窗口/布局更新2D画布的纵横比与预览尺寸
            self.canvas_widget.update_preview_size()
            self.canvas_widget.update_aspect_ratio()
            if hasattr(self.canvas_widget, 'resized'):
                self.canvas_widget.resized.emit()
            self.canvas_widget.update()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 任何主窗口尺寸变化后，调度2D布局刷新以避免拉伸
        self._schedule_canvas_layout_refresh()

    def _set_slider_value_no_signal(self, slider, value):
        """安全设置slider的值，不触发信号"""
        if slider is None:
            return
        if slider.value() == int(value):
            return
        slider.blockSignals(True)
        slider.setValue(int(value))
        slider.blockSignals(False)

    def _set_checkbox_checked_no_signal(self, checkbox, checked):
        if checkbox is None:
            return
        if bool(checkbox.isChecked()) == bool(checked):
            return
        checkbox.blockSignals(True)
        checkbox.setChecked(bool(checked))
        checkbox.blockSignals(False)

    def _register_parameters(self):
        """集中注册参数的读/写，保证 Model+UI+Brush 统一更新路径"""
        pm = self.panel_manager
        c = self.canvas_widget

        # brush_radius
        self.param_registry.register(
            "brush_radius",
            read_fn=lambda: int(c.brush_radius),
            apply_fn=lambda v, transient=False: (
                setattr(c, "brush_radius", int(v)),
                self.update_canvas_brush_radius(int(v)),
                pm.update_brush_size_label(int(v)),
                self._set_slider_value_no_signal(pm.get_control("brush_size_slider"), int(v))
            )
        )

        # brush_strength (0~1)
        self.param_registry.register(
            "brush_strength",
            read_fn=lambda: float(c.brush_strength),
            apply_fn=lambda v, transient=False: (
                setattr(c, "brush_strength", float(v)),
                pm.update_flow_strength_label(float(v)),
                self._set_slider_value_no_signal(pm.get_control("flow_strength_slider"), int(round(float(v) * 100)))
            )
        )

        # speed_sensitivity (0~1)
        self.param_registry.register(
            "speed_sensitivity",
            read_fn=lambda: float(c.speed_sensitivity),
            apply_fn=lambda v, transient=False: (
                setattr(c, "speed_sensitivity", float(v)),
                pm.update_speed_sensitivity_label(float(v)),
                self._set_slider_value_no_signal(pm.get_control("speed_sensitivity_slider"), int(round(float(v) * 100)))
            )
        )

        # flow_speed (0~2)
        self.param_registry.register(
            "flow_speed",
            read_fn=lambda: float(c.flow_speed),
            apply_fn=lambda v, transient=False: (
                setattr(c, "flow_speed", float(v)),
                pm.update_flow_speed_label(float(v)),
                self._set_slider_value_no_signal(pm.get_control("flow_speed_slider"), int(round(float(v) * 100)))
            )
        )

        # flow_distortion (0~1)
        self.param_registry.register(
            "flow_distortion",
            read_fn=lambda: float(c.flow_distortion),
            apply_fn=lambda v, transient=False: (
                setattr(c, "flow_distortion", float(v)),
                pm.update_flow_distortion_label(float(v)),
                self._set_slider_value_no_signal(pm.get_control("flow_distortion_slider"), int(round(float(v) * 100)))
            )
        )

        # base_scale (0.5~4.0)
        # 注意：仅作为渲染缩放传入 shader，不改变坐标映射
        if not hasattr(c, 'base_scale'):
            setattr(c, 'base_scale', 1.0)
        self.param_registry.register(
            "base_scale",
            read_fn=lambda: float(getattr(c, 'base_scale', 1.0)),
            apply_fn=lambda v, transient=False: (
                setattr(c, "base_scale", float(v)),
                (pm.get_control("base_scale_label").setText(f"{translator.tr('base_scale')}: {float(v):.2f}") if pm.get_control("base_scale_label") else None),
                self._set_slider_value_no_signal(pm.get_control("base_scale_slider"), int(round(float(v) * 100))),
                c.update()
            )
        )

        # seamless mode (bool)
        self.param_registry.register(
            "seamless_mode",
            read_fn=lambda: bool(app_settings.seamless_mode),
            apply_fn=lambda v, transient=False: (
                self.canvas_widget.set_seamless_mode(bool(v)),
                app_settings.set_seamless_mode(bool(v)),
                app_settings.save_settings(),
                self._set_checkbox_checked_no_signal(pm.get_control("seamless_checkbox"), bool(v)),
                self.status_bar.showMessage(translator.tr("seamless_status", status=(translator.tr("enabled") if bool(v) else translator.tr("disabled"))), 2000)
            )
        )

        # preview repeat (bool)
        self.param_registry.register(
            "preview_repeat",
            read_fn=lambda: bool(app_settings.preview_repeat),
            apply_fn=lambda v, transient=False: (
                setattr(self.canvas_widget, "preview_repeat", bool(v)),
                app_settings.set_preview_repeat(bool(v)),
                app_settings.save_settings(),
                self.canvas_widget.update(),
                self._set_checkbox_checked_no_signal(pm.get_control("preview_repeat_checkbox"), bool(v)),
                self.status_bar.showMessage(translator.tr("preview_mode", status=(translator.tr("enabled") if bool(v) else translator.tr("disabled"))), 2000)
            )
        )

        # invert R channel (bool)
        self.param_registry.register(
            "invert_r_channel",
            read_fn=lambda: bool(app_settings.invert_r_channel),
            apply_fn=lambda v, transient=False: (
                app_settings.set_invert_r_channel(bool(v)),
                app_settings.save_settings(),
                self._set_checkbox_checked_no_signal(pm.get_control("invert_r_checkbox"), bool(v)),
                self.panel_manager._update_orientation_label()
            )
        )

        # invert G channel (bool)
        self.param_registry.register(
            "invert_g_channel",
            read_fn=lambda: bool(app_settings.invert_g_channel),
            apply_fn=lambda v, transient=False: (
                app_settings.set_invert_g_channel(bool(v)),
                app_settings.save_settings(),
                self._set_checkbox_checked_no_signal(pm.get_control("invert_g_checkbox"), bool(v)),
                self.panel_manager._update_orientation_label()
            )
        )

        # UV overlay params
        self.param_registry.register(
            "uv_wire_opacity",
            read_fn=lambda: float(c.uv_wire_opacity),
            apply_fn=lambda v, transient=False: (
                setattr(c, "uv_wire_opacity", float(v)),
                None
            )
        )
        self.param_registry.register(
            "uv_wire_line_width",
            read_fn=lambda: float(c.uv_wire_line_width),
            apply_fn=lambda v, transient=False: (
                setattr(c, "uv_wire_line_width", float(v)),
                None
            )
        )

        # overlay_opacity (0~1)
        self.param_registry.register(
            "overlay_opacity",
            read_fn=lambda: float(self.canvas_widget.overlay_opacity),
            apply_fn=lambda v, transient=False: (
                setattr(self.canvas_widget, "overlay_opacity", float(v)),
                self._set_slider_value_no_signal(pm.get_control("overlay_opacity_slider"), int(round(float(v) * 100))),
                pm.get_control("overlay_opacity_label").setText(f"{translator.tr('overlay_opacity')}: {float(v):.2f}") if pm.get_control("overlay_opacity_label") else None,
                self.canvas_widget.update()
            )
        )

        # selected_uv_set (int index)
        if not hasattr(self, 'selected_uv_set'):
            self.selected_uv_set = 0
        self.param_registry.register(
            "selected_uv_set",
            read_fn=lambda: int(getattr(self, 'selected_uv_set', 0)),
            apply_fn=lambda v, transient=False: (
                setattr(self, 'selected_uv_set', int(v)),
                self._update_uv_set_selection(int(v))
            )
        )

    def on_brush_size_pressed(self):
        # 记录开始编辑时的旧值
        try:
            self._old_param_values["brush_radius"] = self.param_registry.read("brush_radius")
        except Exception:
            self._old_param_values["brush_radius"] = int(self.canvas_widget.brush_radius)

    def on_brush_size_changed(self, value, need_record=False):
        """处理笔刷大小变化"""
        # 实时应用，不入栈
        self.param_registry.apply("brush_radius", int(value), transient=True)
        if need_record and not self.is_in_brush_adjustment:
            old_value = getattr(self, "_old_param_values", {}).get("brush_radius", None)
            new_value = int(value)
            if old_value is None:
                old_value = new_value
            if old_value != new_value and self.param_registry.has_key("brush_radius"):
                cmd = ParameterChangeCommand(self.param_registry, "brush_radius", old_value, new_value)
            self.command_mgr.execute_command(cmd)

    def on_brush_size_released(self):
        slider = self.panel_manager.get_control("brush_size_slider")
        if slider:
            value = slider.value()
        else:
            value = int(self.canvas_widget.brush_radius)
        self.on_brush_size_changed(value, True)

    def on_flow_strength_pressed(self):
        # 记录开始编辑时的旧值
        try:
            self._old_param_values["brush_strength"] = self.param_registry.read("brush_strength")
        except Exception:
            self._old_param_values["brush_strength"] = float(self.canvas_widget.brush_strength)

    def on_flow_strength_changed(self, value, need_record=False):
        """处理流动强度变化"""
        strength = value / 100.0
        # 实时应用，不入栈
        self.param_registry.apply("brush_strength", float(strength), transient=True)
        if need_record and not self.is_in_brush_adjustment:
            old_value = getattr(self, "_old_param_values", {}).get("brush_strength", None)
            new_value = float(strength)
            if old_value is None:
                old_value = new_value
            if abs(old_value - new_value) > 1e-6 and self.param_registry.has_key("brush_strength"):
                cmd = ParameterChangeCommand(self.param_registry, "brush_strength", old_value, new_value)
            self.command_mgr.execute_command(cmd)

    def on_flow_strength_released(self):
        slider = self.panel_manager.get_control("flow_strength_slider")
        if slider:
            value = slider.value()
        else:
            value = int(self.canvas_widget.brush_strength * 100)
        self.on_flow_strength_changed(value, True)

    def _on_speed_sensitivity_released_internal(self, slider_value):
        # 实时应用在 valueChanged 已做；此处决定是否入栈
        sensitivity = slider_value / 100.0
        old_value = getattr(self, "_old_param_values", {}).get("speed_sensitivity", None)
        new_value = float(sensitivity)
        if old_value is None:
            old_value = new_value
        if abs(old_value - new_value) > 1e-6 and self.param_registry.has_key("speed_sensitivity"):
            cmd = ParameterChangeCommand(self.param_registry, "speed_sensitivity", old_value, new_value)
            self.command_mgr.execute_command(cmd)

    def on_flow_speed_changed(self, value, need_record=False):
        """处理流动速度变化"""
        speed = value / 100.0
        # 实时应用，不入栈
        self.param_registry.apply("flow_speed", float(speed), transient=True)
        if need_record:
            old_value = getattr(self, "_old_param_values", {}).get("flow_speed", None)
            new_value = float(speed)
            if old_value is None:
                old_value = new_value
            if abs(old_value - new_value) > 1e-6 and self.param_registry.has_key("flow_speed"):
                cmd = ParameterChangeCommand(self.param_registry, "flow_speed", old_value, new_value)
                self.command_mgr.execute_command(cmd)

    def on_flow_distortion_changed(self, value, need_record=False):
        """处理流动距离变化"""
        distortion = value / 100.0
        # 实时应用，不入栈
        self.param_registry.apply("flow_distortion", float(distortion), transient=True)
        if need_record:
            old_value = getattr(self, "_old_param_values", {}).get("flow_distortion", None)
            new_value = float(distortion)
            if old_value is None:
                old_value = new_value
            if abs(old_value - new_value) > 1e-6 and self.param_registry.has_key("flow_distortion"):
                cmd = ParameterChangeCommand(self.param_registry, "flow_distortion", old_value, new_value)
                self.command_mgr.execute_command(cmd)

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
        
        # 添加通道反转选项
        channel_layout = QHBoxLayout()
        channel_label = QLabel(translator.tr("channel_inversion"))
        channel_label.setFixedWidth(130)
        
        # 创建复选框容器
        checkbox_container = QHBoxLayout()
        checkbox_container.setSpacing(15)  # 设置复选框间距
        
        invert_r_checkbox = QCheckBox(translator.tr("invert_r_channel"))
        invert_g_checkbox = QCheckBox(translator.tr("invert_g_channel"))
        
        # 设置初始状态
        invert_r_checkbox.setChecked(app_settings.invert_r_channel)
        invert_g_checkbox.setChecked(app_settings.invert_g_channel)
        
        checkbox_container.addWidget(invert_r_checkbox)
        checkbox_container.addWidget(invert_g_checkbox)
        checkbox_container.addStretch()  # 添加弹性空间
        
        channel_layout.addWidget(channel_label)
        channel_layout.addLayout(checkbox_container)
        other_layout.addLayout(channel_layout)
        
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
            
            # 获取通道反转设置
            invert_r = invert_r_checkbox.isChecked()
            invert_g = invert_g_checkbox.isChecked()
            
            # 保存通道反转设置
            app_settings.set_invert_r_channel(invert_r)
            app_settings.set_invert_g_channel(invert_g)
            app_settings.save_settings()
            
            # 导出
            self.canvas_widget.export_flowmap(path, target_size, use_bilinear, invert_r, invert_g)
            
            self.status_bar.showMessage(translator.tr("flowmap_exported", 
                                                     path=path, 
                                                     res=f"{width}x{height}", 
                                                     interp=interp_method), 5000)

    def import_flowmap(self):
        """处理导入Flowmap的功能，支持多种格式和通道朝向设置"""
        from PyQt5.QtWidgets import QInputDialog, QComboBox, QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QHBoxLayout, QSpinBox, QCheckBox, QGroupBox
        
        # 创建带有过滤器的文件对话框
        flowmap_filter = translator.tr("flowmap_files")
        path, selected_filter = QFileDialog.getOpenFileName(self, translator.tr("select_flowmap"), '', flowmap_filter)
        if not path:
            return

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(translator.tr("import_settings"))
        dialog.setMinimumWidth(350)  # 设置最小宽度，避免对话框太窄
        layout = QVBoxLayout()
        
        # 获取当前纹理大小
        current_width, current_height = self.canvas_widget.texture_size
        
        # 计算原始纹理宽高比
        original_aspect_ratio = current_width / current_height
        
        # 创建分辨率分组框
        res_group = QGroupBox(translator.tr("import_resolution"))
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
        
        # 添加通道朝向选项
        channel_layout = QHBoxLayout()
        channel_label = QLabel(translator.tr("channel_orientation"))
        channel_label.setFixedWidth(130)
        
        # 创建复选框容器
        checkbox_container = QHBoxLayout()
        checkbox_container.setSpacing(15)  # 设置复选框间距
        
        invert_r_checkbox = QCheckBox(translator.tr("invert_r_channel"))
        invert_g_checkbox = QCheckBox(translator.tr("invert_g_channel"))
        
        # 设置初始状态
        invert_r_checkbox.setChecked(app_settings.invert_r_channel)
        invert_g_checkbox.setChecked(app_settings.invert_g_channel)
        
        checkbox_container.addWidget(invert_r_checkbox)
        checkbox_container.addWidget(invert_g_checkbox)
        checkbox_container.addStretch()  # 添加弹性空间
        
        channel_layout.addWidget(channel_label)
        channel_layout.addLayout(checkbox_container)
        other_layout.addLayout(channel_layout)
        
        # 显示当前通道朝向状态
        r_orient = translator.tr("r_channel_inverted") if app_settings.invert_r_channel else translator.tr("r_channel_normal")
        g_orient = translator.tr("g_channel_inverted") if app_settings.invert_g_channel else translator.tr("g_channel_normal")
        orientation_label = QLabel(translator.tr("current_channel_orientation", r_orient=r_orient, g_orient=g_orient))
        orientation_label.setStyleSheet("color: #666666; font-size: 10px;")
        other_layout.addWidget(orientation_label)
        
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
            
            # 获取通道反转设置
            invert_r = invert_r_checkbox.isChecked()
            invert_g = invert_g_checkbox.isChecked()
            
            # 保存通道反转设置
            app_settings.set_invert_r_channel(invert_r)
            app_settings.set_invert_g_channel(invert_g)
            app_settings.save_settings()
            
            # 导入
            success = self.canvas_widget.import_flowmap(path, target_size, use_bilinear, invert_r, invert_g)
            
            if success:
                self.status_bar.showMessage(translator.tr("flowmap_imported", 
                                                         path=path, 
                                                         res=f"{width}x{height}"), 5000)
            else:
                self.status_bar.showMessage(translator.tr("import_failed"), 5000)

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
        
        # 更新UI标签 - 使用panel_manager获取和更新标签
        self.panel_manager.update_speed_sensitivity_label(sensitivity)
        
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
        
        # 初始化时仅刷新画布内部纵横比与预览，无需锁定尺寸
        self._refresh_canvas_layout()
        
        # 立即更新预览窗口大小
        self.canvas_widget.update_preview_size()
        
        # 更新窗口的纵横比状态和绘制区域
        self.canvas_widget.update_aspect_ratio()
        self.canvas_widget.update()
        
        print(f"窗口初始化为 {window_width}x{window_height}，图像比例: {image_aspect_ratio:.2f}")
    
    def _load_font(self):
        """加载字体：优先在fonts目录下搜索ttf/otf文件"""
        try:
            from PyQt5.QtGui import QFontDatabase, QFont
            from PyQt5.QtWidgets import QApplication
            
            font_loaded = False
            
            # 首先在fonts目录下搜索所有字体文件
            fonts_dir = "fonts"
            if os.path.exists(fonts_dir):
                try:
                    for filename in os.listdir(fonts_dir):
                        if filename.lower().endswith(('.ttf', '.otf')):
                            font_path = os.path.join(fonts_dir, filename)
                            font_id = QFontDatabase.addApplicationFont(font_path)
                            if font_id != -1:
                                font_families = QFontDatabase.applicationFontFamilies(font_id)
                                if font_families:
                                    app = QApplication.instance()
                                    if app:
                                        # 设置全局字体
                                        font = QFont(font_families[0], 9)  # 9pt 大小
                                        app.setFont(font)
                                        print(f"已从fonts目录加载字体: {filename} ({font_families[0]})")
                                        font_loaded = True
                                        break
                except Exception as e:
                    print(f"搜索fonts目录失败: {e}")
            
            # 如果fonts目录没有找到字体，尝试根目录的OPPOSans-H.ttf
            if not font_loaded:
                fallback_paths = ["OPPOSans-H.ttf"]
                for font_path in fallback_paths:
                    if os.path.exists(font_path):
                        font_id = QFontDatabase.addApplicationFont(font_path)
                        if font_id != -1:
                            font_families = QFontDatabase.applicationFontFamilies(font_id)
                            if font_families:
                                app = QApplication.instance()
                                if app:
                                    # 设置全局字体
                                    font = QFont(font_families[0], 9)  # 9pt 大小
                                    app.setFont(font)
                                    print(f"已从根目录加载字体: {font_path} ({font_families[0]})")
                                    font_loaded = True
                                    break
            
            if not font_loaded:
                print("未找到字体文件，使用系统默认字体")
                
        except Exception as e:
            print(f"字体加载失败: {e}")
    
    # 保留早先的 resizeEvent 定义（文件前部已有），此处不再重载，避免冲突

    def _setup_canvas_container(self):
        """设置2D画布容器，支持在非正方形窗口中居中显示正方形内容"""
        # 当前实现保持简单，后续可以扩展为更复杂的布局管理
        pass
    
    def _update_canvas_layout(self):
        """更新2D画布布局，确保在非正方形区域中正确显示"""
        try:
            if not hasattr(self, 'canvas_widget') or not self.canvas_widget:
                return
                
            # 获取中央区域的实际可用尺寸
            central_widget = self.centralWidget()
            if not central_widget:
                return
                
            # 获取中央区域的尺寸
            width = central_widget.width()
            height = central_widget.height()
            
            if width <= 0 or height <= 0:
                return
            
            # 如果有纹理比例，使用纹理比例
            if hasattr(self.canvas_widget, 'texture_original_aspect_ratio') and self.canvas_widget.texture_original_aspect_ratio:
                aspect_ratio = self.canvas_widget.texture_original_aspect_ratio
                
                # 计算在当前区域内能容纳的最大尺寸
                if width / height > aspect_ratio:
                    # 中央区域比纹理更宽，以高度为基准
                    canvas_height = height
                    canvas_width = int(height * aspect_ratio)
                else:
                    # 中央区域比纹理更高，以宽度为基准
                    canvas_width = width
                    canvas_height = int(width / aspect_ratio)
            else:
                # 没有纹理时，使用正方形，以较小边为准
                square_size = min(width, height)
                canvas_width = canvas_height = square_size
            
            # 确保尺寸不为0
            canvas_width = max(100, canvas_width)
            canvas_height = max(100, canvas_height)
            
            # 更新画布尺寸
            self.canvas_widget.setFixedSize(canvas_width, canvas_height)
            
            print(f"Canvas layout updated: {canvas_width}x{canvas_height} in central area {width}x{height}")
            
        except Exception as e:
            print(f"_update_canvas_layout error: {e}")

    def apply_modern_style(self):
        """应用现代化样式：Dracula主题 + OPPO Sans字体"""
        # 1) 加载OPPO Sans字体
        self._load_font()
        
        # 2) 应用Dracula主题（根据深浅模式选择）
        try:
            if app_settings.is_dark_mode:
                dracula_path = "themes/dracula.qss"
                shortcut_color = '#6272a4'  # Dracula comment color
                theme_name = "Dracula 深色"
            else:
                dracula_path = "themes/dracula-light.qss"
                shortcut_color = '#6272a4'  # 保持一致的注释色
                theme_name = "Dracula 浅色"
                
            if os.path.exists(dracula_path):
                with open(dracula_path, "r", encoding="utf-8") as f:
                    dracula_qss = f.read()
                self.setStyleSheet(dracula_qss)
                for label in self.panel_manager.get_shortcut_labels():
                    label.setStyleSheet(f"color: {shortcut_color};")
                print(f"已应用 {theme_name} 主题")
                return
        except Exception as e:
            print(f"Dracula 主题加载失败: {e}")
        
        # 回退：QDarkStyle
        try:
            import qdarkstyle
            if app_settings.is_dark_mode:
                self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))
                shortcut_color = '#888888'
            else:
                self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5', palette=qdarkstyle.LightPalette))
                shortcut_color = '#666666'
            
            for label in self.panel_manager.get_shortcut_labels():
                label.setStyleSheet(f"color: {shortcut_color};")
            return
        except Exception:
            pass

        # 最终回退：内置QSS
        qss, shortcut_color = app_settings.get_theme_stylesheet()
        self.setStyleSheet(qss)
        for label in self.panel_manager.get_shortcut_labels():
            label.setStyleSheet(f"color: {shortcut_color};")

    def eventFilter(self, obj, event):
        """过滤事件以捕获S键状态"""
        if obj == self.canvas_widget:
            # 处理键盘事件
            if event.type() == event.KeyPress and event.key() == Qt.Key_S:
                if hasattr(self, 'brush_cursor'):
                    self.brush_cursor.set_adjusting_state(True)
            elif event.type() == event.KeyRelease and event.key() == Qt.Key_S:
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

    def _set_2d_brush_visible(self, visible: bool):
        try:
            if hasattr(self, 'brush_cursor') and self.brush_cursor:
                self.brush_cursor.setVisible(bool(visible))
        except Exception:
            pass

    def _set_2d_input_suppressed(self, suppressed: bool):
        self._suppress_2d_input = bool(suppressed)

    def _set_action_checked_no_signal(self, action, checked: bool):
        try:
            if action is None:
                return
            action.blockSignals(True)
            action.setChecked(bool(checked))
            action.blockSignals(False)
        except Exception:
            pass

    def _update_uv_set_selection(self, uv_set_index):
        """更新UV集选择，同步3D视口和2D覆盖"""
        try:
            if hasattr(self, '_three_d_widget') and self._three_d_widget:
                # 通知3D视口切换UV集
                self._three_d_widget.set_active_uv_set(uv_set_index)
                
                # 获取新UV集的数据并更新2D覆盖
                uvs, indices = self._three_d_widget.get_uv_wire_data(uv_set_index)
                if uvs is not None and indices is not None:
                    self.canvas_widget.set_uv_overlay_data(uvs, indices)
                    self.canvas_widget.update()
        except Exception as e:
            print(f"_update_uv_set_selection error: {e}")

