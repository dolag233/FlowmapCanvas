"""
面板管理器模块 - 负责创建和管理工具面板
"""

from PyQt5.QtWidgets import (
    QDockWidget, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QSlider, QGroupBox, QCheckBox, QPushButton, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from localization import translator
from functools import partial

class PanelManager:
    """工具面板管理器 - 负责创建和管理工具面板"""
    
    def __init__(self, main_window):
        """
        初始化面板管理器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.dock_widgets = {}
        self.controls = {}
        
    def create_parameter_panel(self):
        """创建参数面板"""
        param_dock = QDockWidget('', self.main_window)  # 移除标题
        param_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)  # 禁止折叠和移动
        param_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 创建各个组件
        self._create_brush_group(layout)
        self._create_mode_group(layout)
        self._create_flow_group(layout)
        self._create_channel_orientation_group(layout)
        self._create_uv_overlay_group(layout)
        self._create_overlay_group(layout)
        self._create_fill_controls(layout)
        layout.addStretch()  # 添加伸缩空间，使其他组件靠上
        self._create_shortcut_group(layout)

        param_widget.setLayout(layout)
        param_dock.setWidget(param_widget)
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, param_dock)
        
        self.dock_widgets["parameter_panel"] = param_dock
        return param_dock

    def _create_brush_group(self, parent_layout):
        """创建笔刷参数组"""
        brush_group = QGroupBox(translator.tr("brush_parameters"))
        brush_layout = QVBoxLayout()
        brush_layout.setSpacing(8)

        # 笔刷大小参数
        brush_size_label = QLabel(f"{translator.tr('brush_size')}: 40")

        font = brush_size_label.font()
        font_size = font.pointSize()
        font.setPointSize(int(font_size * 1.2))
        brush_size_label.setFont(font)
        
        brush_size_slider = QSlider(Qt.Horizontal)
        brush_size_slider.setMinimum(5)
        brush_size_slider.setMaximum(200)
        brush_size_slider.setValue(40)  # 默认值与 FlowmapCanvas 中的相同

        # 流动强度参数
        flow_strength_label = QLabel(f"{translator.tr('flow_strength')}: 0.5")
        flow_strength_label.setFont(font)  # 使用相同的放大字体
        
        flow_strength_slider = QSlider(Qt.Horizontal)
        flow_strength_slider.setMinimum(1)
        flow_strength_slider.setMaximum(100)
        flow_strength_slider.setValue(50)  # 0.5 * 100

        # 速度灵敏度参数
        speed_sensitivity_label = QLabel(f"{translator.tr('speed_sensitivity')}: 0.7")
        speed_sensitivity_label.setFont(font)  # 使用相同的放大字体
        
        speed_sensitivity_slider = QSlider(Qt.Horizontal)
        speed_sensitivity_slider.setMinimum(1)
        speed_sensitivity_slider.setMaximum(100)
        speed_sensitivity_slider.setValue(70)  # 0.7 * 100

        # 连接信号：拖动时仅预览；释放时才入撤销栈
        brush_size_slider.sliderPressed.connect(self.main_window.on_brush_size_pressed)
        brush_size_slider.valueChanged.connect(self.main_window.on_brush_size_changed)
        brush_size_slider.sliderReleased.connect(self.main_window.on_brush_size_released)

        flow_strength_slider.sliderPressed.connect(self.main_window.on_flow_strength_pressed)
        flow_strength_slider.valueChanged.connect(self.main_window.on_flow_strength_changed)
        flow_strength_slider.sliderReleased.connect(self.main_window.on_flow_strength_released)

        speed_sensitivity_slider.sliderPressed.connect(lambda: self.main_window._old_param_values.__setitem__("speed_sensitivity", self.main_window.param_registry.read("speed_sensitivity") if self.main_window.param_registry.has_key("speed_sensitivity") else self.main_window.canvas_widget.speed_sensitivity))
        speed_sensitivity_slider.valueChanged.connect(self.main_window.on_speed_sensitivity_changed)
        speed_sensitivity_slider.sliderReleased.connect(lambda: self.main_window._on_speed_sensitivity_released_internal(speed_sensitivity_slider.value()))

        # 添加笔刷参数到布局
        brush_layout.addWidget(brush_size_label)
        brush_layout.addWidget(brush_size_slider)
        brush_layout.addWidget(flow_strength_label)
        brush_layout.addWidget(flow_strength_slider)
        brush_layout.addWidget(speed_sensitivity_label)
        brush_layout.addWidget(speed_sensitivity_slider)
        brush_group.setLayout(brush_layout)
        
        # 存储控件引用
        self.controls["brush_size_label"] = brush_size_label
        self.controls["brush_size_slider"] = brush_size_slider
        self.controls["flow_strength_label"] = flow_strength_label
        self.controls["flow_strength_slider"] = flow_strength_slider
        self.controls["speed_sensitivity_label"] = speed_sensitivity_label
        self.controls["speed_sensitivity_slider"] = speed_sensitivity_slider
        
        parent_layout.addWidget(brush_group)

    def _create_mode_group(self, parent_layout):
        """创建模式设置组"""
        mode_group = QGroupBox(translator.tr("mode_settings"))
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(8)

        # 字体
        font = QFont()
        font_size = font.pointSize()
        font.setPointSize(int(font_size * 1.2))

        # 四方连续贴图选项
        seamless_checkbox = QCheckBox(translator.tr("enable_seamless"))
        seamless_checkbox.setFont(font)
        seamless_checkbox.setChecked(False)
        seamless_checkbox.stateChanged.connect(lambda state: self._on_bool_param_changed("seamless_mode", state == Qt.Checked))

        # 预览重复选项
        preview_repeat_checkbox = QCheckBox(translator.tr("enable_preview_repeat"))
        preview_repeat_checkbox.setFont(font)
        preview_repeat_checkbox.setChecked(False)
        preview_repeat_checkbox.stateChanged.connect(lambda state: self._on_bool_param_changed("preview_repeat", state == Qt.Checked))

        # 添加到模式设置布局
        mode_layout.addWidget(seamless_checkbox)
        mode_layout.addWidget(preview_repeat_checkbox)
        mode_group.setLayout(mode_layout)
        
        # 存储控件引用
        self.controls["seamless_checkbox"] = seamless_checkbox
        self.controls["preview_repeat_checkbox"] = preview_repeat_checkbox
        
        parent_layout.addWidget(mode_group)

    def _create_flow_group(self, parent_layout):
        """创建流动效果组"""
        flow_group = QGroupBox(translator.tr("flow_effect_control"))
        flow_layout = QVBoxLayout()
        flow_layout.setSpacing(8)

        # 字体
        font = QFont()
        font_size = font.pointSize()
        font.setPointSize(int(font_size * 1.2))

        # 流动速度控制
        flow_speed_label = QLabel(f"{translator.tr('flow_speed')}: {self.main_window.canvas_widget.flow_speed:.2f}")
        flow_speed_label.setFont(font)
        
        flow_speed_slider = QSlider(Qt.Horizontal)
        flow_speed_slider.setMinimum(1)
        flow_speed_slider.setMaximum(200)
        flow_speed_slider.setValue(int(self.main_window.canvas_widget.flow_speed * 100))
        flow_speed_slider.sliderPressed.connect(lambda: self.main_window._old_param_values.__setitem__("flow_speed", self.main_window.param_registry.read("flow_speed") if self.main_window.param_registry.has_key("flow_speed") else self.main_window.canvas_widget.flow_speed))
        flow_speed_slider.valueChanged.connect(self.main_window.on_flow_speed_changed)
        flow_speed_slider.sliderReleased.connect(lambda: self.main_window.on_flow_speed_changed(flow_speed_slider.value(), True) if hasattr(self.main_window, 'on_flow_speed_changed') else None)

        # 流动距离控制
        flow_distortion_label = QLabel(f"{translator.tr('flow_distance')}: {self.main_window.canvas_widget.flow_distortion:.2f}")
        flow_distortion_label.setFont(font)
        
        flow_distortion_slider = QSlider(Qt.Horizontal)
        flow_distortion_slider.setMinimum(1)
        flow_distortion_slider.setMaximum(100)
        flow_distortion_slider.setValue(int(self.main_window.canvas_widget.flow_distortion * 100))
        flow_distortion_slider.sliderPressed.connect(lambda: self.main_window._old_param_values.__setitem__("flow_distortion", self.main_window.param_registry.read("flow_distortion") if self.main_window.param_registry.has_key("flow_distortion") else self.main_window.canvas_widget.flow_distortion))
        flow_distortion_slider.valueChanged.connect(self.main_window.on_flow_distortion_changed)
        flow_distortion_slider.sliderReleased.connect(lambda: self.main_window.on_flow_distortion_changed(flow_distortion_slider.value(), True) if hasattr(self.main_window, 'on_flow_distortion_changed') else None)

        # 底图缩放控制 (0.5 ~ 4.0)
        base_scale = getattr(self.main_window.canvas_widget, 'base_scale', 1.0)
        base_scale_label = QLabel(f"{translator.tr('base_scale')}: {float(base_scale):.2f}")
        base_scale_label.setFont(font)

        base_scale_slider = QSlider(Qt.Horizontal)
        base_scale_slider.setMinimum(10)   # 0.50
        base_scale_slider.setMaximum(200)  # 4.00
        base_scale_slider.setValue(int(round(float(base_scale) * 100)))

        def on_base_scale_changed(v:int):
            val = float(v) / 100.0
            base_scale_label.setText(f"{translator.tr('base_scale')}: {val:.2f}")
            # 实时应用（transient），松手时入撤销栈
            try:
                self.main_window.param_registry.apply("base_scale", val, transient=True)
                self.main_window.canvas_widget.update()
            except Exception:
                pass

        base_scale_slider.sliderPressed.connect(lambda: self._record_old_value("base_scale"))
        base_scale_slider.valueChanged.connect(on_base_scale_changed)
        base_scale_slider.sliderReleased.connect(lambda: self._commit_param_change("base_scale", base_scale_slider.value() / 100.0))

        # 添加到流动效果布局
        flow_layout.addWidget(flow_speed_label)
        flow_layout.addWidget(flow_speed_slider)
        flow_layout.addWidget(flow_distortion_label)
        flow_layout.addWidget(flow_distortion_slider)
        flow_layout.addWidget(base_scale_label)
        flow_layout.addWidget(base_scale_slider)
        flow_group.setLayout(flow_layout)
        
        # 存储控件引用
        self.controls["flow_speed_label"] = flow_speed_label
        self.controls["flow_speed_slider"] = flow_speed_slider
        self.controls["flow_distortion_label"] = flow_distortion_label
        self.controls["flow_distortion_slider"] = flow_distortion_slider
        self.controls["base_scale_label"] = base_scale_label
        self.controls["base_scale_slider"] = base_scale_slider
        
        parent_layout.addWidget(flow_group)

    def _create_channel_orientation_group(self, parent_layout):
        """创建通道朝向设置组"""
        from app_settings import app_settings
        
        channel_group = QGroupBox(translator.tr("channel_orientation"))
        channel_layout = QVBoxLayout()
        channel_layout.setSpacing(8)

        # 字体
        font = QFont()
        font_size = font.pointSize()
        font.setPointSize(int(font_size * 1.2))

        # R通道反转选项
        invert_r_checkbox = QCheckBox(translator.tr("invert_r_channel"))
        invert_r_checkbox.setFont(font)
        invert_r_checkbox.setChecked(app_settings.invert_r_channel)
        invert_r_checkbox.stateChanged.connect(lambda state: self._on_invert_param_changed("invert_r_channel", state == Qt.Checked))

        # G通道反转选项
        invert_g_checkbox = QCheckBox(translator.tr("invert_g_channel"))
        invert_g_checkbox.setFont(font)
        invert_g_checkbox.setChecked(app_settings.invert_g_channel)
        invert_g_checkbox.stateChanged.connect(lambda state: self._on_invert_param_changed("invert_g_channel", state == Qt.Checked))

        # 当前朝向状态显示
        r_orient = translator.tr("r_channel_inverted") if app_settings.invert_r_channel else translator.tr("r_channel_normal")
        g_orient = translator.tr("g_channel_inverted") if app_settings.invert_g_channel else translator.tr("g_channel_normal")
        orientation_label = QLabel(translator.tr("current_channel_orientation", r_orient=r_orient, g_orient=g_orient))
        orientation_label.setStyleSheet("color: #666666; font-size: 10px;")
        orientation_label.setFont(font)

        # 添加到通道朝向布局
        channel_layout.addWidget(invert_r_checkbox)
        channel_layout.addWidget(invert_g_checkbox)
        channel_layout.addWidget(orientation_label)
        channel_group.setLayout(channel_layout)
        
        # 存储控件引用
        self.controls["invert_r_checkbox"] = invert_r_checkbox
        self.controls["invert_g_checkbox"] = invert_g_checkbox
        self.controls["orientation_label"] = orientation_label
        
        parent_layout.addWidget(channel_group)

    def _create_uv_overlay_group(self, parent_layout):
        """创建UV覆盖设置组（仅3D打开时显示）"""
        from localization import translator
        uv_group = QGroupBox(translator.tr("uv_overlay"))
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # UV Set Selection
        uv_set_label = QLabel(f"{translator.tr('uv_set')}: UV0")
        uv_set_combo = QComboBox()
        uv_set_combo.addItem("UV0")  # Default item
        
        def on_uv_set_changed(index):
            if index >= 0:
                uv_set_name = uv_set_combo.itemText(index)
                uv_set_label.setText(f"{translator.tr('uv_set')}: {uv_set_name}")
                # Apply UV set change through registry
                try:
                    if hasattr(self.main_window, 'param_registry') and self.main_window.param_registry:
                        self.main_window.param_registry.apply("selected_uv_set", index, transient=False)
                    # Update 3D viewport and 2D UV overlay
                    self._update_uv_set_selection(index)
                except Exception as e:
                    print(f"UV set change error: {e}")
        
        uv_set_combo.currentIndexChanged.connect(on_uv_set_changed)
        
        layout.addWidget(uv_set_label)
        layout.addWidget(uv_set_combo)

        # Opacity
        opacity_label = QLabel(f"{translator.tr('uv_opacity')}: 0.70")
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setMinimum(0)
        opacity_slider.setMaximum(100)
        opacity_slider.setValue(int(round(float(getattr(self.main_window.canvas_widget, 'uv_wire_opacity', 0.7)) * 100)))

        def on_opacity_changed(value):
            opacity = value / 100.0
            opacity_label.setText(f"{translator.tr('uv_opacity')}: {opacity:.2f}")
            # 通过注册表应用，支持撤销
            try:
                if hasattr(self.main_window, 'param_registry') and self.main_window.param_registry:
                    self.main_window.param_registry.apply("uv_wire_opacity", opacity, transient=True)
                else:
                    self.main_window.canvas_widget.uv_wire_opacity = float(opacity)
                self.main_window.canvas_widget.update()
            except Exception:
                pass

        opacity_slider.sliderPressed.connect(lambda: self._record_old_value("uv_wire_opacity"))
        opacity_slider.valueChanged.connect(on_opacity_changed)
        opacity_slider.sliderReleased.connect(lambda: self._commit_param_change("uv_wire_opacity", opacity_slider.value() / 100.0))

        # Line width
        width_label = QLabel(f"{translator.tr('uv_line_width')}: 1.00")
        width_slider = QSlider(Qt.Horizontal)
        width_slider.setMinimum(2)   # 1.0 -> 2*0.5
        width_slider.setMaximum(10)  # 5.0 -> 10*0.5
        # map current to scaled integer
        current_lw = float(getattr(self.main_window.canvas_widget, 'uv_wire_line_width', 1.0))
        width_slider.setValue(int(round(current_lw / 0.5)))

        def on_width_changed(v):
            lw = float(v) * 0.5
            width_label.setText(f"{translator.tr('uv_line_width')}: {lw:.2f}")
            try:
                if hasattr(self.main_window, 'param_registry') and self.main_window.param_registry:
                    self.main_window.param_registry.apply("uv_wire_line_width", lw, transient=True)
                else:
                    self.main_window.canvas_widget.uv_wire_line_width = lw
                self.main_window.canvas_widget.update()
            except Exception:
                pass

        width_slider.sliderPressed.connect(lambda: self._record_old_value("uv_wire_line_width"))
        width_slider.valueChanged.connect(on_width_changed)
        width_slider.sliderReleased.connect(lambda: self._commit_param_change("uv_wire_line_width", float(width_slider.value()) * 0.5))

        layout.addWidget(opacity_label)
        layout.addWidget(opacity_slider)
        layout.addWidget(width_label)
        layout.addWidget(width_slider)
        uv_group.setLayout(layout)
        parent_layout.addWidget(uv_group)

        # 记录控件并默认隐藏（由MainWindow在3D开关时显示/隐藏）
        self.controls["uv_group"] = uv_group
        self.controls["uv_set_label"] = uv_set_label
        self.controls["uv_set_combo"] = uv_set_combo
        self.controls["uv_opacity_label"] = opacity_label
        self.controls["uv_opacity_slider"] = opacity_slider
        self.controls["uv_width_label"] = width_label
        self.controls["uv_width_slider"] = width_slider
        uv_group.setVisible(False)

    def _record_old_value(self, key):
        try:
            old = getattr(self.main_window.canvas_widget, key)
            self.main_window._old_param_values[key] = old
        except Exception:
            pass

    def _commit_param_change(self, key, new_value):
        try:
            from commands import ParameterChangeCommand
            old_value = self.main_window._old_param_values.get(key, new_value)
            if hasattr(self.main_window, 'param_registry') and self.main_window.param_registry and self.main_window.param_registry.has_key(key):
                if old_value != new_value:
                    cmd = ParameterChangeCommand(self.main_window.param_registry, key, old_value, new_value)
                    self.main_window.command_mgr.execute_command(cmd)
            else:
                # fallback:直接赋值
                setattr(self.main_window.canvas_widget, key, new_value)
        except Exception as e:
            print(f"commit_param_change error: {e}")

    def _create_overlay_group(self, parent_layout):
        """创建参考贴图设置组"""
        overlay_group = QGroupBox(translator.tr("overlay_settings"))
        layout = QVBoxLayout()
        layout.setSpacing(8)

        font = QFont()
        font_size = font.pointSize()
        font.setPointSize(int(font_size * 1.2))

        opacity_label = QLabel(f"{translator.tr('overlay_opacity')}: 0.5")
        opacity_label.setFont(font)

        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setMinimum(0)
        opacity_slider.setMaximum(100)
        opacity_slider.setValue(50)

        def on_opacity_changed(value):
            opacity = value / 100.0
            opacity_label.setText(f"{translator.tr('overlay_opacity')}: {opacity:.2f}")
            # 预览实时更新，但不入栈
            self.main_window.param_registry.apply("overlay_opacity", opacity, transient=True)

        opacity_slider.sliderPressed.connect(lambda: self._record_overlay_old_opacity())
        opacity_slider.valueChanged.connect(on_opacity_changed)
        opacity_slider.sliderReleased.connect(lambda: self._commit_overlay_opacity(opacity_slider.value()))

        layout.addWidget(opacity_label)
        layout.addWidget(opacity_slider)
        overlay_group.setLayout(layout)

        self.controls["overlay_opacity_label"] = opacity_label
        self.controls["overlay_opacity_slider"] = opacity_slider
        self.controls["overlay_group"] = overlay_group

        parent_layout.addWidget(overlay_group)
        # 默认在未导入参考贴图之前隐藏整个组
        overlay_group.setVisible(False)

    def _on_invert_param_changed(self, key, checked):
        # 使用注册表写入并入栈
        try:
            old = self.main_window.param_registry.read(key)
        except Exception:
            from app_settings import app_settings
            old = getattr(app_settings, 'invert_r_channel' if key == 'invert_r_channel' else 'invert_g_channel')

        self.main_window.param_registry.apply(key, bool(checked), transient=True)
        if old != bool(checked) and self.main_window.param_registry.has_key(key):
            from commands import ParameterChangeCommand
            cmd = ParameterChangeCommand(self.main_window.param_registry, key, bool(old), bool(checked))
            self.main_window.command_mgr.execute_command(cmd)

    def _update_orientation_label(self):
        """更新朝向状态标签"""
        from app_settings import app_settings
        from localization import translator
        
        if "orientation_label" in self.controls:
            r_orient = translator.tr("r_channel_inverted") if app_settings.invert_r_channel else translator.tr("r_channel_normal")
            g_orient = translator.tr("g_channel_inverted") if app_settings.invert_g_channel else translator.tr("g_channel_normal")
            self.controls["orientation_label"].setText(translator.tr("current_channel_orientation", r_orient=r_orient, g_orient=g_orient))

    def _on_bool_param_changed(self, key, checked):
        # 使用注册表写入并入栈
        try:
            old = self.main_window.param_registry.read(key)
        except Exception:
            from app_settings import app_settings
            old = getattr(app_settings, 'seamless_mode' if key == 'seamless_mode' else 'preview_repeat')

        self.main_window.param_registry.apply(key, bool(checked), transient=True)
        if bool(old) != bool(checked) and self.main_window.param_registry.has_key(key):
            from commands import ParameterChangeCommand
            cmd = ParameterChangeCommand(self.main_window.param_registry, key, bool(old), bool(checked))
            self.main_window.command_mgr.execute_command(cmd)

    def _create_fill_controls(self, parent_layout):
        """创建填充画布控件"""
        fill_layout = QHBoxLayout()
        fill_btn = QPushButton(translator.tr("fill_canvas"))
        fill_btn.clicked.connect(self.main_window.fill_canvas)
        
        color_btn = QPushButton()
        color_btn.setFixedSize(32, 32)
        color_btn.setStyleSheet("background-color: rgba(128, 128, 0, 255); border-radius: 4px;")
        color_btn.clicked.connect(self.main_window.choose_fill_color)
        
        fill_layout.addWidget(fill_btn)
        fill_layout.addWidget(color_btn)
        
        # 存储控件引用
        self.controls["fill_button"] = fill_btn
        self.controls["color_button"] = color_btn
        
        parent_layout.addLayout(fill_layout)

    def _create_shortcut_group(self, parent_layout):
        """创建快捷键信息组"""
        shortcut_group = QGroupBox(translator.tr("shortcuts"))
        shortcut_layout = QVBoxLayout()
        
        # 创建快捷键标签
        shortcuts_text = [
            translator.tr("shortcut_left_click"),
            translator.tr("shortcut_right_click"),
            translator.tr("shortcut_middle_drag"),
            translator.tr("shortcut_wheel"),
            translator.tr("shortcut_space"),
            translator.tr("shortcut_ctrl_z"),
            translator.tr("shortcut_ctrl_shift_z"),
            translator.tr("shortcut_alt_horiz"),
            translator.tr("shortcut_alt_vert")
        ]
        
        # 创建快捷键标签
        shortcut_labels = []
        for text in shortcuts_text:
            label = QLabel(text)
            shortcut_labels.append(label)
            shortcut_layout.addWidget(label)
            
        shortcut_group.setLayout(shortcut_layout)
        
        # 存储控件引用
        self.controls["shortcut_labels"] = shortcut_labels
        
        parent_layout.addWidget(shortcut_group)
        
    def get_control(self, name):
        """获取指定名称的控件"""
        return self.controls.get(name)
    
    def _record_overlay_old_opacity(self):
        try:
            self.main_window._old_param_values["overlay_opacity"] = self.main_window.param_registry.read("overlay_opacity")
        except Exception:
            self.main_window._old_param_values["overlay_opacity"] = float(self.main_window.canvas_widget.overlay_opacity)
    
    def _commit_overlay_opacity(self, slider_value):
        new_value = slider_value / 100.0
        old_value = self.main_window._old_param_values.get("overlay_opacity", new_value)
        if abs(old_value - new_value) > 1e-6 and self.main_window.param_registry.has_key("overlay_opacity"):
            from commands import ParameterChangeCommand
            cmd = ParameterChangeCommand(self.main_window.param_registry, "overlay_opacity", old_value, new_value)
            self.main_window.command_mgr.execute_command(cmd)
        
    def update_brush_size_label(self, value):
        """更新笔刷大小标签"""
        if "brush_size_label" in self.controls:
            self.controls["brush_size_label"].setText(f"{translator.tr('brush_size')}: {value}")
            
    def update_flow_strength_label(self, value):
        """更新流动强度标签"""
        if "flow_strength_label" in self.controls:
            self.controls["flow_strength_label"].setText(f"{translator.tr('flow_strength')}: {value:.2f}")
            
    def update_speed_sensitivity_label(self, value):
        """更新速度灵敏度标签"""
        if "speed_sensitivity_label" in self.controls:
            self.controls["speed_sensitivity_label"].setText(f"{translator.tr('speed_sensitivity')}: {value:.2f}")
            
    def update_flow_speed_label(self, value):
        """更新流动速度标签"""
        if "flow_speed_label" in self.controls:
            self.controls["flow_speed_label"].setText(f"{translator.tr('flow_speed')}: {value:.2f}")
            
    def update_flow_distortion_label(self, value):
        """更新流动距离标签"""
        if "flow_distortion_label" in self.controls:
            self.controls["flow_distortion_label"].setText(f"{translator.tr('flow_distance')}: {value:.2f}")
            
    def get_shortcut_labels(self):
        """获取快捷键标签列表"""
        return self.controls.get("shortcut_labels", [])
    
    def update_uv_sets(self, uv_set_names):
        """更新UV集选择下拉框"""
        try:
            combo = self.controls.get("uv_set_combo")
            if combo and uv_set_names:
                combo.blockSignals(True)
                combo.clear()
                for name in uv_set_names:
                    combo.addItem(name)
                combo.setCurrentIndex(0)  # 默认选择第一个UV集
                combo.blockSignals(False)
                
                # 更新标签
                label = self.controls.get("uv_set_label")
                if label and uv_set_names:
                    from localization import translator
                    label.setText(f"{translator.tr('uv_set')}: {uv_set_names[0]}")
        except Exception as e:
            print(f"update_uv_sets error: {e}")
    
    def _update_uv_set_selection(self, uv_set_index):
        """更新UV集选择，通知3D视口和2D覆盖"""
        try:
            # 通知3D视口切换UV集
            if hasattr(self.main_window, '_three_d_widget') and self.main_window._three_d_widget:
                self.main_window._three_d_widget.set_active_uv_set(uv_set_index)
            
            # 更新2D UV覆盖显示
            if hasattr(self.main_window, '_three_d_widget') and self.main_window._three_d_widget:
                uvs, indices = self.main_window._three_d_widget.get_uv_wire_data(uv_set_index)
                if uvs is not None and indices is not None:
                    self.main_window.canvas_widget.set_uv_overlay_data(uvs, indices)
                    self.main_window.canvas_widget.update()
        except Exception as e:
            print(f"_update_uv_set_selection error: {e}") 