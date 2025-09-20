from PyQt5.QtWidgets import QOpenGLWidget, QMessageBox, QMainWindow
from PyQt5.QtCore import Qt, QPoint, QSize, pyqtSignal, QTimer, QPointF, QSizeF
from PyQt5.QtGui import QMouseEvent, QTabletEvent, QImage, QVector2D, QCursor
from OpenGL.GL import *
from OpenGL.GL import shaders
from OpenGL.error import GLError
from PIL import Image
import numpy as np
import ctypes
import time
import enum
import os

# 鼠标状态枚举，用于优化状态检查
class MouseState(enum.Enum):
    IDLE = 0        # 空闲状态
    DRAWING = 1     # 正常绘制
    ERASING = 2     # 橡皮擦模式
    DRAG_PREVIEW = 3 # 拖拽预览视图
    DRAG_MAIN = 4   # 拖拽主视图

# 笔刷数据类，缓存常用的计算结果
class BrushData:
    def __init__(self):
        self.center_x = 0       # 笔刷中心X坐标
        self.center_y = 0       # 笔刷中心Y坐标
        self.radius = 0         # 笔刷半径
        self.min_x = 0          # 影响区域最小X
        self.max_x = 0          # 影响区域最大X
        self.min_y = 0          # 影响区域最小Y
        self.max_y = 0          # 影响区域最大Y
        self.flow_r = 0.5       # 红色分量
        self.flow_g = 0.5       # 绿色分量
        self.strength = 0.0     # 笔刷强度
        self.needs_seamless = False  # 是否需要四方连续处理
        self.mirror_positions = []   # 需要镜像的位置列表
        self.dist_sq_cache = None    # 距离场缓存
        self.falloff_cache = None    # 衰减系数缓存

# 基础顶点着色器
VERTEX_SHADER_SOURCE = """
#version 150
in vec2 aPos;
in vec2 aTexCoords;

out vec2 TexCoords;

void main()
{
    gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);
    TexCoords = aTexCoords;
}
"""

PREVIEW_FRAGMENT_SHADER_SOURCE = None

# --- Helper Function for Shader Compilation ---
def create_shader_program(vertex_source, fragment_source):
    """编译顶点和片段着色器，并链接成一个程序"""
    try:
        vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(fragment_source, GL_FRAGMENT_SHADER)

        # 注意：PyOpenGL 的 compileProgram 会自动处理附加和链接
        # 它在失败时会引发 RuntimeError，并通常包含日志信息
        program = shaders.compileProgram(vertex_shader, fragment_shader)

        # 编译后可以立即删除着色器对象 (它们已链接到程序中)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)

        print(f"Shader program compiled and linked successfully. ID: {program}")
        return program
    except Exception as e:
        # shaders.compileProgram 会在日志中打印错误，但我们再次打印异常信息
        print(f"Shader compilation/linking failed: {e}")
        # 尝试访问日志（如果存在）
        log = None
        if hasattr(e, 'log') and e.log:
            log = e.log.decode(errors='ignore') # Decode bytes log, ignore errors
            print("--- Shader Log ---")
            print(log)
            print("------------------")
        # 可以尝试更详细地检查哪个阶段失败，但 compileProgram 通常足够
        return 0 # 返回 0 表示失败

class FlowmapCanvas(QOpenGLWidget):
    # 信号，当 flowmap 更新时发出，用于更新预览等
    flowmap_updated = pyqtSignal()
    mouseMoveNonDrawing = pyqtSignal(QPointF)  # 鼠标移动但没有绘制时发出
    drawingStarted = pyqtSignal()  # 开始绘制时发出
    drawingFinished = pyqtSignal()  # 结束绘制时发出
    mouse_moved = pyqtSignal(QPoint)
    resized = pyqtSignal()
    opengl_initialized = pyqtSignal()  # 新增信号，当OpenGL初始化完成时发出
    base_image_loaded = pyqtSignal(int, int)  # 新增信号，当底图加载完成时发出，参数为宽度和高度
    brush_properties_changed = pyqtSignal(float, float)  # 新增信号，当笔刷属性(半径、强度)变化时发出
    hover_entered = pyqtSignal()
    hover_left = pyqtSignal()

    def __init__(self, parent=None, size=(1024, 1024)):
        super().__init__(parent)

        self.texture_size = size
        self.last_pos = QPoint()
        self.mouse_state = MouseState.IDLE  # 使用枚举代替多个布尔标志
        self.brush_radius = 40.0 # 笔刷半径 (像素)
        self.brush_strength = 0.5 # 笔刷强度 [0, 1]
        self.speed_sensitivity = 0.7  # 鼠标速度灵敏度 [0, 1]
        
        # 数位板笔压相关属性
        self.current_pressure = 1.0  # 当前笔压 [0, 1]
        self.pressure_affects_size = True  # 笔压是否影响笔刷大小
        self.pressure_affects_strength = True  # 笔压是否影响笔刷强度
        self.base_brush_radius = 40.0  # 基础笔刷半径（无压感时）
        self.base_brush_strength = 0.5  # 基础笔刷强度（无压感时）
        self.is_tablet_input = False  # 标记当前是否为数位板输入
        
        # 笔压响应参数（可配置）
        self.pressure_size_min = 0.2  # 大小最小值（基础大小的百分比）
        self.pressure_strength_min = 0.2  # 强度最小值（基础强度的百分比）
        self.graphics_api_mode = "opengl"  # 默认使用OpenGL模式 - 'opengl'或'directx'
        self.enable_seamless = False  # 启用四方连续贴图
        self.preview_size = QSizeF(0.2, 0.2)  # 预览窗口的初始大小
        self.preview_offset = QPointF(0.0, 0.0)  # 预览窗口中内容的偏移量（归一化坐标）
        self.preview_repeat = False  # 启用底图重复显示
        self.is_dragging_preview = False  # 拖拽预览视角
        self.last_mouse_pos = QPoint()  # 上一次鼠标位置，用于拖拽预览

        # Shift键状态 - 用于模糊效果
        self.shift_pressed = False
        self.s_pressed = False  # S键状态（用于笔刷调整）
        self.s_press_position = None  # S键按下时的位置
        self.initial_brush_radius = 40.0  # 按下S键时的初始笔刷半径
        self.initial_brush_strength = 0.5  # 按下S键时的初始笔刷强度

        # 绘制优化参数
        self.last_draw_time = 0  # 上次绘制时间
        self.draw_throttle_ms = 16  # 绘制节流时间，约60fps
        self.accumulated_positions = []  # 累积的位置，用于节流期间保存鼠标位置
        self.update_pending = False  # 是否有待处理的更新

        # 主视图控制
        self.main_view_scale = 1.0  # 主视图缩放比例
        self.target_main_view_scale = 1.0  # 目标主视图缩放比例（用于平滑过渡）
        self.main_view_offset = QPointF(0.0, 0.0)  # 主视图偏移量
        self.target_main_view_offset = QPointF(0.0, 0.0)  # 目标主视图偏移量（用于平滑过渡）
        self.is_dragging_main_view = False  # 拖拽主视图标志
        self.scale_animation_active = False  # 缩放动画是否激活
        self.scale_animation_start_time = 0  # 缩放动画开始时间
        self.scale_animation_duration = 0.15  # 缩放动画持续时间（秒）
        self.MAX_SCALE = 20.0  # 最大缩放倍数
        self.MIN_SCALE = 0.05  # 最小缩放倍数
        self.SCROLL_SENSITIVITY = 0.25  # 滚轮灵敏度，值越小越不敏感

        # 纵横比校正参数
        self.texture_original_aspect_ratio = 1.0  # 纹理的原始纵横比
        self.main_view_scale_correction_x = 1.0  # X方向的缩放校正
        self.main_view_scale_correction_y = 1.0  # Y方向的缩放校正
        self.main_view_offset_correction_x = 0.0  # X方向的偏移校正
        self.main_view_offset_correction_y = 0.0  # Y方向的偏移校正
        self.preview_aspect_ratio = 1.0  # 预览窗口的宽高比，默认为1:1
        # cover 模式下的屏幕->内容校正参数（传给shader）
        self.aspect_scale_x = 1.0
        self.aspect_scale_y = 1.0
        self.aspect_offset_x = 0.0
        self.aspect_offset_y = 0.0

        # Flowmap 数据 (H, W, RGBA)
        self.flowmap_data = np.zeros((self.texture_size[1], self.texture_size[0], 4), dtype=np.float32)
        self.flowmap_data[..., 0] = 0.5
        self.flowmap_data[..., 1] = 0.5
        self.flowmap_data[..., 3] = 1.0

        self.flowmap_texture_id = 0
        self.base_texture_id = 0
        self.has_base_map = False

        self.shader_program_id = 0
        self.preview_shader_program_id = 0
        self.overlay_shader_program_id = 0
        self.overlay_texture_id = 0
        self.overlay_opacity = 0.5
        self.has_overlay = False
        # UV overlay state
        self.uv_overlay_tex = 0
        self.uv_overlay_enabled = False
        self.uv_overlay_opacity = 0.7

        self.vao = 0
        self.vbo = 0

        # 顶点数据 (全屏四边形)
        self.quad_vertices = np.array([
            -1.0,  1.0,  0.0, 1.0,
            -1.0, -1.0,  0.0, 0.0,
             1.0,  1.0,  1.0, 1.0,
             1.0, -1.0,  1.0, 0.0,
        ], dtype=np.float32)

        # 3D 模型相关（保留）
        self.uv_data = None
        self.uv_vbo = 0

        # Flow effect parameters
        self.flow_speed = 0.5
        self.flow_distortion = 0.3
        self.base_scale = 1.0
        self.anim_time = 0.0
        self.last_anim_update_time = time.time()
        self.is_animating = True
        self.start_time = time.time()

        # Timer for animation update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.brush_data = BrushData()
        self.is_drawing = False
        self.is_erasing = False
        self.is_dragging_preview = False
        self.is_dragging_main_view = False

        self.uv_wire_program = 0
        self.uv_wire_vao = 0
        self.uv_wire_vbo = 0
        self.uv_wire_ebo = 0
        self.uv_wire_index_count = 0
        self.uv_wire_opacity = 0.7
        self.uv_wire_enabled = False
        self.uv_wire_line_width = 1.0

    def update_animation(self):
        """更新动画状态"""
        current_time = time.time()
        delta_time = current_time - self.last_anim_update_time
        self.last_anim_update_time = current_time

        # 累积动画时间
        self.anim_time += delta_time

        # 处理缩放动画
        if self.scale_animation_active:
            progress = min(1.0, (current_time - self.scale_animation_start_time) / self.scale_animation_duration)
            if progress >= 1.0:
                self.main_view_scale = self.target_main_view_scale
                self.main_view_offset = self.target_main_view_offset
                self.scale_animation_active = False
            else:
                # 使用平滑的缓动函数
                t = progress
                ease = t * t * (3.0 - 2.0 * t)  # 平滑过渡函数

                # 插值当前值和目标值
                self.main_view_scale = self.main_view_scale + (self.target_main_view_scale - self.main_view_scale) * ease

                # 对偏移量进行插值
                self.main_view_offset = QPointF(
                    self.main_view_offset.x() + (self.target_main_view_offset.x() - self.main_view_offset.x()) * ease,
                    self.main_view_offset.y() + (self.target_main_view_offset.y() - self.main_view_offset.y()) * ease
                )

        # 强制每帧更新，确保动画流畅
        self.update()

    def initializeGL(self):
        """初始化OpenGL上下文"""
        try:
            print("Initializing OpenGL context...")
            print("OpenGL Version:", glGetString(GL_VERSION).decode(errors='ignore'))
            print("GLSL Version:", glGetString(GL_SHADING_LANGUAGE_VERSION).decode(errors='ignore'))
            print("Vendor:", glGetString(GL_VENDOR).decode(errors='ignore'))
            print("Renderer:", glGetString(GL_RENDERER).decode(errors='ignore'))
            
            # 设置清空颜色
            glClearColor(0.1, 0.1, 0.1, 1.0)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            # 启用模板缓冲支持
            glClearStencil(0)
        
            # 初始化顶点缓冲对象
            self.init_quad_buffers()
            
            # 初始化纹理
            self.init_textures()
            
            # 初始化着色器
            self.init_shaders()
            
            # 设置初始宽高比
            self.texture_original_aspect_ratio = self.texture_size[0] / self.texture_size[1]
            self.window_width = self.width() or 800
            self.window_height = self.height() or 600
            
            # 更新预览窗口大小
            self.update_preview_size()
            
            # 设置动画计时器
            self.start_time = time.time()
            self.last_anim_update_time = time.time()
            
            # 发送OpenGL初始化完成信号
            self.opengl_initialized.emit()
            
            # 初始化完成后，立即强制更新一次
            self.update_aspect_ratio()
            self.update()

            print("OpenGL initialization completed successfully!")
        except Exception as e:
            print(f"OpenGL initialization error: {e}")
            import traceback
            traceback.print_exc()

    def init_quad_buffers(self):
        # 使用 gl* 函数
        vao_id = glGenVertexArrays(1)
        self.vao = vao_id
        vbo_id = glGenBuffers(1)
        self.vbo = vbo_id

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.quad_vertices.nbytes, self.quad_vertices, GL_STATIC_DRAW)

        # 位置属性 (location = 0)
        # 使用 ctypes.c_void_p 进行偏移
        # sizeof(ctypes.c_float) is 4
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # 纹理坐标属性 (location = 1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))
        glEnableVertexAttribArray(1)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def init_textures(self):
        # 使用 gl* 函数
        # --- Flowmap Texture ---
        texture_id = glGenTextures(1)
        self.flowmap_texture_id = texture_id
        glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)
        # 使用REPEAT模式以支持无缝贴图
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F,
                           self.texture_size[0], self.texture_size[1], 0,
                           GL_RGBA, GL_FLOAT, self.flowmap_data)

        # --- Base Texture (Placeholder) ---
        texture_id = glGenTextures(1)
        self.base_texture_id = texture_id
        glBindTexture(GL_TEXTURE_2D, self.base_texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        white_pixel = np.array([[[128, 128, 128, 255]]], dtype=np.uint8) # Use grey placeholder
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, white_pixel)

        glBindTexture(GL_TEXTURE_2D, 0)

    def load_overlay_image(self, file_path):
        """加载参考贴图到GPU纹理"""
        try:
            self.makeCurrent()
            img = Image.open(file_path).convert('RGBA')
            width, height = img.size
            data = np.array(img, dtype=np.uint8)
            data = np.flipud(data)

            if self.overlay_texture_id == 0:
                self.overlay_texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.overlay_texture_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, 0)

            self.has_overlay = True
            self.doneCurrent()
            self.update()
            return True
        except Exception as e:
            print(f"Failed to load overlay image: {e}")
            try:
                glBindTexture(GL_TEXTURE_2D, 0)
            except:
                pass
            self.has_overlay = False
            self.doneCurrent()
            return False

    def init_shaders(self):
        # 使用辅助函数创建 shader program
        fragShader = ""
        with open("shaders/flow_shader.glsl", encoding="utf-8") as f:
            fragShader = f.read()

        self.shader_program_id = create_shader_program(VERTEX_SHADER_SOURCE, fragShader)
        if self.shader_program_id == 0:
            QMessageBox.critical(self, "Shader Error", "Failed to compile or link shaders. Check console output.")

        # 创建预览 shader（从外部文件加载）
        try:
            with open("shaders/preview_shader.glsl", encoding="utf-8") as f:
                preview_frag_source = f.read()
        except Exception as e:
            print(f"Failed to read preview_shader.glsl: {e}")
            preview_frag_source = None

        if preview_frag_source:
            self.preview_shader_program_id = create_shader_program(VERTEX_SHADER_SOURCE, preview_frag_source)
        else:
            self.preview_shader_program_id = 0
        if self.preview_shader_program_id == 0:
            QMessageBox.critical(self, "Shader Error", "Failed to compile preview shader.")

        # Overlay Texture Shader
        try:
            with open("shaders/overlay_shader.glsl", encoding="utf-8") as f:
                self.overlay_shader_program_id = create_shader_program(VERTEX_SHADER_SOURCE, f.read())
        except Exception as e:
            print(f"Failed to read overlay_texture_shader.glsl: {e}")
            self.overlay_shader_program_id = 0

        # UV wire program
        try:
            with open("shaders/uv_wire_vs.glsl", encoding="utf-8") as f:
                uv_vs = f.read()
            with open("shaders/uv_wire_ps.glsl", encoding="utf-8") as f:
                uv_fs = f.read()
            self.uv_wire_program = create_shader_program(uv_vs, uv_fs)
        except Exception as e:
            print(f"Failed to read UV wire shaders: {e}")
            self.uv_wire_program = 0

    def paintGL(self):
        """绘制OpenGL内容"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # 检查 shader program ID 和 VAO 是否有效
        if self.shader_program_id == 0 or self.preview_shader_program_id == 0 or self.vao == 0:
            return
        # draw main shader full-screen
        try:
            glViewport(0, 0, self.width(), self.height())

            glUseProgram(self.shader_program_id)

            # --- 获取 Uniform 位置并设置 ---
            baseMapLoc = glGetUniformLocation(self.shader_program_id, "baseMap")
            hasBaseMapLoc = glGetUniformLocation(self.shader_program_id, "u_hasBaseMap")
            flowMapLoc = glGetUniformLocation(self.shader_program_id, "flowMap")
            timeLoc = glGetUniformLocation(self.shader_program_id, "u_time")
            speedLoc = glGetUniformLocation(self.shader_program_id, "u_flowSpeed")
            distLoc = glGetUniformLocation(self.shader_program_id, "u_flowDistortion")
            baseScaleLoc = glGetUniformLocation(self.shader_program_id, "u_scale")
            previewRepeatLoc = glGetUniformLocation(self.shader_program_id, "u_previewRepeat")
            mainViewScaleLoc = glGetUniformLocation(self.shader_program_id, "u_mainViewScale")
            mainViewOffsetLoc = glGetUniformLocation(self.shader_program_id, "u_mainViewOffset")
            useDirectX = glGetUniformLocation(self.shader_program_id, "u_useDirectX")

            glActiveTexture(GL_TEXTURE0)
            base_tex_to_bind = self.base_texture_id if self.base_texture_id != 0 else 0
            glBindTexture(GL_TEXTURE_2D, base_tex_to_bind)
            if baseMapLoc != -1:
                glUniform1i(baseMapLoc, 0)
            has_valid_base = self.has_base_map and self.base_texture_id != 0
            if hasBaseMapLoc != -1:
                glUniform1i(hasBaseMapLoc, 1 if has_valid_base else 0)

            glActiveTexture(GL_TEXTURE1)
            flow_tex_to_bind = self.flowmap_texture_id if self.flowmap_texture_id != 0 else 0
            glBindTexture(GL_TEXTURE_2D, flow_tex_to_bind)
            if flowMapLoc != -1:
                glUniform1i(flowMapLoc, 1)

            if timeLoc != -1: glUniform1f(timeLoc, self.anim_time)
            if speedLoc != -1: glUniform1f(speedLoc, self.flow_speed)
            if distLoc != -1: glUniform1f(distLoc, self.flow_distortion)
            if baseScaleLoc != -1: glUniform1f(baseScaleLoc, float(getattr(self, 'base_scale', 1.0)))
            if previewRepeatLoc != -1: glUniform1i(previewRepeatLoc, 1 if self.preview_repeat else 0)
            if mainViewScaleLoc != -1: glUniform1f(mainViewScaleLoc, self.main_view_scale)
            if mainViewOffsetLoc != -1: glUniform2f(mainViewOffsetLoc, self.main_view_offset.x(), self.main_view_offset.y())
            if useDirectX != -1: glUniform1f(useDirectX, 1.0 if self.graphics_api_mode == "directx" else 0.0)
            # 传递cover纵横比校正
            loc_as = glGetUniformLocation(self.shader_program_id, "u_aspectScale")
            if loc_as != -1:
                glUniform2f(loc_as, float(self.aspect_scale_x), float(self.aspect_scale_y))
            loc_ao = glGetUniformLocation(self.shader_program_id, "u_aspectOffset")
            if loc_ao != -1:
                glUniform2f(loc_ao, float(self.aspect_offset_x), float(self.aspect_offset_y))

            glBindVertexArray(self.vao)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            glBindVertexArray(0)
        except GLError as e:
            print(f"Error drawing main pass: {e}")
        finally:
            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, 0)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, 0)
            glUseProgram(0)

        # Draw UV wire overlay (full-screen, over base/flowmap)
        if getattr(self, 'uv_wire_enabled', False) and self.uv_wire_program != 0 and getattr(self, 'uv_wire_index_count', 0) > 0:
            try:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glViewport(0, 0, self.width(), self.height())
                glUseProgram(self.uv_wire_program)
                ms = glGetUniformLocation(self.uv_wire_program, "u_mainViewScale")
                if ms != -1:
                    glUniform1f(ms, self.main_view_scale)
                mo = glGetUniformLocation(self.uv_wire_program, "u_mainViewOffset")
                if mo != -1:
                    glUniform2f(mo, self.main_view_offset.x(), self.main_view_offset.y())
                # 传递cover纵横比校正
                loc_as = glGetUniformLocation(self.uv_wire_program, "u_aspectScale")
                if loc_as != -1:
                    glUniform2f(loc_as, float(self.aspect_scale_x), float(self.aspect_scale_y))
                loc_ao = glGetUniformLocation(self.uv_wire_program, "u_aspectOffset")
                if loc_ao != -1:
                    glUniform2f(loc_ao, float(self.aspect_offset_x), float(self.aspect_offset_y))
                col = glGetUniformLocation(self.uv_wire_program, "u_color")
                if col != -1:
                    glUniform3f(col, 0.95, 0.5, 0.1)
                op = glGetUniformLocation(self.uv_wire_program, "u_opacity")
                if op != -1:
                    glUniform1f(op, float(getattr(self, 'uv_wire_opacity', 0.7)))
                glBindVertexArray(self.uv_wire_vao)
                glLineWidth(float(getattr(self, 'uv_wire_line_width', 1.0)))
                glDrawElements(GL_LINES, int(self.uv_wire_index_count), GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                print(f"Error drawing UV wire: {e}")
            finally:
                glUseProgram(0)
                glDisable(GL_BLEND)

        # draw overlay image (if any) over MAIN VIEW (full-screen), not the small preview
        if self.has_overlay and self.overlay_texture_id != 0 and self.overlay_shader_program_id != 0:
            try:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glViewport(0, 0, self.width(), self.height())
                glUseProgram(self.overlay_shader_program_id)

                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, self.overlay_texture_id)
                loc_tex = glGetUniformLocation(self.overlay_shader_program_id, "overlayMap")
                if loc_tex != -1:
                    glUniform1i(loc_tex, 0)
                loc_op = glGetUniformLocation(self.overlay_shader_program_id, "u_opacity")
                if loc_op != -1:
                    glUniform1f(loc_op, float(self.overlay_opacity))
                loc_ms = glGetUniformLocation(self.overlay_shader_program_id, "u_mainViewScale")
                if loc_ms != -1:
                    glUniform1f(loc_ms, self.main_view_scale)
                loc_mo = glGetUniformLocation(self.overlay_shader_program_id, "u_mainViewOffset")
                if loc_mo != -1:
                    glUniform2f(loc_mo, self.main_view_offset.x(), self.main_view_offset.y())
                loc_rep = glGetUniformLocation(self.overlay_shader_program_id, "u_repeat")
                if loc_rep != -1:
                    glUniform1i(loc_rep, 1 if self.preview_repeat else 0)
                # 传递cover纵横比校正
                loc_as = glGetUniformLocation(self.overlay_shader_program_id, "u_aspectScale")
                if loc_as != -1:
                    glUniform2f(loc_as, float(self.aspect_scale_x), float(self.aspect_scale_y))
                loc_ao = glGetUniformLocation(self.overlay_shader_program_id, "u_aspectOffset")
                if loc_ao != -1:
                    glUniform2f(loc_ao, float(self.aspect_offset_x), float(self.aspect_offset_y))

                glBindVertexArray(self.vao)
                glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
                glBindVertexArray(0)
            except Exception as e:
                print(f"Error drawing reference overlay: {e}")
            finally:
                glUseProgram(0)
                glBindTexture(GL_TEXTURE_2D, 0)
                glDisable(GL_BLEND)

        # draw preview overlay (top-right small viewport) LAST
        pv_w = int(self.preview_size.width() * self.width())
        pv_h = int(self.preview_size.height() * self.height())
        pv_x = int(self.preview_pos.x() * self.width())
        pv_y = int((1.0 - self.preview_pos.y() - self.preview_size.height()) * self.height())
        try:
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glViewport(pv_x, pv_y, pv_w, pv_h)
            glUseProgram(self.preview_shader_program_id)

            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id if self.flowmap_texture_id != 0 else 0)
            loc_flow = glGetUniformLocation(self.preview_shader_program_id, "flowMap")
            if loc_flow != -1:
                glUniform1i(loc_flow, 0)
            loc_off = glGetUniformLocation(self.preview_shader_program_id, "u_previewOffset")
            if loc_off != -1:
                glUniform2f(loc_off, self.preview_offset.x(), self.preview_offset.y())
            loc_rep = glGetUniformLocation(self.preview_shader_program_id, "u_previewRepeat")
            if loc_rep != -1:
                glUniform1i(loc_rep, 1 if self.preview_repeat else 0)

            glBindVertexArray(self.vao)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            glBindVertexArray(0)
        except Exception as e:
            print(f"Error drawing preview overlay: {e}")
        finally:
            glUseProgram(0)
            glBindTexture(GL_TEXTURE_2D, 0)
            glDisable(GL_BLEND)

    def resizeGL(self, w, h):
        """处理窗口大小变化事件。
        取消对widget高度的强制锁定，仅更新视口与内部纵横比校正，
        让画布始终填满分配区域，避免出现外部空白条。"""
        # 检查尺寸有效性
        if w <= 0 or h <= 0:
            return

        # 保存当前窗口尺寸
        self.window_width = w
        self.window_height = h

        # 设置OpenGL视口
        glViewport(0, 0, w, h)

        # 确保纹理宽高比存在
        if not hasattr(self, 'texture_original_aspect_ratio') or self.texture_original_aspect_ratio <= 0:
            if self.texture_size[0] > 0 and self.texture_size[1] > 0:
                self.texture_original_aspect_ratio = self.texture_size[0] / self.texture_size[1]
            else:
                self.texture_original_aspect_ratio = 1.0

        # 计算 cover 模式的纵横比校正（内容填满而不拉伸：多余部分裁剪）
        self._update_cover_aspect()
        # 更新 shader 用的比例校正
        self.update_aspect_ratio()
        self.update_preview_size()
        self.resized.emit()
        self.update()

    def _update_cover_aspect(self):
        """计算屏幕到内容坐标的cover映射参数: Tex' = (Tex - offset)/scale
        目标：内容等比填满widget，超出部分裁剪，不产生拉伸。"""
        tex_w, tex_h = self.texture_size
        if tex_w <= 0 or tex_h <= 0:
            self.aspect_scale_x = self.aspect_scale_y = 1.0
            self.aspect_offset_x = self.aspect_offset_y = 0.0
            return

        win_w = max(1, self.width())
        win_h = max(1, self.height())
        r_tex = float(tex_w) / float(tex_h)
        r_win = float(win_w) / float(win_h)

        if r_win > r_tex:
            # widget 更宽：应左右裁剪，但我们在screen->content中需要把"裁剪轴"的scale放在Y以避免XY反置
            self.aspect_scale_x = 1.0
            self.aspect_scale_y = r_win / r_tex
            self.aspect_offset_x = 0.0
            self.aspect_offset_y = (1.0 - self.aspect_scale_y) * 0.5
        else:
            # widget 更高（更窄）：应上下裁剪，对应将scale放在X
            self.aspect_scale_x = r_tex / r_win
            self.aspect_scale_y = 1.0
            self.aspect_offset_x = (1.0 - self.aspect_scale_x) * 0.5
            self.aspect_offset_y = 0.0

    def wheelEvent(self, event):
        """处理鼠标滚轮事件，用于缩放主视图"""
        # 主视图的缩放 - 以窗口中心为缩放点
        # 调整缩放
        delta = event.angleDelta().y()
        new_scale = self.main_view_scale

        if delta > 0:
            # 放大，但限制最大缩放
            new_scale = min(self.MAX_SCALE, self.main_view_scale * (1.0 + self.SCROLL_SENSITIVITY))
        else:
            # 缩小，但限制最小缩放
            new_scale = max(self.MIN_SCALE, self.main_view_scale / (1.0 + self.SCROLL_SENSITIVITY))

        # 计算窗口中心点并转换为场景坐标
        center_widget = QPoint(self.width() // 2, self.height() // 2)
        center_scene = self.mapToScene(center_widget)

        # 缩放后的新场景坐标应该和缩放前的相同，计算所需的新偏移
        old_offset = self.main_view_offset
        
        # 正确的偏移量计算公式
        new_offset = QPointF(
            old_offset.x() + 0.5 * (1.0/new_scale - 1.0/self.main_view_scale),
            old_offset.y() + 0.5 * (1.0/new_scale - 1.0/self.main_view_scale)
        )

        # 设置目标值，启用平滑过渡
        self.target_main_view_scale = new_scale
        self.target_main_view_offset = new_offset
        self.scale_animation_active = True
        self.scale_animation_start_time = time.time()

        self.update()  # 请求重绘

    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key_Space or event.key() == Qt.Key_F:
            # 空格键或F键重置视图到中心
            self.target_main_view_scale = 1.0
            self.target_main_view_offset = QPointF(0.0, 0.0)
            self.scale_animation_active = True
            self.scale_animation_start_time = time.time()
            self.update()
        elif event.key() == Qt.Key_Shift:
            # 按下Shift键时激活模糊模式
            self.shift_pressed = True
        elif event.key() == Qt.Key_S:
            # 按下S键，标记为笔刷调整模式
            self.s_pressed = True
            
            # 始终使用当前鼠标位置作为S键按下时的位置
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            # 确保位置在widget内
            if self.rect().contains(cursor_pos):
                self.s_press_position = cursor_pos
            else:
                # 如果鼠标不在widget内，使用widget中心作为默认位置
                self.s_press_position = QPoint(self.width() // 2, self.height() // 2)

            # 保存当前笔刷参数作为初始值
            self.initial_brush_radius = self.brush_radius
            self.initial_brush_strength = self.brush_strength

            # 发送鼠标位置信号以更新笔刷预览位置
            self.mouse_moved.emit(self.s_press_position)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """处理键盘释放事件"""
        if event.key() == Qt.Key_Shift:
            # 释放Shift键时关闭模糊模式
            self.shift_pressed = False
        elif event.key() == Qt.Key_S:
            # 释放S键
            self.s_pressed = False
            self.s_press_position = None  # 清除S键按下时的位置
        else:
            super().keyReleaseEvent(event)

    def leaveEvent(self, event):
        """当鼠标离开画布时，强制退出S键调整模式，防止状态卡住"""
        try:
            self.s_pressed = False
            self.s_press_position = None
            # 离开时若正在绘制，结束绘制，防止漂移
            if self.mouse_state == MouseState.DRAWING or self.mouse_state == MouseState.ERASING:
                self.mouse_state = MouseState.IDLE
                self.is_drawing = False
                self.is_erasing = False
                try:
                    self.drawingFinished.emit()
                except Exception:
                    pass
            # 发出离开信号用于隐藏笔刷UI
            try:
                self.hover_left.emit()
            except Exception:
                pass
        except Exception:
            pass
        return super().leaveEvent(event)

    def focusOutEvent(self, event):
        """当画布失去焦点时，强制退出S键调整模式，防止状态卡住"""
        try:
            self.s_pressed = False
            self.s_press_position = None
        except Exception:
            pass
        return super().focusOutEvent(event)

    def enterEvent(self, event):
        try:
            self.hover_entered.emit()
        except Exception:
            pass
        return super().enterEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # 检查鼠标是否在预览区域
        if self.is_in_preview(event.pos()):
            if event.button() == Qt.MiddleButton:
                # 开始拖动预览窗口视角
                self.mouse_state = MouseState.DRAG_PREVIEW
                self.is_dragging_preview = True
                self.last_mouse_pos = event.pos()
                return
        else:
            # 调试打印当前鼠标位置和映射后的场景坐标
            if event.button() == Qt.LeftButton:
                self.debug_coordinates(event.pos())

            if event.button() == Qt.MiddleButton:
                # 开始拖动主视图
                self.mouse_state = MouseState.DRAG_MAIN
                self.is_dragging_main_view = True
                self.last_mouse_pos = event.pos()
                return

        if event.button() == Qt.LeftButton:
            # 标记为鼠标输入
            self.is_tablet_input = False
            # 鼠标事件时重置为最大压力（速度影响会在绘制时动态调整）
            self.current_pressure = 1.0
            self.update_brush_from_pressure()
            
            self.mouse_state = MouseState.DRAWING
            self.is_drawing = True
            self.is_erasing = False
            self.last_pos = event.pos()
            # 发出绘制开始信号
            self.drawingStarted.emit()
            self.apply_brush(event.pos(), event.pos())
            self.update()
            # 在鼠标按下时不发出flowmap_updated信号，只在释放时发出
        elif event.button() == Qt.RightButton:  # 新增右键擦除功能
            # 标记为鼠标输入
            self.is_tablet_input = False
            # 鼠标事件时重置为最大压力
            self.current_pressure = 1.0
            self.update_brush_from_pressure()
            
            self.mouse_state = MouseState.ERASING
            self.is_drawing = True
            self.is_erasing = True
            self.last_pos = event.pos()
            # 发出绘制开始信号
            self.drawingStarted.emit()
            self.apply_brush(event.pos(), event.pos())
            self.update()
            # 在鼠标按下时不发出flowmap_updated信号，只在释放时发出

    def mouseMoveEvent(self, event: QMouseEvent):
        # 处理S键+鼠标移动的快捷键功能 - 优先级最高
        if self.s_pressed and self.s_press_position:
            current_pos = event.pos()

            # 计算与S键按下位置的差值
            delta_x = current_pos.x() - self.s_press_position.x()
            delta_y = current_pos.y() - self.s_press_position.y()

            # 判断移动距离更大的方向，并只应用对应参数的变化
            if abs(delta_x) > abs(delta_y):
                # 水平移动更明显 - 只调整笔刷大小
                scale_factor = 0.1  # 调整灵敏度系数
                new_radius = self.initial_brush_radius + delta_x * scale_factor
                self.brush_radius = max(5.0, min(200.0, new_radius))  # 限制笔刷大小范围
                # 保持强度不变
                self.brush_strength = self.initial_brush_strength
            else:
                # 垂直移动更明显 - 只调整流动强度
                # 向上减小，向下增加，从初始值开始调整
                scale_factor = 0.005  # 调整灵敏度系数
                new_strength = self.initial_brush_strength - delta_y * scale_factor
                self.brush_strength = max(0.01, min(1.0, new_strength))  # 限制强度范围
                # 保持半径不变
                self.brush_radius = self.initial_brush_radius

            # 发出笔刷属性变化信号
            self.brush_properties_changed.emit(self.brush_radius, self.brush_strength)

            # 无论调整哪个参数，发送鼠标位置信号保持笔刷预览在原位
            self.mouse_moved.emit(self.s_press_position)  # 使用 S 按下时的位置而不是 last_pos

            self.update()
            return

        # 使用状态枚举处理不同的鼠标状态
        if self.mouse_state == MouseState.DRAG_PREVIEW:
            current_pos = event.pos()
            delta_x = current_pos.x() - self.last_mouse_pos.x()
            delta_y = current_pos.y() - self.last_mouse_pos.y()

            # 转换为预览窗口的归一化坐标
            dx = delta_x / (self.width() * self.preview_size.width())
            dy = delta_y / (self.height() * self.preview_size.height())

            # 调整偏移量 - 预览窗口在右下角
            self.preview_offset += QPointF(dx, dy)

            self.last_mouse_pos = current_pos
            self.update()
            return
        elif self.mouse_state == MouseState.DRAG_MAIN:
            current_pos = event.pos()
            delta_x = current_pos.x() - self.last_mouse_pos.x()
            delta_y = current_pos.y() - self.last_mouse_pos.y()

            # 转换为归一化坐标的偏移量
            dx = delta_x / self.width()
            dy = delta_y / self.height()

            # 根据当前缩放调整偏移量
            self.main_view_offset += QPointF(dx / self.main_view_scale,
                                         -dy / self.main_view_scale)  # 注意这里修改了符号，使纵向拖拽方向正确

            self.last_mouse_pos = current_pos
            self.update()  # 请求重绘
            return

        # 发送鼠标移动信号，用于更新画笔预览
        if not self.s_pressed:
            pos = QPoint(event.pos().x(), event.pos().y())
            self.mouse_moved.emit(pos)

        # 始终将鼠标位置传递给预览
        scene_pos = self.mapToScene(event.pos())
        self.mouseMoveNonDrawing.emit(scene_pos)

        # 如果正在绘制且没有按下S键，则应用笔刷
        if not self.s_pressed and (self.mouse_state == MouseState.DRAWING or self.mouse_state == MouseState.ERASING) and \
           ((event.buttons() & Qt.LeftButton) or (event.buttons() & Qt.RightButton)):
            current_pos = event.pos()

            # 绘制节流控制 - 限制绘制频率以提高性能
            current_time = time.time() * 1000  # 转换为毫秒
            time_since_last_draw = current_time - self.last_draw_time

            if time_since_last_draw >= self.draw_throttle_ms:
                # 时间间隔足够，执行绘制
                # 使用插值算法填充跳过的点，避免快速绘制时出现断点
                self.apply_brush_with_interpolation(self.last_pos, current_pos)
                self.last_pos = current_pos
                self.last_draw_time = current_time

                # 如果有累积的位置，一并处理掉
                if self.accumulated_positions:
                    self.accumulated_positions = []

                # 更新屏幕
                self.update()
                # 在鼠标移动过程中不发送flowmap_updated信号，减少信号数量
                self.update_pending = False
            else:
                # 累积鼠标位置，等待下次绘制
                self.accumulated_positions.append(current_pos)

                # 如果还没有安排更新，则安排一个
                if not self.update_pending:
                    self.update_pending = True
                    # 计算剩余等待时间
                    remaining_time = max(1, int(self.draw_throttle_ms - time_since_last_draw))
                    # 使用 singleShot 计时器在适当时间后触发更新
                    QTimer.singleShot(remaining_time, self.process_accumulated_positions)

    def process_accumulated_positions(self):
        """处理在节流期间累积的鼠标位置"""
        if not self.accumulated_positions or (self.mouse_state != MouseState.DRAWING and self.mouse_state != MouseState.ERASING):
            self.update_pending = False
            return

        # 取最近的点与上次绘制点之间绘制一条线
        current_pos = self.accumulated_positions[-1]

        # 执行绘制
        self.apply_brush_with_interpolation(self.last_pos, current_pos)
        self.last_pos = current_pos
        self.last_draw_time = time.time() * 1000

        # 清除累积的位置
        self.accumulated_positions = []

        # 更新屏幕
        self.update()
        # 在累积位置处理中不发送flowmap_updated信号
        self.update_pending = False

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件，结束绘制或拖拽操作"""
        # 检查是否处于防重入状态
        if hasattr(self, '_in_release_event') and self._in_release_event:
            return

        # 设置重入防护标志
        self._in_release_event = True

        try:
            # 只处理鼠标左键释放和右键释放事件，对应绘制和擦除状态
            if event.button() == Qt.LeftButton and self.mouse_state == MouseState.DRAWING:
                # 仅在状态为绘制时处理左键释放
                self.mouse_state = MouseState.IDLE
                self.is_drawing = False
                self.is_erasing = False
                # 发出绘制结束信号
                self.drawingFinished.emit()
                
            elif event.button() == Qt.RightButton and self.mouse_state == MouseState.ERASING:
                # 仅在状态为擦除时处理右键释放
                self.mouse_state = MouseState.IDLE
                self.is_drawing = False
                self.is_erasing = False
                # 发出绘制结束信号
                self.drawingFinished.emit()
                
            # 处理中键释放 - 结束拖拽
            elif event.button() == Qt.MiddleButton:
                if self.mouse_state == MouseState.DRAG_PREVIEW:
                    self.is_dragging_preview = False
                    self.mouse_state = MouseState.IDLE
                elif self.mouse_state == MouseState.DRAG_MAIN:
                    self.is_dragging_main_view = False
                    self.mouse_state = MouseState.IDLE

            # 更新画面
            self.update()
        finally:
            # 清除防重入标志
            self._in_release_event = False

    def tabletEvent(self, event: QTabletEvent):
        """处理数位板事件，获取笔压信息"""
        # 标记为数位板输入
        self.is_tablet_input = True
        
        # 获取笔压值 (0.0 - 1.0)
        pressure = event.pressure()
        self.current_pressure = max(0.01, pressure)  # 确保最小压力，避免完全无效果
        
        # 根据笔压更新笔刷参数
        self.update_brush_from_pressure()
        
        # 根据事件类型处理绘制
        if event.type() == QTabletEvent.TabletPress:
            # 数位板按下，开始绘制
            if event.button() == Qt.LeftButton:
                self.mouse_state = MouseState.DRAWING
                self.is_drawing = True
                self.is_erasing = False
                self.last_pos = event.pos()
                self.drawingStarted.emit()
                self.apply_brush(event.pos(), event.pos())
                self.update()
            elif event.button() == Qt.RightButton:
                self.mouse_state = MouseState.ERASING
                self.is_drawing = True
                self.is_erasing = True
                self.last_pos = event.pos()
                self.drawingStarted.emit()
                self.apply_brush(event.pos(), event.pos())
                self.update()
                
        elif event.type() == QTabletEvent.TabletMove:
            # 数位板移动，继续绘制
            if self.is_drawing:
                self.apply_brush_with_interpolation(self.last_pos, event.pos())
                self.last_pos = event.pos()
                self.update()
                
        elif event.type() == QTabletEvent.TabletRelease:
            # 数位板抬起，结束绘制
            if self.is_drawing:
                self.mouse_state = MouseState.IDLE
                self.is_drawing = False
                self.is_erasing = False
                self.drawingFinished.emit()
                self.update()
        
        # 接受事件，防止传递给鼠标事件处理
        event.accept()
    
    def update_brush_from_pressure(self):
        """根据当前笔压更新笔刷参数"""
        # 只在数位板输入模式下影响大小
        if self.pressure_affects_size and self.is_tablet_input:
            # 笔压影响大小：使用可配置的最小值
            size_range = 1.0 - self.pressure_size_min
            size_factor = self.pressure_size_min + size_range * self.current_pressure
            self.brush_radius = self.base_brush_radius * size_factor
        else:
            # 鼠标模式下保持基础大小
            self.brush_radius = self.base_brush_radius
        
        if self.pressure_affects_strength:
            # 笔压影响强度：使用可配置的最小值
            strength_range = 1.0 - self.pressure_strength_min
            strength_factor = self.pressure_strength_min + strength_range * self.current_pressure
            self.brush_strength = self.base_brush_strength * strength_factor

    def apply_brush_with_interpolation(self, last_widget_pos, current_widget_pos, explicit_flow_dir=None):
        """
        带插值的笔刷绘制，解决快速绘制时出现断点的问题
        在两个点之间进行线性插值，确保绘制的连续性
        """
        # 计算两点间的距离
        dx = current_widget_pos.x() - last_widget_pos.x()
        dy = current_widget_pos.y() - last_widget_pos.y()
        distance = np.sqrt(dx*dx + dy*dy)
        
        # 根据笔刷半径确定插值步长
        # 步长约为笔刷半径的一半，确保有足够的重叠
        step_size = max(1.0, self.brush_radius * 0.5)
        
        # 如果距离小于步长，直接绘制
        if distance <= step_size:
            self.apply_brush(last_widget_pos, current_widget_pos, explicit_flow_dir)
            return
        
        # 计算需要插值的点数
        num_steps = int(np.ceil(distance / step_size))
        
        # 进行线性插值绘制
        for i in range(num_steps + 1):
            t = i / num_steps if num_steps > 0 else 0
            
            # 线性插值计算当前点
            interp_x = last_widget_pos.x() + dx * t
            interp_y = last_widget_pos.y() + dy * t
            interp_pos = QPoint(int(interp_x), int(interp_y))
            
            # 为每个插值点计算前一个点（用于流向计算）
            if i == 0:
                prev_pos = last_widget_pos
            else:
                prev_t = (i - 1) / num_steps if num_steps > 0 else 0
                prev_x = last_widget_pos.x() + dx * prev_t
                prev_y = last_widget_pos.y() + dy * prev_t
                prev_pos = QPoint(int(prev_x), int(prev_y))
            
            # 绘制插值点
            self.apply_brush(prev_pos, interp_pos, explicit_flow_dir)

    def apply_brush(self, last_widget_pos, current_widget_pos, explicit_flow_dir=None):
        """
        应用笔刷效果到纹理上，处理常规绘制和四方连续绘制
        优化版本：使用笔刷数据缓存、局部纹理更新和向量化操作
        
        Args:
            last_widget_pos: 上一个窗口坐标位置
            current_widget_pos: 当前窗口坐标位置
            explicit_flow_dir: 显式的flow方向(2D numpy数组)，用于3D无缝绘制
        """
        # 检查窗口和纹理尺寸是否有效
        widget_size = self.size()
        w_width = widget_size.width()
        w_height = widget_size.height()
        if w_width <= 0 or w_height <= 0: return

        tex_h, tex_w = self.texture_size[1], self.texture_size[0]
        if tex_w <= 0 or tex_h <= 0: return

        # 将窗口坐标转换为场景坐标（纹理空间）
        last_pos_scene = self.mapToScene(last_widget_pos)
        current_pos_scene = self.mapToScene(current_widget_pos)

        # 允许在预览区域上绘制（仅在中键拖拽时才进入预览拖动逻辑）

        # 四方连续模式下，对坐标取模确保在[0,1]范围内
        if self.enable_seamless:
            # 使用取模操作处理坐标，确保它们落在[0,1]范围内
            current_pos_scene = QPointF(
                current_pos_scene.x() - np.floor(current_pos_scene.x()),
                current_pos_scene.y() - np.floor(current_pos_scene.y())
            )
            last_pos_scene = QPointF(
                last_pos_scene.x() - np.floor(last_pos_scene.x()),
                last_pos_scene.y() - np.floor(last_pos_scene.y())
            )
        # 非四方连续模式下，检查是否超出有效范围
        elif (current_pos_scene.x() < 0 or current_pos_scene.x() > 1.0 or
              current_pos_scene.y() < 0 or current_pos_scene.y() > 1.0):
            return  # 不绘制超出纹理范围的部分

        # 转换到纹理像素坐标
        # shader 和 OpenGL 纹理都使用左上角为原点(0,0)的坐标系
        center_x_tex = int(current_pos_scene.x() * tex_w)
        center_y_tex = int(current_pos_scene.y() * tex_h)  # 不需要翻转，因为 shader 使用的是 Y 轴向下的坐标系

        # 计算流向向量
        if explicit_flow_dir is not None:
            # 使用3D无缝绘制提供的显式flow方向（已经在切线空间中正确编码）
            # 修改：与2D新的符号约定保持一致（向右为正）
            flow_x = explicit_flow_dir[0] * 100.0   # 向右移动表示材质向右流动
            flow_y = -explicit_flow_dir[1] * 100.0  # Y轴保持原有的负号约定
        else:
            # 传统方式：基于两点间的差值计算
            delta_x_scene = current_pos_scene.x() - last_pos_scene.x()
            delta_y_scene = current_pos_scene.y() - last_pos_scene.y()

            # 四方连续模式下处理跨边界的情况（例如从右边缘到左边缘）
            if self.enable_seamless:
                # 如果横向差值大于0.5，表示跨越了水平边界
                if abs(delta_x_scene) > 0.5:
                    delta_x_scene = -np.sign(delta_x_scene) * (1.0 - abs(delta_x_scene))
                # 如果纵向差值大于0.5，表示跨越了垂直边界
                if abs(delta_y_scene) > 0.5:
                    delta_y_scene = -np.sign(delta_y_scene) * (1.0 - abs(delta_y_scene))

            # 计算流向在纹理空间的大小
            flow_x = delta_x_scene * tex_w   # 修改：向右移动表示材质向右流动（默认反转R通道）
            flow_y = -delta_y_scene * tex_h  # 修改：使用负号确保 Y 轴方向一致

        # 测试输出当前位置和转换后的纹理坐标，用于调试
        # print(f"Scene: ({current_pos_scene.x():.3f}, {current_pos_scene.y():.3f}) -> Texture: ({center_x_tex}, {center_y_tex})")
        # print(f"Flow vector: ({flow_x:.3f}, {flow_y:.3f})")

        # 检查是否处于模糊模式（按住Shift键）
        is_blur_mode = self.shift_pressed

        # 对于模糊模式，我们不需要检查流向量大小，因为不是基于移动量绘制
        if not is_blur_mode:
            # 检查流向量是否太小（避免过小移动产生的噪声）
            length_sq = flow_x**2 + flow_y**2
            min_length_sq = (0.1)**2  # 最小阈值
            
            # 在鼠标模式下，根据速度调整current_pressure来影响强度
            if not self.is_tablet_input:
                # 特殊处理：如果是第一个点（last_pos == current_pos），使用中等压力
                if length_sq < min_length_sq:
                    if last_widget_pos == current_widget_pos:
                        self.current_pressure = 0
                        
                        # 避免除零错误
                        flow_x = 0.0
                        flow_y = 0.001
                    else:
                        # 移动距离太小，跳过绘制
                        return
                else:
                    # 根据移动速度调整current_pressure
                    # 计算原始速度因子 (0-1)
                    raw_speed_factor = min(1.0, np.sqrt(length_sq) / 100.0)
                    
                    # 修正速度感应逻辑：快速绘制时压力大，慢速绘制时压力小
                    if self.speed_sensitivity < 0.01:  # 接近0时，固定压力
                        self.current_pressure = 1.0
                    else:
                        # 正确的映射：快速时压力大，慢速时压力小
                        min_factor = (1.0 - self.speed_sensitivity) * 0.8  # 更激进的衰减
                        self.current_pressure = min_factor + (1.0 - min_factor) * raw_speed_factor
                
                # 根据新的压力值更新笔刷强度
                self.update_brush_from_pressure()
            
            # 处理流向向量标准化
            if length_sq < min_length_sq:
                # 已在上面处理了第一个点的情况
                pass
            else:

                # 标准化流向向量
                length = np.sqrt(length_sq)
                if length > 1e-8:  # 避免除零错误
                    flow_x /= length
                    flow_y /= length
                else:
                    # 极小的移动，使用默认方向
                    flow_x = 0.0
                    flow_y = 0.01

            # 根据API模式和擦除状态计算流向颜色
            if self.is_erasing or self.mouse_state == MouseState.ERASING:
                # 擦除模式：设为中性值(0.5,0.5)
                flow_color_r = 0.5
                flow_color_g = 0.5
            else:
                # 正常绘制模式：根据流向方向计算颜色
                flow_color_r = np.clip((flow_x + 1.0) * 0.5, 0.0, 1.0)
                flow_color_g = np.clip((flow_y + 1.0) * 0.5, 0.0, 1.0)
        else:
            # 模糊模式：强度决定模糊程度（使用当前笔刷强度）
            # 模糊模式下不设置特定的流向颜色，而是通过对周围像素进行平均来实现模糊
            flow_color_r = 0.0  # 这个值会在模糊处理中被忽略
            flow_color_g = 0.0  # 这个值会在模糊处理中被忽略

        # 输出调试信息 - 启用调试信息，帮助理解坐标映射
        # print(f"Widget pos: ({current_widget_pos.x()}, {current_widget_pos.y()}) -> Scene: ({current_pos_scene.x():.3f}, {current_pos_scene.y():.3f})")
        # print(f"Center tex: ({center_x_tex}, {center_y_tex}), Flow: ({flow_x:.2f}, {flow_y:.2f}) -> Color: ({flow_color_r:.2f}, {flow_color_g:.2f})")

        # 计算笔刷影响区域
        radius_tex = self.brush_radius
        min_x = max(0, int(center_x_tex - radius_tex))
        max_x = min(tex_w, int(center_x_tex + radius_tex) + 1)
        min_y = max(0, int(center_y_tex - radius_tex))
        max_y = min(tex_h, int(center_y_tex + radius_tex) + 1)

        if min_x >= max_x or min_y >= max_y: return

        # 检查是否需要处理四方连续绘制（笔刷与边缘重叠的情况）
        needs_seamless = self.enable_seamless and (
            center_x_tex - radius_tex < 0 or
            center_x_tex + radius_tex >= tex_w or
            center_y_tex - radius_tex < 0 or
            center_y_tex + radius_tex >= tex_h
        )

        # 填充笔刷数据缓存
        self.brush_data.center_x = center_x_tex
        self.brush_data.center_y = center_y_tex
        self.brush_data.radius = radius_tex
        self.brush_data.min_x = min_x
        self.brush_data.max_x = max_x
        self.brush_data.min_y = min_y
        self.brush_data.max_y = max_y
        self.brush_data.flow_r = flow_color_r
        self.brush_data.flow_g = flow_color_g
        self.brush_data.strength = self.brush_strength
        self.brush_data.needs_seamless = needs_seamless

        # 局部修改区域列表，用于跟踪需要更新的纹理区域
        modified_regions = []

        # 使用try-finally确保纹理始终被正确解绑
        try:
            # 应用主笔刷效果
            self.apply_brush_effect_optimized(min_x, max_x, min_y, max_y, center_x_tex, center_y_tex,
                              radius_tex, flow_color_r, flow_color_g, self.brush_strength)
            modified_regions.append((min_x, min_y, max_x - min_x, max_y - min_y))

            # 只有在四方连续模式下且笔刷与边缘重叠时才应用四方连续效果
            if needs_seamless:
                seamless_regions = self.apply_seamless_brush_all_directions_optimized(center_x_tex, center_y_tex, radius_tex,
                                                flow_color_r, flow_color_g, self.brush_strength)
                modified_regions.extend(seamless_regions)

            # 更新GPU上的纹理数据
            if self.flowmap_texture_id == 0:
                print("Error: Flowmap texture not initialized.")
                return

            glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)

            # 使用部分纹理更新而不是更新整个纹理
            if len(modified_regions) <= 3:  # 少量区域时使用局部更新
                for region in modified_regions:
                    x, y, width, height = region
                    # 确保有效范围
                    if width <= 0 or height <= 0:
                        continue

                    # 确保数据连续存储
                    update_data = self.flowmap_data[y:y+height, x:x+width]
                    if not update_data.flags['C_CONTIGUOUS']:
                        update_data = np.ascontiguousarray(update_data)

                    # 局部更新纹理
                    glTexSubImage2D(GL_TEXTURE_2D, 0, x, y, width, height,
                                  GL_RGBA, GL_FLOAT, update_data)
            else:
                # 区域过多时更新整个纹理更高效
                # 确保数据连续存储
                if not self.flowmap_data.flags['C_CONTIGUOUS']:
                    update_data = np.ascontiguousarray(self.flowmap_data)
                else:
                    update_data = self.flowmap_data

                # 更新整个纹理
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, tex_w, tex_h,
                              GL_RGBA, GL_FLOAT, update_data)

        except GLError as e:
             print(f"OpenGL Error during glTexSubImage2D: {e}")
        except Exception as e:
             print(f"Error during brush application: {e}")
        finally:
             # 确保纹理解绑
             if self.flowmap_texture_id != 0:
                  glBindTexture(GL_TEXTURE_2D, 0)

    def apply_brush_effect_optimized(self, min_x, max_x, min_y, max_y, center_x, center_y, radius, flow_r, flow_g, strength):
        """
        优化版本的笔刷应用函数，使用向量化和预计算
        """
        # 防御性检查，确保坐标有效
        if min_x >= max_x or min_y >= max_y:
            return

        tex_h, tex_w = self.texture_size[1], self.texture_size[0]
        if tex_w <= 0 or tex_h <= 0 or min_x < 0 or min_y < 0 or max_x > tex_w or max_y > tex_h:
            return

        # 提取子区域进行处理 - 使用视图而不是复制以提高性能
        sub_region = self.flowmap_data[min_y:max_y, min_x:max_x]

        # 区域的高度和宽度
        h, w = sub_region.shape[0], sub_region.shape[1]

        # 1. 创建笔刷强度矩阵和距离场

        # 计算 y, x 网格的坐标点
        y_indices, x_indices = np.ogrid[:h, :w]

        # 调整为相对于笔刷中心的坐标
        y_coords = y_indices + min_y - center_y
        x_coords = x_indices + min_x - center_x

        # 计算距离的平方 (距离场)
        dist_sq = x_coords**2 + y_coords**2

        # 应用平滑的回落(falloff)函数 - 使用二次函数使边缘更平滑
        radius_sq = radius**2
        # 将距离转换为 0-1 范围的回落值，超出半径的部分为0
        falloff = np.maximum(0, 1.0 - dist_sq / radius_sq)
        # 使用平方来让衰减更加平滑
        falloff = falloff**2

        # 将强度矩阵限制在笔刷半径内
        strength_mask = falloff * strength

        # 检查是否处于模糊模式
        if self.shift_pressed:
            # 模糊模式 - 进行局部平均
            # 为每个像素创建一个模糊核心，基于距离场和强度
            blur_result = np.zeros_like(sub_region[:,:,:2])  # 只需处理RG通道

            # 对每个受影响的像素，计算周围像素的加权平均
            # 这是一个简化的实现，实际上可以使用高斯模糊或其他更高效的算法
            for y in range(h):
                for x in range(w):
                    if falloff[y, x] > 0.01:  # 只处理受影响的像素
                        # 定义一个小的采样窗口
                        sample_radius = max(1, int(radius * 0.2))  # 采样半径为笔刷半径的20%
                        sample_min_y = max(0, y - sample_radius)
                        sample_max_y = min(h, y + sample_radius + 1)
                        sample_min_x = max(0, x - sample_radius)
                        sample_max_x = min(w, x + sample_radius + 1)

                        # 提取采样窗口
                        sample_window = sub_region[sample_min_y:sample_max_y, sample_min_x:sample_max_x, :2]

                        # 计算加权平均
                        if sample_window.size > 0:  # 确保窗口不为空
                            avg_color = np.mean(sample_window, axis=(0, 1))
                            current_color = sub_region[y, x, :2]
                            # 根据强度渐进地应用模糊效果
                            blend_factor = strength_mask[y, x]
                            blur_result[y, x] = current_color * (1 - blend_factor) + avg_color * blend_factor

            # 应用模糊结果到子区域
            sub_region[:, :, 0] = np.where(falloff[:, :] > 0.01, blur_result[:, :, 0], sub_region[:, :, 0])
            sub_region[:, :, 1] = np.where(falloff[:, :] > 0.01, blur_result[:, :, 1], sub_region[:, :, 1])
        else:
            # 2. 正常绘制模式 - 应用笔刷颜色
            # 将颜色值整形为与子区域匹配的形状，以便进行向量化操作
            flow_r_array = np.full((h, w), flow_r)
            flow_g_array = np.full((h, w), flow_g)

            # 使用线性混合公式: result = original * (1 - alpha) + new_color * alpha
            # 其中alpha是强度掩码
            sub_region[:, :, 0] = sub_region[:, :, 0] * (1 - strength_mask) + flow_r_array * strength_mask
            sub_region[:, :, 1] = sub_region[:, :, 1] * (1 - strength_mask) + flow_g_array * strength_mask

    def apply_seamless_brush_all_directions_optimized(self, center_x, center_y, radius, flow_r, flow_g, strength):
        """
        优化版的四方连续绘制，返回修改区域列表用于局部纹理更新
        性能优化：
        1. 预先计算所有镜像位置
        2. 批量处理镜像位置
        3. 使用向量化操作代替循环
        4. 返回修改区域列表，用于局部纹理更新
        """
        tex_h, tex_w = self.texture_size[1], self.texture_size[0]
        modified_regions = []

        # 检查笔刷与边缘的关系
        brush_min_x = center_x - radius
        brush_max_x = center_x + radius
        brush_min_y = center_y - radius
        brush_max_y = center_y + radius

        # 确定需要哪些镜像位置 - 使用布尔运算加速
        need_left_mirror = brush_min_x < 0
        need_right_mirror = brush_max_x >= tex_w
        need_top_mirror = brush_min_y < 0
        need_bottom_mirror = brush_max_y >= tex_h

        # 快速检查：如果不需要任何镜像，直接返回
        if not (need_left_mirror or need_right_mirror or need_top_mirror or need_bottom_mirror):
            return []

        # 使用列表推导式批量创建镜像位置
        mirror_positions = []

        # 边缘镜像
        if need_right_mirror:
            mirror_positions.append((center_x - tex_w, center_y))
        if need_left_mirror:
            mirror_positions.append((center_x + tex_w, center_y))
        if need_bottom_mirror:
            mirror_positions.append((center_x, center_y - tex_h))
        if need_top_mirror:
            mirror_positions.append((center_x, center_y + tex_h))

        # 角落镜像 - 使用布尔逻辑组合加速
        corner_mirrors = [
            (need_left_mirror and need_top_mirror, (center_x + tex_w, center_y + tex_h)),
            (need_right_mirror and need_top_mirror, (center_x - tex_w, center_y + tex_h)),
            (need_left_mirror and need_bottom_mirror, (center_x + tex_w, center_y - tex_h)),
            (need_right_mirror and need_bottom_mirror, (center_x - tex_w, center_y - tex_h))
        ]

        mirror_positions.extend([pos for needed, pos in corner_mirrors if needed])

        # 缓存镜像位置列表
        self.brush_data.mirror_positions = mirror_positions

        # 批量处理所有镜像位置 - 计算一次半径的平方
        radius_sq = radius * radius
        int_radius = int(radius)

        # 对每个需要的镜像位置应用笔刷效果
        for mirror_x, mirror_y in mirror_positions:
            # 快速有效范围检查 - 使用整数运算
            if mirror_x < -int_radius or mirror_x >= tex_w + int_radius or mirror_y < -int_radius or mirror_y >= tex_h + int_radius:
                continue

            # 计算笔刷区域范围 - 采用整数边界
            min_x = max(0, int(mirror_x - radius))
            max_x = min(tex_w, int(mirror_x + radius) + 1)
            min_y = max(0, int(mirror_y - radius))
            max_y = min(tex_h, int(mirror_y + radius) + 1)

            # 快速跳过无效区域
            if min_x >= max_x or min_y >= max_y:
                continue

            # 使用优化版应用笔刷效果
            self.apply_brush_effect_optimized(min_x, max_x, min_y, max_y, mirror_x, mirror_y,
                            radius, flow_r, flow_g, strength)

            # 添加修改区域
            modified_regions.append((min_x, min_y, max_x - min_x, max_y - min_y))

        return modified_regions

    def load_base_image(self, file_path):
        """加载底图纹理"""
        try:
            # 确保有效的 OpenGL 上下文
            self.makeCurrent()

            # 加载图像
            img = Image.open(file_path).convert('RGBA')
            width, height = img.size
            print(f"Loading base image: {file_path}, size: {width}x{height}")
            
            # 保存原始图像尺寸
            self.original_image_size = (width, height)
            
            # 更新纹理大小以匹配图像尺寸
            self.texture_size = (width, height)
            
            # 获取图像数据
            img_data = np.array(img, dtype=np.uint8)
            
            # 翻转Y轴，确保在OpenGL中正确显示
            img_data = np.flipud(img_data)
            
            # 重新初始化flowmap数据以匹配新的图像尺寸
            self.flowmap_data = np.zeros((height, width, 4), dtype=np.float32)
            self.flowmap_data[..., 0] = 0.5  # 初始化为 (0, 0) 向量 -> (0.5, 0.5) 颜色
            self.flowmap_data[..., 1] = 0.5
            self.flowmap_data[..., 3] = 1.0  # Alpha

            # 如果基础纹理已存在，则删除原纹理
            if self.base_texture_id != 0:
                try:
                    glDeleteTextures(1, [self.base_texture_id])
                    print(f"Deleted existing base texture: {self.base_texture_id}")
                except GLError as e:
                    print(f"Warning: Failed to delete existing texture: {e}")
                self.base_texture_id = 0
                
            # 如果flowmap纹理已存在，也需要更新其大小
            if self.flowmap_texture_id != 0:
                try:
                    glDeleteTextures(1, [self.flowmap_texture_id])
                    print(f"Deleted existing flowmap texture due to size change")
                except GLError as e:
                    print(f"Warning: Failed to delete existing flowmap texture: {e}")
                self.flowmap_texture_id = 0

            # 创建新的底图纹理对象
            texture_id = glGenTextures(1)
            self.base_texture_id = texture_id

            if self.base_texture_id == 0:
                print("Error: Failed to generate base texture ID.")
                QMessageBox.critical(self, "OpenGL Error", "Failed to create texture object.")
                self.doneCurrent()
                return

            print(f"Created new base texture ID: {self.base_texture_id}")

            # 上传底图纹理数据
            try:
                glBindTexture(GL_TEXTURE_2D, self.base_texture_id)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                                GL_RGBA, GL_UNSIGNED_BYTE, img_data)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                # 检查上传是否成功
                error = glGetError()
                if error != GL_NO_ERROR:
                    print(f"OpenGL error after texture upload: {error}")
                    raise GLError(error, "Texture upload failed")
            except GLError as e:
                print(f"OpenGL error loading base image data: {e}")
                QMessageBox.critical(self, "OpenGL Error", f"Failed to load base image data: {e}")
                self.has_base_map = False
                if self.base_texture_id != 0:
                    glDeleteTextures(1, [self.base_texture_id])
                    self.base_texture_id = 0
                self.doneCurrent()
                return
            finally:
                glBindTexture(GL_TEXTURE_2D, 0)
                
            # 创建新的flowmap纹理
            flow_texture_id = glGenTextures(1)
            self.flowmap_texture_id = flow_texture_id
            
            if self.flowmap_texture_id == 0:
                print("Error: Failed to generate flowmap texture ID.")
                QMessageBox.critical(self, "OpenGL Error", "Failed to create flowmap texture object.")
                self.doneCurrent()
                return
                
            # 上传flowmap纹理数据
            try:
                glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0,
                             GL_RGBA, GL_FLOAT, self.flowmap_data)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                
                # 检查上传是否成功
                error = glGetError()
                if error != GL_NO_ERROR:
                    print(f"OpenGL error after flowmap texture upload: {error}")
                    raise GLError(error, "Flowmap texture upload failed")
            except GLError as e:
                print(f"OpenGL error creating flowmap texture: {e}")
                QMessageBox.critical(self, "OpenGL Error", f"Failed to create flowmap texture: {e}")
                if self.flowmap_texture_id != 0:
                    glDeleteTextures(1, [self.flowmap_texture_id])
                    self.flowmap_texture_id = 0
            finally:
                glBindTexture(GL_TEXTURE_2D, 0)

            # 设置标志并发送信号
            self.has_base_map = True

            # 更新预览窗口大小
            self.update_preview_size()

            # 加载图像后更新纵横比校正
            self.update_aspect_ratio()

            self.doneCurrent() # 释放OpenGL上下文
            self.update() # 重绘

            # 发出信号通知外部底图已加载，传递图像的宽高
            self.base_image_loaded.emit(width, height)

        except Exception as e:
            print(f"Error loading base image: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Import Error", f"Failed to load base image: {e}")
            self.doneCurrent() # 确保释放OpenGL上下文

    def import_flowmap(self, file_path, target_size=None, use_bilinear=True, invert_r=False, invert_g=False):
        """
        导入Flowmap从图像文件
        
        参数:
        file_path -- 导入文件的路径
        target_size -- 目标尺寸元组(width, height)，如果None则使用当前纹理尺寸
        use_bilinear -- 如果需要缩放，是否使用双线性插值(True)或最近邻(False)
        invert_r -- 是否反转R通道
        invert_g -- 是否反转G通道
        """
        try:
            from PIL import Image
            import numpy as np
            import os
            
            # 确保有效的 OpenGL 上下文
            self.makeCurrent()
            
            # 加载图像
            img = Image.open(file_path).convert('RGB')
            width, height = img.size
            print(f"Importing flowmap: {file_path}, size: {width}x{height}")
            
            # 获取图像数据
            img_data = np.array(img, dtype=np.uint8)
            
            # 提取R和G通道
            r_channel = img_data[..., 0].astype(np.float32) / 255.0
            g_channel = img_data[..., 1].astype(np.float32) / 255.0
            
            # 应用通道反转
            if invert_r:
                r_channel = 1.0 - r_channel
            if invert_g:
                g_channel = 1.0 - g_channel
            
            # 如果指定了目标尺寸且与当前尺寸不同，则进行缩放
            if target_size and (width, height) != target_size:
                if use_bilinear:
                    # 使用双线性插值
                    resample_method = Image.BILINEAR
                else:
                    # 使用最近邻插值
                    resample_method = Image.NEAREST
                
                img = img.resize(target_size, resample_method)
                width, height = target_size
                print(f"已将图像从 {img_data.shape[1]}x{img_data.shape[0]} 缩放到 {width}x{height} 使用{resample_method}")
                
                # 重新获取缩放后的数据
                img_data = np.array(img, dtype=np.uint8)
                r_channel = img_data[..., 0].astype(np.float32) / 255.0
                g_channel = img_data[..., 1].astype(np.float32) / 255.0
                
                # 重新应用通道反转
                if invert_r:
                    r_channel = 1.0 - r_channel
                if invert_g:
                    g_channel = 1.0 - g_channel
            
            # 更新纹理大小以匹配图像尺寸
            self.texture_size = (width, height)
            
            # 翻转Y轴以匹配OpenGL坐标系（与导出时的操作相反）
            r_channel = np.flipud(r_channel)
            g_channel = np.flipud(g_channel)
            
            # 创建新的flowmap数据
            self.flowmap_data = np.zeros((height, width, 4), dtype=np.float32)
            self.flowmap_data[..., 0] = r_channel  # R通道
            self.flowmap_data[..., 1] = g_channel  # G通道
            self.flowmap_data[..., 3] = 1.0  # Alpha
            
            # 如果flowmap纹理已存在，则删除原纹理
            if self.flowmap_texture_id != 0:
                try:
                    glDeleteTextures(1, [self.flowmap_texture_id])
                    print(f"Deleted existing flowmap texture: {self.flowmap_texture_id}")
                except GLError as e:
                    print(f"Warning: Failed to delete existing flowmap texture: {e}")
                self.flowmap_texture_id = 0
            
            # 创建新的flowmap纹理
            flow_texture_id = glGenTextures(1)
            self.flowmap_texture_id = flow_texture_id
            
            if self.flowmap_texture_id == 0:
                print("Error: Failed to generate flowmap texture ID.")
                QMessageBox.critical(self, "OpenGL Error", "Failed to create flowmap texture object.")
                self.doneCurrent()
                return False
                
            # 上传flowmap纹理数据
            try:
                glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0,
                             GL_RGBA, GL_FLOAT, self.flowmap_data)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                
                # 检查上传是否成功
                error = glGetError()
                if error != GL_NO_ERROR:
                    print(f"OpenGL error after flowmap texture upload: {error}")
                    raise GLError(error, "Flowmap texture upload failed")
            except GLError as e:
                print(f"OpenGL error creating flowmap texture: {e}")
                QMessageBox.critical(self, "OpenGL Error", f"Failed to create flowmap texture: {e}")
                if self.flowmap_texture_id != 0:
                    glDeleteTextures(1, [self.flowmap_texture_id])
                    self.flowmap_texture_id = 0
                self.doneCurrent()
                return False
            finally:
                glBindTexture(GL_TEXTURE_2D, 0)
            
            # 更新预览窗口大小
            self.update_preview_size()
            
            # 更新纵横比校正
            self.update_aspect_ratio()
            
            self.doneCurrent() # 释放OpenGL上下文
            self.update() # 重绘
            
            # 发出信号通知外部flowmap已更新
            self.flowmap_updated.emit()
            
            print(f"Successfully imported flowmap: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error importing flowmap: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Import Error", f"Failed to import flowmap: {e}")
            self.doneCurrent() # 确保释放OpenGL上下文
            return False

    def set_texture_size(self, width, height):
        if width <= 0 or height <= 0:
             print(f"Invalid texture size: {width}x{height}")
             return
        print(f"Attempting to resize Flowmap texture to {width}x{height}")
        self.texture_size = (width, height)
        # Reinitialize flowmap data
        self.flowmap_data = np.zeros((height, width, 4), dtype=np.float32)
        self.flowmap_data[..., 0:2] = 0.5 # R, G
        self.flowmap_data[..., 2] = 0.0   # B
        self.flowmap_data[..., 3] = 1.0   # A

        # 确保有效的 OpenGL 上下文
        self.makeCurrent()

        if self.flowmap_texture_id == 0:
            texture_id = glGenTextures(1)
            self.flowmap_texture_id = texture_id
            if self.flowmap_texture_id == 0:
                 print("Error: Failed to generate flowmap texture ID during resize.")
                 QMessageBox.critical(self, "OpenGL Error", "Failed to create texture object during resize.")
                 self.doneCurrent()
                 return
        # Use try-finally for texture binding safety
        try:
            glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0,
                               GL_RGBA, GL_FLOAT, self.flowmap_data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            print(f"Flowmap texture successfully resized to {width}x{height}")

            # 更新纵横比校正
            self.update_aspect_ratio()

            self.update()
            self.flowmap_updated.emit()
        except GLError as e:
             print(f"OpenGL error during texture resize: {e}")
             QMessageBox.critical(self, "OpenGL Error", f"Failed to resize texture: {e}")
        finally:
             glBindTexture(GL_TEXTURE_2D, 0) # Ensure unbinding
             self.doneCurrent() # 释放OpenGL上下文

        # 更新预览窗口大小
        self.update_preview_size()

    def export_flowmap(self, file_path, target_size=None, use_bilinear=True, invert_r=False, invert_g=False):
        """
        导出Flowmap为不同格式的图片文件

        参数:
        file_path -- 导出文件的路径（包含扩展名，如.tga、.png、.jpg等）
        target_size -- 目标尺寸元组(width, height)，如果None则使用当前纹理尺寸
        use_bilinear -- 如果需要缩放，是否使用双线性插值(True)或最近邻(False)
        invert_r -- 是否反转R通道
        invert_g -- 是否反转G通道
        """
        from PIL import Image
        import numpy as np
        import os
        import time
        
        start_time = time.time()

        # 获取当前纹理尺寸
        texture_height, texture_width = self.flowmap_data.shape[:2]
        
        # 如果未指定目标尺寸，则使用当前纹理尺寸
        if target_size is None:
            target_size = (texture_width, texture_height)
        
        # 使用NumPy的向量化操作快速转换数据
        # 1. 提取R和G通道并缩放到[0,255]范围
        r_channel = self.flowmap_data[..., 0]
        g_channel = self.flowmap_data[..., 1]
        
        # 应用通道反转
        if invert_r:
            r_channel = 1.0 - r_channel
        if invert_g:
            g_channel = 1.0 - g_channel
            
        # 转换为uint8
        r_channel = (r_channel * 255).astype(np.uint8)
        g_channel = (g_channel * 255).astype(np.uint8)
        
        # 2. 创建RGB数组
        data = np.zeros((texture_height, texture_width, 3), dtype=np.uint8)
        data[..., 0] = r_channel  # R通道
        data[..., 1] = g_channel  # G通道
        # B通道保持为0
        
        # 3. 翻转Y轴以匹配最终图像格式
        data = np.flipud(data)

        # 创建PIL图像
        img = Image.fromarray(data, 'RGB')

        # 如果指定了目标尺寸且与当前尺寸不同，则进行缩放
        if target_size and (texture_width, texture_height) != target_size:
            if use_bilinear:
                # 使用双线性插值
                resample_method = Image.BILINEAR
            else:
                # 使用最近邻插值
                resample_method = Image.NEAREST

            img = img.resize(target_size, resample_method)
            print(f"已将图像从 {texture_width}x{texture_height} 缩放到 {target_size[0]}x{target_size[1]} 使用{resample_method}")

        # 获取文件扩展名并转换为小写
        _, file_ext = os.path.splitext(file_path)
        file_ext = file_ext.lower()

        # 根据扩展名选择格式并使用优化的参数
        if file_ext == '.tga':
            img.save(file_path, format='TGA')
        elif file_ext == '.png':
            # 优化PNG保存参数 - 减少压缩级别提高速度
            img.save(file_path, format='PNG', optimize=False, compress_level=1)
        elif file_ext == '.jpg' or file_ext == '.jpeg':
            # 使用较低的质量值提高保存速度
            img.save(file_path, format='JPEG', quality=90, optimize=False)
        elif file_ext == '.bmp':
            img.save(file_path, format='BMP')
        else:
            # 默认使用TGA格式
            if not file_path.lower().endswith('.tga'):
                file_path += '.tga'
            img.save(file_path, format='TGA')
            print(f"未知格式，已默认使用TGA格式保存: {file_path}")

        # 计算并显示导出所需时间
        elapsed_time = time.time() - start_time
        print(f"已导出Flowmap到: {file_path}，耗时: {elapsed_time:.2f}秒")
        
    # 保留旧函数名以保持兼容性，但内部调用新函数
    def export_to_tga(self, file_path, target_size=None, use_bilinear=True):
        """兼容旧版API，实际调用export_flowmap方法"""
        self.export_flowmap(file_path, target_size, use_bilinear)

    def get_flowmap_preview(self):
        if self.flowmap_data is None: return QImage()
        height, width, _ = self.flowmap_data.shape
        if width <= 0 or height <=0: return QImage()

        # Convert float[0,1] to BGRA uint8 for QImage
        preview_data_8bit = (np.clip(self.flowmap_data, 0.0, 1.0) * 255).astype(np.uint8)
        bgra_data = np.zeros((height, width, 4), dtype=np.uint8)
        bgra_data[..., 0] = 0 # Blue
        bgra_data[..., 1] = preview_data_8bit[..., 1] # Green
        bgra_data[..., 2] = preview_data_8bit[..., 0] # Red
        bgra_data[..., 3] = 255 # Alpha

        bytes_per_line = width * 4
        # Ensure data is contiguous for QImage constructor
        if not bgra_data.flags['C_CONTIGUOUS']:
            bgra_data = np.ascontiguousarray(bgra_data)

        # Create QImage from buffer. The copy() might be important.
        qimg = QImage(bgra_data.data, width, height, bytes_per_line, QImage.Format_RGB32).copy()
        return qimg

    def cleanupGL(self):
        """清理 OpenGL 资源"""
        # Important: Make the context current before deleting OpenGL resources
        self.makeCurrent()
        print("Cleaning up OpenGL resources...")
        # Use try-except for robustness during cleanup
        try:
            if self.flowmap_texture_id != 0:
                print(f"Deleting flowmap texture: {self.flowmap_texture_id}")
                glDeleteTextures(1, [self.flowmap_texture_id])
                self.flowmap_texture_id = 0
            if self.base_texture_id != 0:
                print(f"Deleting base texture: {self.base_texture_id}")
                glDeleteTextures(1, [self.base_texture_id])
                self.base_texture_id = 0
            if self.uv_vbo != 0:
                 print(f"Deleting UV VBO: {self.uv_vbo}")
                 glDeleteBuffers(1, [self.uv_vbo])
                 self.uv_vbo = 0
            if self.vbo != 0:
                print(f"Deleting quad VBO: {self.vbo}")
                glDeleteBuffers(1, [self.vbo])
                self.vbo = 0
            if self.vao != 0:
                print(f"Deleting quad VAO: {self.vao}")
                glDeleteVertexArrays(1, [self.vao])
                self.vao = 0
            # Delete shader program
            if self.shader_program_id != 0:
                print(f"Deleting shader program: {self.shader_program_id}")
                glDeleteProgram(self.shader_program_id)
                self.shader_program_id = 0
        except Exception as e:
            print(f"Error during OpenGL cleanup: {e}")
        finally:
             self.doneCurrent() # Release the context even if errors occurred
             print("OpenGL cleanup finished.")

    def __del__(self):
        # Note: cleanupGL should ideally be called explicitly before widget destruction,
        # as calling it in __del__ is unreliable for OpenGL contexts.
        print(f"FlowmapCanvas object {id(self)} potentially leaking GL resources if cleanupGL not called.")

    def update_aspect_ratio(self):
        """
        更新纵横比校正参数以保持纹理原始比例

        设纹理的尺寸为(width, height)，纵横比为ratio_texture = width/height
        窗口尺寸为(window_width, window_height)，纵横比为ratio_window = window_width/window_height

        为使纹理在窗口中保持原始纵横比，我们使用以下校正参数:
        1. 如果ratio_texture > ratio_window (纹理较宽):
           水平方向填满，垂直方向居中
           scale_x = 1.0
           scale_y = ratio_window / ratio_texture
           offset_x = 0.0
           offset_y = (1 - scale_y) / 2

        2. 如果ratio_texture < ratio_window (纹理较高):
           垂直方向填满，水平方向居中
           scale_x = ratio_texture / ratio_window
           scale_y = 1.0
           offset_x = (1 - scale_x) / 2
           offset_y = 0.0
        """

        try:
            # 获取纹理尺寸
            texture_width, texture_height = self.texture_size

            # 获取窗口尺寸
            window_width = max(1, self.width())
            window_height = max(1, self.height())

            # 计算纵横比
            ratio_texture = float(texture_width) / float(texture_height)
            ratio_window = float(window_width) / float(window_height)

            # 更新预览窗口的宽高比为纹理的宽高比
            self.preview_aspect_ratio = ratio_texture

            print(f"纹理纵横比: {ratio_texture}, 窗口纵横比: {ratio_window}")

            # 根据纵横比差异计算校正参数
            if abs(ratio_texture - ratio_window) < 0.01:
                # 纵横比几乎相同，不需要校正
                self.main_view_scale_correction_x = 1.0
                self.main_view_scale_correction_y = 1.0
                self.main_view_offset_correction_x = 0.0
                self.main_view_offset_correction_y = 0.0
            elif ratio_texture > ratio_window:
                # 纹理较宽，水平方向填满，垂直方向居中
                self.main_view_scale_correction_x = 1.0
                self.main_view_scale_correction_y = ratio_window / ratio_texture
                self.main_view_offset_correction_x = 0.0
                self.main_view_offset_correction_y = (1.0 - self.main_view_scale_correction_y) / 2.0
            else:
                # 纹理较高，垂直方向填满，水平方向居中
                self.main_view_scale_correction_x = ratio_texture / ratio_window
                self.main_view_scale_correction_y = 1.0
                self.main_view_offset_correction_x = (1.0 - self.main_view_scale_correction_x) / 2.0
                self.main_view_offset_correction_y = 0.0

            # 保存原始纵横比用于坐标转换
            self.texture_original_aspect_ratio = ratio_texture

            print(f"应用纵横比校正: scale=({self.main_view_scale_correction_x}, {self.main_view_scale_correction_y}), offset=({self.main_view_offset_correction_x}, {self.main_view_offset_correction_y})")

            # 更新预览窗口大小以匹配纹理比例
            self.update_preview_size()

        except Exception as e:
            print(f"更新纵横比出错: {e}")
            import traceback
            traceback.print_exc()
            # 出错时使用默认值
            self.main_view_scale_correction_x = 1.0
            self.main_view_scale_correction_y = 1.0
            self.main_view_offset_correction_x = 0.0
            self.main_view_offset_correction_y = 0.0

        # 更新显示
        self.update()

    def mapToScene(self, pos):
        """
        将窗口坐标映射到场景坐标(纹理空间)

        关键点：
        1. shader 中的坐标系以左上角为原点(0,0)，X向右，Y向下
        2. TexCoords 在 shader 中直接映射到左上角为原点的纹理坐标系
        3. 主视图的缩放和偏移通过这个公式应用: mainTexCoords = TexCoords / u_mainViewScale - u_mainViewOffset
        4. 在 mouseMoveEvent 中，Y 轴偏移使用负号是为了保持拖动行为的直观性

        此函数必须生成与 shader 计算完全一致的坐标
        """
        if self.width() <= 0 or self.height() <= 0:
            return QPointF(0, 0)

        # 归一化窗口坐标到[0,1]范围（屏幕坐标，左上角为(0,0)）
        norm_x = pos.x() / self.width()
        norm_y_screen = pos.y() / self.height()

        # 将屏幕坐标转换为 shader 的 TexCoords（左上角为(0,0)但Y向上为1）：
        # 屏幕y向下增大，因此 TexCoords.y = 1 - norm_y_screen
        tex_x = norm_x
        tex_y = 1.0 - norm_y_screen

        # 应用 cover 的纵横比逆变换：corrected = (TexCoords - offset) / scale
        corrected_x = (tex_x - self.aspect_offset_x) / max(1e-6, self.aspect_scale_x)
        corrected_y = (tex_y - self.aspect_offset_y) / max(1e-6, self.aspect_scale_y)

        # 应用主视图缩放与偏移的逆变换
        scene_x = corrected_x / self.main_view_scale - self.main_view_offset.x()
        scene_y = corrected_y / self.main_view_scale - self.main_view_offset.y()

        return QPointF(scene_x, scene_y)

    def mapFromScene(self, scene_pos):
        """
        将场景坐标(纹理空间)映射到窗口坐标

        这是 mapToScene 的逆运算：
        1. 从 shader 公式反推: TexCoords = (mainTexCoords + u_mainViewOffset) * u_mainViewScale
        2. 保持与 mapToScene 和 shader 一致的坐标系约定
        """
        # 1) 内容坐标 -> TexCoords（shader空间）
        tex_x = (scene_pos.x() + self.main_view_offset.x()) * self.main_view_scale
        tex_y = (scene_pos.y() + self.main_view_offset.y()) * self.main_view_scale

        # 2) 应用 cover 的纵横比正向变换：Tex' = Tex * scale + offset
        tex_x = tex_x * self.aspect_scale_x + self.aspect_offset_x
        tex_y = tex_y * self.aspect_scale_y + self.aspect_offset_y

        # 3) TexCoords -> 屏幕归一化坐标（y翻转）
        norm_x = tex_x
        norm_y_screen = 1.0 - tex_y

        # 4) 转换为窗口像素坐标
        widget_x = norm_x * self.width()
        widget_y = norm_y_screen * self.height()

        return QPoint(int(widget_x), int(widget_y))

    def update_texture_from_data(self):
        """直接从flowmap_data更新OpenGL纹理"""
        if self.flowmap_texture_id == 0 or self.flowmap_data is None:
            return

        try:
            self.makeCurrent()
            # 绑定纹理并更新数据
            glBindTexture(GL_TEXTURE_2D, self.flowmap_texture_id)

            # 确保数据有正确的格式 - 修复可能的浮点数到无符号字节的转换问题
            # flowmap_data是float32类型 [0,1] 范围，需要正确地转换为 [0,255] 范围
            h, w, c = self.flowmap_data.shape
            data = (np.clip(self.flowmap_data, 0.0, 1.0) * 255.0).astype(np.uint8)

            # 确保数据是连续的
            if not data.flags['C_CONTIGUOUS']:
                data = np.ascontiguousarray(data)

            # 更新整个纹理
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)

            # 检查错误
            error = glGetError()
            if error != GL_NO_ERROR:
                print(f"OpenGL error updating texture data: {error}")

            glBindTexture(GL_TEXTURE_2D, 0)
            self.doneCurrent()
            # 更新画布
            self.update()
        except Exception as e:
            print(f"Error updating texture from data: {e}")
            import traceback
            traceback.print_exc()
            self.doneCurrent()

    def set_graphics_api_mode(self, mode):
        """设置图形API模式，处理DirectX和OpenGL中的坐标和纹理差异

        OpenGL: Y轴向上为正，DirectX: Y轴向下为正
        对于流向图，从OpenGL转为DirectX时:
        - 只需反转G通道（垂直方向）
        - 保持R通道（水平方向）不变
        """
        old_mode = self.graphics_api_mode
        self.graphics_api_mode = mode.lower()  # 确保小写

        texture_height = self.texture_size[0]
        texture_width = self.texture_size[1]


        # 只有当模式真正改变时才处理
        if old_mode != self.graphics_api_mode:
            if self.graphics_api_mode == 'directx':
                print("切换到DirectX模式 - 反转G通道")
                # DirectX模式: 只需要反转G通道的数值
                for y in range(texture_height):
                    for x in range(texture_width):
                        # 只反转G通道，R通道保持不变
                        # 从[0,1]范围转换为反转后的值 (1.0 - 原值)
                        self.flowmap_data[x, y, 1] = 1.0 - self.flowmap_data[x, y, 1]
            elif old_mode == 'directx':
                print("切换回OpenGL模式 - 还原G通道")
                # 从DirectX切换回OpenGL模式，还原G通道的反转
                for y in range(texture_height):
                    for x in range(texture_width):
                        idx = (y * texture_width + x) * 4
                        # 只反转G通道，R通道保持不变
                        self.flowmap_data[x, y, 1] = 1.0 - self.flowmap_data[x, y, 1]

            # 更新纹理数据到GPU
            self.update_texture_from_data()
            self.update()
            print(f"已切换图形API模式为: {self.graphics_api_mode}")

    def set_seamless_mode(self, enable):
        """设置是否启用四方连续绘制模式"""
        self.enable_seamless = enable
        # 不需要重绘，只在下次绘制时应用

    def reset_parameters(self):
        """重置所有视图参数到默认值"""
        self.main_view_scale = 1.0
        self.main_view_offset = QPointF(0.0, 0.0)
        self.preview_offset = QPointF(0.0, 0.0)
        self.update()


    def apply_improved_seamless_brush(self, center_x, center_y, radius, flow_r, flow_g, strength):
        """
        改进的四方连续笔刷实现，处理边缘重叠区域

        数学原理：
        在四方连续纹理中，左右边缘和上下边缘需要无缝衔接。
        当笔刷与边缘重叠时，笔刷效果需要在相应的对侧边缘重复出现。

        具体来说，当笔刷中心点(x,y)与纹理边缘的距离小于半径r时：
        1. 对于左边缘(x < r)：需要在右边缘(x = width - (r - x))应用相同效果
        2. 对于右边缘(x > width - r)：需要在左边缘(x = (x - (width - r)))应用相同效果
        3. 对于上边缘(y < r)：需要在下边缘(y = height - (r - y))应用相同效果
        4. 对于下边缘(y > height - r)：需要在上边缘(y = (y - (height - r)))应用相同效果

        此外，还需要处理四个角落的情况，这需要在对角的三个位置应用相同效果。
        """
        tex_h, tex_w = self.texture_size[1], self.texture_size[0]

        # 使用正方形区域进行检测，确保更准确的边界检测
        # 如果笔刷不靠近任何边缘，直接返回
        radius_sq = radius * radius

        # 四方连续处理涉及多个复制点，基于笔刷位置和纹理大小
        # 创建笔刷区域的边界框
        brush_min_x = center_x - radius
        brush_max_x = center_x + radius
        brush_min_y = center_y - radius
        brush_max_y = center_y + radius

        # 检查是否需要四方连续处理
        needs_wrap_x_left = brush_min_x < 0
        needs_wrap_x_right = brush_max_x >= tex_w
        needs_wrap_y_top = brush_min_y < 0
        needs_wrap_y_bottom = brush_max_y >= tex_h

        if not (needs_wrap_x_left or needs_wrap_x_right or needs_wrap_y_top or needs_wrap_y_bottom):
            return  # 笔刷完全在纹理内部，不需要四方连续处理

        brush_positions = []  # 存储需要复制笔刷效果的位置

        # 处理水平边缘 - 左右方向
        if needs_wrap_x_left:
            # 在右侧创建一个笔刷
            wrap_x = center_x + tex_w
            brush_positions.append((wrap_x, center_y))

        if needs_wrap_x_right:
            # 在左侧创建一个笔刷
            wrap_x = center_x - tex_w
            brush_positions.append((wrap_x, center_y))

        # 处理垂直边缘 - 上下方向
        if needs_wrap_y_top:
            # 在底部创建一个笔刷
            wrap_y = center_y + tex_h
            brush_positions.append((center_x, wrap_y))

        if needs_wrap_y_bottom:
            # 在顶部创建一个笔刷
            wrap_y = center_y - tex_h
            brush_positions.append((center_x, wrap_y))

        # 处理角落 - 需要在对角位置也创建笔刷
        if needs_wrap_x_left and needs_wrap_y_top:
            wrap_x = center_x + tex_w
            wrap_y = center_y + tex_h
            brush_positions.append((wrap_x, wrap_y))

        if needs_wrap_x_right and needs_wrap_y_top:
            wrap_x = center_x - tex_w
            wrap_y = center_y + tex_h
            brush_positions.append((wrap_x, wrap_y))

        if needs_wrap_x_left and needs_wrap_y_bottom:
            wrap_x = center_x + tex_w
            wrap_y = center_y - tex_h
            brush_positions.append((wrap_x, wrap_y))

        if needs_wrap_x_right and needs_wrap_y_bottom:
            wrap_x = center_x - tex_w
            wrap_y = center_y - tex_h
            brush_positions.append((wrap_x, wrap_y))

        # 对每个需要复制的位置应用笔刷效果
        for wrap_center_x, wrap_center_y in brush_positions:
            # 确保坐标在纹理范围内
            # 注意：这里使用整数取模运算来确保坐标被正确地包装
            wrap_center_x = wrap_center_x % tex_w
            wrap_center_y = wrap_center_y % tex_h

            # 计算笔刷区域
            brush_min_x = max(0, int(wrap_center_x - radius))
            brush_max_x = min(tex_w, int(wrap_center_x + radius + 1))
            brush_min_y = max(0, int(wrap_center_y - radius))
            brush_max_y = min(tex_h, int(wrap_center_y + radius + 1))

            # 确保有效范围
            if brush_min_x >= brush_max_x or brush_min_y >= brush_max_y:
                continue

            # 创建距离场
            y_grid, x_grid = np.ogrid[brush_min_y:brush_max_y, brush_min_x:brush_max_x]
            dist_sq = (x_grid - wrap_center_x) ** 2 + (y_grid - wrap_center_y) ** 2

            # 计算笔刷衰减
            t = np.clip(np.sqrt(dist_sq) / radius, 0.0, 1.0)
            falloff = 1.0 - t * t * (3.0 - 2.0 * t)  # 平滑衰减函数
            falloff = np.clip(falloff, 0.0, 1.0).astype(np.float32)

            # 应用笔刷效果
            current_region = self.flowmap_data[brush_min_y:brush_max_y, brush_min_x:brush_max_x, :2]
            new_flow_color = np.array([flow_r, flow_g], dtype=np.float32)
            falloff_expanded = falloff[..., np.newaxis] * strength
            updated_region = current_region * (1.0 - falloff_expanded) + new_flow_color * falloff_expanded
            self.flowmap_data[brush_min_y:brush_max_y, brush_min_x:brush_max_x, :2] = updated_region

    def update_preview_size(self):
        """更新预览窗口的大小以匹配纹理比例"""
        # 确保窗口尺寸已存在
        if not hasattr(self, 'window_width') or not hasattr(self, 'window_height'):
            self.window_width = self.width() or 800
            self.window_height = self.height() or 600
            print(f"初始化窗口大小：{self.window_width}x{self.window_height}")
        
        # 检查纹理尺寸有效性
        if self.texture_size[0] <= 0 or self.texture_size[1] <= 0:
            print("警告：纹理尺寸无效")
            return
            
        # 计算纹理的宽高比
        texture_aspect_ratio = float(self.texture_size[0]) / float(self.texture_size[1])
        
        # 根据窗口大小动态调整预览窗口的像素宽度
        if self.window_width < 400 or self.window_height < 300:
            preview_scale_factor = 0.15  # 相对于窗口宽度
        else:
            preview_scale_factor = 0.2

        # 先用像素计算，避免因不同坐标归一化导致的纵横比误差
        pv_w_px = int(self.window_width * preview_scale_factor)
        pv_h_px = int(max(1, pv_w_px / texture_aspect_ratio))

        # 上限：不超过窗口高度的35%
        max_h_px = int(self.window_height * 0.35)
        if pv_h_px > max_h_px:
            pv_h_px = max_h_px
            pv_w_px = int(pv_h_px * texture_aspect_ratio)

        # 下限：宽度至少占窗口宽的10%
        min_w_px = int(self.window_width * 0.1)
        if pv_w_px < min_w_px:
            pv_w_px = min_w_px
            pv_h_px = int(max(1, pv_w_px / texture_aspect_ratio))

        # 转回归一化比例
        preview_width = pv_w_px / float(self.window_width)
        preview_height = pv_h_px / float(self.window_height)

        # 更新预览窗口大小（归一化）
        self.preview_size = QSizeF(preview_width, preview_height)
        
        # 添加适当的边距
        margin = 0.01  # 窗口边距
        
        # 放置预览窗口在右上角
        right_margin = 1.0 - preview_width - margin
        top_margin = margin
        
        # 设置预览窗口位置（以左上为原点的归一化坐标）
        self.preview_pos = QPointF(right_margin, top_margin)
        
        print(f"预览窗口更新(右上)：宽度={preview_width:.3f}，高度={preview_height:.3f}，宽高比={preview_width/preview_height:.3f}，纹理比例={texture_aspect_ratio:.3f}")
        
        # 强制更新
        self.update()

    def is_in_preview(self, pos):
        """检查给定窗口坐标是否在预览区域内"""
        pos_x = pos.x() / self.width()
        pos_y = pos.y() / self.height()

        return (pos_x >= self.preview_pos.x() and
                pos_x <= self.preview_pos.x() + self.preview_size.width() and
                pos_y >= self.preview_pos.y() and
                pos_y <= self.preview_pos.y() + self.preview_size.height())

    def get_preview_coords(self, pos):
        """将窗口坐标转换为预览区域内的归一化坐标"""
        pos_x = pos.x() / self.width()
        pos_y = pos.y() / self.height()

        preview_coord_x = (pos_x - self.preview_pos.x()) / self.preview_size.width()
        preview_coord_y = (pos_y - self.preview_pos.y()) / self.preview_size.height()

        return QPointF(preview_coord_x, preview_coord_y)

    def debug_coordinates(self, widget_pos):
        """
        打印窗口坐标和对应的场景坐标，用于调试坐标映射
        """
        scene_pos = self.mapToScene(widget_pos)

        # 转换到纹理像素坐标
        tex_h, tex_w = self.texture_size[1], self.texture_size[0]
        tex_x = int(scene_pos.x() * tex_w)
        tex_y = int((1.0 - scene_pos.y()) * tex_h)  # 翻转Y轴

        print(f"Widget pos: ({widget_pos.x()}, {widget_pos.y()})")
        print(f"Scene pos: ({scene_pos.x():.3f}, {scene_pos.y():.3f})")
        print(f"Texture pos: ({tex_x}, {tex_y})")
        print(f"View scale: {self.main_view_scale}, offset: ({self.main_view_offset.x():.3f}, {self.main_view_offset.y():.3f})")

        return scene_pos

    def fill_flowmap(self, r_value, g_value):
        """使用指定颜色填充整个flowmap"""
        if self.flowmap_data is None:
            return

        # 创建填充颜色数组 (RGBA)
        fill_color = np.array([r_value, g_value, 0.0, 1.0], dtype=np.float32)

        # 填充整个纹理
        h, w, _ = self.flowmap_data.shape
        for y in range(h):
            for x in range(w):
                self.flowmap_data[y, x] = fill_color

        # 更新GPU上的纹理
        self.update_texture_from_data()

        # 更新显示
        self.update()

        # 发送更新信号
        self.flowmap_updated.emit()

        print(f"已填充整个flowmap为颜色: ({r_value:.2f}, {g_value:.2f}, 0.0, 1.0)")

    def set_uv_overlay_data(self, uvs_np, indices_np):
        """接收3D模型的UV与三角索引，构建线框（边）并上传到GL buffer。
        uvs_np: (N,2) float32; indices_np: (M,) uint32 (triangles)
        """
        try:
            if uvs_np is None or indices_np is None or uvs_np.size == 0 or indices_np.size == 0:
                self.uv_wire_enabled = False
                return
            self.makeCurrent()
            # 提取三角形边作为线，构建线索引
            tris = indices_np.reshape(-1, 3)
            edges = np.concatenate([
                tris[:, [0,1]], tris[:, [1,2]], tris[:, [2,0]]
            ], axis=0).astype(np.uint32)
            # 去重（无向边）
            a = np.minimum(edges[:,0], edges[:,1])
            b = np.maximum(edges[:,0], edges[:,1])
            packed = a.astype(np.uint64) << 32 | b.astype(np.uint64)
            uniq, idx = np.unique(packed, return_index=True)
            unique_edges = edges[idx]
            line_indices = unique_edges.flatten().astype(np.uint32)
            # 创建/更新VAO/VBO/EBO（确保为有效整型句柄）
            if not getattr(self, 'uv_wire_vao', 0):
                self.uv_wire_vao = int(glGenVertexArrays(1))
            if not getattr(self, 'uv_wire_vbo', 0):
                self.uv_wire_vbo = int(glGenBuffers(1))
            if not getattr(self, 'uv_wire_ebo', 0):
                self.uv_wire_ebo = int(glGenBuffers(1))
            glBindVertexArray(self.uv_wire_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.uv_wire_vbo)
            uvs_np = uvs_np.astype(np.float32, copy=False)
            glBufferData(GL_ARRAY_BUFFER, uvs_np.nbytes, uvs_np, GL_STATIC_DRAW)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.uv_wire_ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, line_indices.nbytes, line_indices, GL_STATIC_DRAW)
            loc_uv = 0
            if self.uv_wire_program:
                loc_uv = glGetAttribLocation(self.uv_wire_program, b"aUV")
                if loc_uv < 0:
                    loc_uv = 0
            glEnableVertexAttribArray(loc_uv)
            glVertexAttribPointer(loc_uv, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
            glBindVertexArray(0)
            self.uv_wire_index_count = int(line_indices.size)
            self.uv_wire_enabled = True
        except Exception as e:
            print(f"set_uv_overlay_data error: {e}")
            self.uv_wire_enabled = False
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass