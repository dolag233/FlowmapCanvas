"""
面板管理器模块 - 负责创建和管理工具面板
"""

from PyQt5.QtWidgets import (
    QDockWidget, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QSlider, QGroupBox, QCheckBox, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from localization import translator

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

        # 连接信号
        brush_size_slider.valueChanged.connect(self.main_window.on_brush_size_changed)
        flow_strength_slider.valueChanged.connect(self.main_window.on_flow_strength_changed)
        speed_sensitivity_slider.valueChanged.connect(self.main_window.on_speed_sensitivity_changed)

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
        seamless_checkbox.stateChanged.connect(self.main_window.on_seamless_changed)

        # 预览重复选项
        preview_repeat_checkbox = QCheckBox(translator.tr("enable_preview_repeat"))
        preview_repeat_checkbox.setFont(font)
        preview_repeat_checkbox.setChecked(False)
        preview_repeat_checkbox.stateChanged.connect(self.main_window.on_preview_repeat_changed)

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
        flow_speed_slider.valueChanged.connect(self.main_window.on_flow_speed_changed)

        # 流动距离控制
        flow_distortion_label = QLabel(f"{translator.tr('flow_distance')}: {self.main_window.canvas_widget.flow_distortion:.2f}")
        flow_distortion_label.setFont(font)
        
        flow_distortion_slider = QSlider(Qt.Horizontal)
        flow_distortion_slider.setMinimum(1)
        flow_distortion_slider.setMaximum(100)
        flow_distortion_slider.setValue(int(self.main_window.canvas_widget.flow_distortion * 100))
        flow_distortion_slider.valueChanged.connect(self.main_window.on_flow_distortion_changed)

        # 添加到流动效果布局
        flow_layout.addWidget(flow_speed_label)
        flow_layout.addWidget(flow_speed_slider)
        flow_layout.addWidget(flow_distortion_label)
        flow_layout.addWidget(flow_distortion_slider)
        flow_group.setLayout(flow_layout)
        
        # 存储控件引用
        self.controls["flow_speed_label"] = flow_speed_label
        self.controls["flow_speed_slider"] = flow_speed_slider
        self.controls["flow_distortion_label"] = flow_distortion_label
        self.controls["flow_distortion_slider"] = flow_distortion_slider
        
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
        invert_r_checkbox.stateChanged.connect(self._on_invert_r_changed)

        # G通道反转选项
        invert_g_checkbox = QCheckBox(translator.tr("invert_g_channel"))
        invert_g_checkbox.setFont(font)
        invert_g_checkbox.setChecked(app_settings.invert_g_channel)
        invert_g_checkbox.stateChanged.connect(self._on_invert_g_changed)

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

    def _on_invert_r_changed(self, state):
        """处理R通道反转状态变化"""
        from app_settings import app_settings
        app_settings.set_invert_r_channel(state == Qt.Checked)
        app_settings.save_settings()
        self._update_orientation_label()

    def _on_invert_g_changed(self, state):
        """处理G通道反转状态变化"""
        from app_settings import app_settings
        app_settings.set_invert_g_channel(state == Qt.Checked)
        app_settings.save_settings()
        self._update_orientation_label()

    def _update_orientation_label(self):
        """更新朝向状态标签"""
        from app_settings import app_settings
        from localization import translator
        
        if "orientation_label" in self.controls:
            r_orient = translator.tr("r_channel_inverted") if app_settings.invert_r_channel else translator.tr("r_channel_normal")
            g_orient = translator.tr("g_channel_inverted") if app_settings.invert_g_channel else translator.tr("g_channel_normal")
            self.controls["orientation_label"].setText(translator.tr("current_channel_orientation", r_orient=r_orient, g_orient=g_orient))

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