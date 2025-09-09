from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPoint, QTimer, QPointF, pyqtSignal as Signal
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GL import shaders
from OpenGL.error import GLError
import numpy as np
import ctypes

from mesh_loader import MeshData
from brush_cursor import BrushCursorWidget


SIMPLE_VERT = """
#version 150
in vec3 aPos;
in vec3 aNormal;
in vec2 aUV;
out vec2 vUV;
out vec3 vNormal;
uniform mat4 u_model;
uniform mat4 u_viewProj;
void main(){
  vUV = aUV;
  vNormal = mat3(u_model) * aNormal;
  gl_Position = u_viewProj * (u_model * vec4(aPos, 1.0));
}
"""

SIMPLE_FRAG = """
#version 150
in vec2 vUV;
in vec3 vNormal;
out vec4 FragColor;
uniform sampler2D baseMap;
uniform sampler2D flowMap;
uniform bool u_hasBaseMap;
uniform float u_flowSpeed;
uniform float u_flowDistortion;
uniform float u_time;
uniform bool u_repeat;
uniform float u_useDirectX;
uniform float u_scale;
void main(){
  vec2 uv = vUV;
  if (u_hasBaseMap) {
    vec2 flowDir = texture(flowMap, uv).rg * 2.0 - 1.0;
    if (u_useDirectX >= 1.0) flowDir.y *= -1.0;
    float phaseTime = u_time * u_flowSpeed;
    float phase0 = fract(phaseTime);
    float phase1 = fract(phaseTime + 0.5);
    vec2 offset0 = flowDir * phase0 * u_flowDistortion;
    vec2 offset1 = flowDir * phase1 * u_flowDistortion;
    vec4 color0;
    vec4 color1;
    // Apply base scale to texture coordinates
    vec2 scaledUV = uv / u_scale;
    if (u_repeat) {
      color0 = texture(baseMap, fract(scaledUV + offset0));
      color1 = texture(baseMap, fract(scaledUV + offset1));
    } else {
      vec2 s0 = clamp(scaledUV + offset0, 0.0, 1.0);
      vec2 s1 = clamp(scaledUV + offset1, 0.0, 1.0);
      color0 = texture(baseMap, s0);
      color1 = texture(baseMap, s1);
    }
    float weight = abs((0.5 - phase0) / 0.5);
    FragColor = mix(color0, color1, weight);
  } else {
    if (u_repeat) {
      FragColor = vec4(texture(flowMap, fract(uv)).rg, 0.0, 1.0);
    } else {
      if (uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0)
        FragColor = vec4(texture(flowMap, uv).rg, 0.0, 1.0);
      else
        FragColor = vec4(0.1,0.1,0.1,1.0);
    }
  }
}
"""


class ThreeDViewport(QOpenGLWidget):
    # 3D绘制开始/结束信号，用于复用2D撤销栈逻辑
    paint_started = Signal()
    paint_finished = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.program = 0
        self.vao = 0
        self.vbo = 0
        self.ebo = 0
        self.index_count = 0
        self.model_loaded = False
        self._use_vao = True
        # repaint timer (60 FPS)
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(16)
        self._repaint_timer.timeout.connect(self.update)
        # painting state
        self._is_painting = False
        self._last_hit_uv = None
        self._alt_pressed = False
        self._is_adjusting = False
        self._adjust_origin = QPoint(0, 0)
        self._initial_brush_radius = 40.0
        self._initial_brush_strength = 0.5
        # optional brush cursor overlay
        self._brush_cursor = BrushCursorWidget(self)
        try:
            self._brush_cursor.resize(self.size())
        except Exception:
            pass
        self._brush_cursor.hide()

        # default attribute indices
        self._attr_pos = 0
        self._attr_nrm = 1
        self._attr_uv  = 2

        # model fit matrix
        self._model_matrix = np.identity(4, dtype=np.float32)

        # camera state (orbit)
        self._cam_yaw = 0.0
        self._cam_pitch = 0.35
        self._cam_distance = 3.0
        self._cam_target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._last_mouse = QPoint(0, 0)
        self._is_rotating = False
        self._is_panning = False
        self._is_zooming = False

        # placeholders
        self._positions = np.zeros((0,3), dtype=np.float32)
        self._uvs = np.zeros((0,2), dtype=np.float32)
        self._normals = np.zeros((0,3), dtype=np.float32)
        self._indices = np.zeros((0,), dtype=np.uint32)

        self.setMouseTracking(True)

    def showEvent(self, event):
        try:
            if self._repaint_timer is not None:
                self._repaint_timer.start()
        except Exception:
            pass
        return super().showEvent(event)

    def hideEvent(self, event):
        try:
            if self._repaint_timer is not None:
                self._repaint_timer.stop()
        except Exception:
            pass
        return super().hideEvent(event)

    def set_canvas(self, canvas_widget):
        """Provide a reference to the 2D canvas so we can sample its textures and params."""
        self._canvas = canvas_widget
        try:
            # 同步笔刷半径
            self._brush_cursor.radius = getattr(self._canvas, 'brush_radius', 40)
        except Exception:
            pass

    def get_uv_wire_data(self):
        """Return current model UVs and triangle indices for 2D UV wire rendering."""
        try:
            return (self._uvs.copy() if hasattr(self, '_uvs') else None,
                    self._indices.copy() if hasattr(self, '_indices') else None)
        except Exception:
            return (None, None)

    def initializeGL(self):
        try:
            glEnable(GL_DEPTH_TEST)
            self.program = shaders.compileProgram(
                shaders.compileShader(SIMPLE_VERT, GL_VERTEX_SHADER),
                shaders.compileShader(SIMPLE_FRAG, GL_FRAGMENT_SHADER)
            )
            # Cache attribute locations; fallback
            self._attr_pos = glGetAttribLocation(self.program, b"aPos")
            self._attr_nrm = glGetAttribLocation(self.program, b"aNormal")
            self._attr_uv  = glGetAttribLocation(self.program, b"aUV")
            if self._attr_pos < 0: self._attr_pos = 0
            if self._attr_nrm < 0: self._attr_nrm = 1
            if self._attr_uv  < 0: self._attr_uv  = 2
            # Context may be recreated by Qt; if we already have mesh data, (re)create buffers now
            if self._indices.size > 0:
                self._create_buffers()
        except Exception as e:
            print(f"3D viewport init error: {e}")

    def _is_valid_vao(self, vao_id):
        try:
            return vao_id != 0 and glIsVertexArray(vao_id)
        except Exception:
            return vao_id != 0

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        glViewport(0, 0, self.width(), self.height())
        glClearColor(0.08, 0.08, 0.1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # Guard: program and mesh must exist
        if self.program == 0 or self.index_count == 0:
            return
        # If VAO invalid (e.g., context recreated), try to rebuild lazily
        if self._use_vao:
            if not self._is_valid_vao(self.vao):
                self._create_buffers()
                if not self._is_valid_vao(self.vao):
                    # VAO path not viable; fallback to non-VAO
                    self._use_vao = False
        else:
            # Ensure buffers exist for non-VAO path
            if self.vbo == 0 or self.ebo == 0:
                self._create_buffers()

        glUseProgram(self.program)

        view = self._compute_view_matrix()
        proj = self._compute_perspective_matrix(45.0, max(1.0, float(self.width()))/max(1.0, float(self.height())), 0.01, 100.0)
        viewproj = proj @ view
        # 缓存用于光线投射，防止高宽变化带来不一致
        self._last_view = view
        self._last_proj = proj

        loc_viewproj = glGetUniformLocation(self.program, "u_viewProj")
        glUniformMatrix4fv(loc_viewproj, 1, GL_TRUE, viewproj.astype(np.float32))

        loc_model = glGetUniformLocation(self.program, "u_model")
        glUniformMatrix4fv(loc_model, 1, GL_TRUE, self._model_matrix.astype(np.float32))

        # Bind textures/uniforms from canvas
        int_has_base = 0
        if hasattr(self, '_canvas') and self._canvas is not None:
            try:
                glActiveTexture(GL_TEXTURE0)
                base_id = int(getattr(self._canvas, 'base_texture_id', 0))
                glBindTexture(GL_TEXTURE_2D, base_id)
                loc_base = glGetUniformLocation(self.program, "baseMap")
                if loc_base != -1:
                    glUniform1i(loc_base, 0)
                int_has_base = 1 if (getattr(self._canvas, 'has_base_map', False) and base_id != 0) else 0
            except Exception:
                int_has_base = 0
            try:
                glActiveTexture(GL_TEXTURE1)
                flow_id = int(getattr(self._canvas, 'flowmap_texture_id', 0))
                glBindTexture(GL_TEXTURE_2D, flow_id)
                loc_flow = glGetUniformLocation(self.program, "flowMap")
                if loc_flow != -1:
                    glUniform1i(loc_flow, 1)
            except Exception:
                pass
            t_loc = glGetUniformLocation(self.program, "u_time")
            if t_loc != -1:
                glUniform1f(t_loc, float(self._canvas.anim_time))
            sp_loc = glGetUniformLocation(self.program, "u_flowSpeed")
            if sp_loc != -1:
                glUniform1f(sp_loc, float(self._canvas.flow_speed))
            ds_loc = glGetUniformLocation(self.program, "u_flowDistortion")
            if ds_loc != -1:
                glUniform1f(ds_loc, float(self._canvas.flow_distortion))
            rp_loc = glGetUniformLocation(self.program, "u_repeat")
            if rp_loc != -1:
                glUniform1i(rp_loc, 1 if getattr(self._canvas, 'preview_repeat', False) else 0)
            udx_loc = glGetUniformLocation(self.program, "u_useDirectX")
            if udx_loc != -1:
                glUniform1f(udx_loc, 1.0 if getattr(self._canvas, 'graphics_api_mode', 'opengl') == 'directx' else 0.0)
            # Pass base scale from 2D canvas
            scale_loc = glGetUniformLocation(self.program, "u_scale")
            if scale_loc != -1:
                glUniform1f(scale_loc, float(getattr(self._canvas, 'base_scale', 1.0)))
        has_loc = glGetUniformLocation(self.program, "u_hasBaseMap")
        if has_loc != -1:
            glUniform1i(has_loc, int_has_base)

        if self._use_vao:
            try:
                glBindVertexArray(self.vao)
            except GLError:
                # Fallback if driver rejects VAO
                self._use_vao = False
            if self._use_vao:
                glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            else:
                # fall through to non-VAO draw
                pass
        if not self._use_vao:
            stride = (3+3+2) * 4
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            if self._attr_pos >= 0:
                glEnableVertexAttribArray(self._attr_pos)
                glVertexAttribPointer(self._attr_pos, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
            if self._attr_nrm >= 0:
                glEnableVertexAttribArray(self._attr_nrm)
                glVertexAttribPointer(self._attr_nrm, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
            if self._attr_uv >= 0:
                glEnableVertexAttribArray(self._attr_uv)
                glVertexAttribPointer(self._attr_uv, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
            glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)

        glUseProgram(0)

    def _create_buffers(self):
        verts = np.hstack([self._positions, self._normals, self._uvs]).astype(np.float32) if self._positions.size else np.zeros((0,8), dtype=np.float32)
        self.index_count = int(self._indices.size)
        # create fresh objects
        if self.vao != 0:
            try:
                glDeleteVertexArrays(1, [self.vao])
            except Exception:
                pass
            self.vao = 0
        if self.vbo != 0:
            try: glDeleteBuffers(1, [self.vbo])
            except Exception: pass
            self.vbo = 0
        if self.ebo != 0:
            try: glDeleteBuffers(1, [self.ebo])
            except Exception: pass
            self.ebo = 0
        if self._use_vao:
            self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)
        if (self._use_vao and self.vao == 0) or self.vbo == 0 or self.ebo == 0:
            print(f"VAO/VBO/EBO creation failed: vao={self.vao}, vbo={self.vbo}, ebo={self.ebo}")
            return
        if self._use_vao:
            glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, GL_STATIC_DRAW)
        if self._use_vao:
            stride = (3+3+2) * 4
            if self._attr_pos >= 0:
                glEnableVertexAttribArray(self._attr_pos)
                glVertexAttribPointer(self._attr_pos, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
            if self._attr_nrm >= 0:
                glEnableVertexAttribArray(self._attr_nrm)
                glVertexAttribPointer(self._attr_nrm, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
            if self._attr_uv >= 0:
                glEnableVertexAttribArray(self._attr_uv)
                glVertexAttribPointer(self._attr_uv, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
            glBindVertexArray(0)

    def _fit_model_matrix(self):
        if self._positions.size == 0:
            self._model_matrix = np.identity(4, dtype=np.float32)
            return
        mins = self._positions.min(axis=0)
        maxs = self._positions.max(axis=0)
        center = (mins + maxs) * 0.5
        extent = (maxs - mins)
        max_dim = max(1e-6, float(np.max(extent)))
        scale = 1.6 / max_dim
        M = np.identity(4, dtype=np.float32)
        M[0,0] = scale; M[1,1] = scale; M[2,2] = scale
        M[0,3] = -center[0] * scale
        M[1,3] = -center[1] * scale
        M[2,3] = -center[2] * scale
        self._model_matrix = M
        self._cam_target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._cam_distance = 3.0

    # renderer-only API
    def load_mesh(self, mesh: MeshData):
        """接受脱耦的MeshData进行上传，并进行居中/缩放适配"""
        self._positions = mesh.positions.astype(np.float32, copy=False)
        self._uvs = mesh.uvs.astype(np.float32, copy=False)
        self._normals = mesh.normals.astype(np.float32, copy=False)
        self._indices = mesh.indices.astype(np.uint32, copy=False)
        try:
            self._tri_indices = self._indices.reshape(-1, 3)
        except Exception:
            self._tri_indices = np.zeros((0,3), dtype=np.uint32)
        # fit
        self._fit_model_matrix()
        # upload
        self.makeCurrent()
        try:
            self._create_buffers()
            # 预计算三角形数据与BVH
            try:
                self._tri_indices = self._indices.reshape(-1, 3).astype(np.int64, copy=False)
                if self._tri_indices.size > 0:
                    P = self._positions.astype(np.float32, copy=False)
                    tris = self._tri_indices
                    v0 = P[tris[:, 0]]
                    v1 = P[tris[:, 1]]
                    v2 = P[tris[:, 2]]
                    self._tri_v0 = v0
                    self._tri_e1 = (v1 - v0).astype(np.float32, copy=False)
                    self._tri_e2 = (v2 - v0).astype(np.float32, copy=False)
                    tri_min = np.minimum(np.minimum(v0, v1), v2)
                    tri_max = np.maximum(np.maximum(v0, v1), v2)
                    tri_centroid = (v0 + v1 + v2) / 3.0
                    self._build_bvh(tri_min, tri_max, tri_centroid)
            except Exception as e:
                print(f"BVH precompute error: {e}")
            self._fit_model_matrix()
            self.model_loaded = True
            self.update()
            return True
        except Exception as e:
            print(f"load_mesh error: {e}")
            return False
        finally:
            try: self.doneCurrent()
            except Exception: pass

    def _compute_view_matrix(self):
        cy = np.cos(self._cam_yaw)
        sy = np.sin(self._cam_yaw)
        cp = np.cos(self._cam_pitch)
        sp = np.sin(self._cam_pitch)
        dir_vec = np.array([cy * cp, sp, sy * cp], dtype=np.float32)
        eye = self._cam_target - dir_vec * self._cam_distance
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        return self._look_at(eye, self._cam_target, up)

    def _look_at(self, eye, center, up):
        f = center - eye
        f = f / (np.linalg.norm(f) + 1e-8)
        u = up / (np.linalg.norm(up) + 1e-8)
        s = np.cross(f, u)
        s = s / (np.linalg.norm(s) + 1e-8)
        u = np.cross(s, f)
        M = np.identity(4, dtype=np.float32)
        M[0, :3] = s
        M[1, :3] = u
        M[2, :3] = -f
        T = np.identity(4, dtype=np.float32)
        T[0, 3] = -eye[0]
        T[1, 3] = -eye[1]
        T[2, 3] = -eye[2]
        return M @ T

    def _compute_perspective_matrix(self, fov_y_deg, aspect, near, far):
        f = 1.0 / np.tan(np.deg2rad(fov_y_deg) * 0.5)
        M = np.zeros((4, 4), dtype=np.float32)
        M[0,0] = f / aspect
        M[1,1] = f
        M[2,2] = (far + near) / (near - far)
        M[2,3] = (2 * far * near) / (near - far)
        M[3,2] = -1.0
        return M

    def mousePressEvent(self, event):
        self._last_mouse = event.pos()
        if event.button() == Qt.LeftButton:
            if (event.modifiers() & Qt.ControlModifier) or not self.model_loaded:
                # Ctrl+左键：旋转
                self._is_rotating = True
                self._is_painting = False
                self._hide_brush_cursor()
            else:
                # 左键绘制
                uv = self._raycast_uv(event.pos())
                if uv is not None:
                    self._is_painting = True
                    self._last_hit_uv = uv
                    self.paint_started.emit()
                    self._invoke_canvas_brush(self._last_hit_uv, uv)
                    self._show_brush_cursor(event.pos())
        elif event.button() == Qt.MiddleButton:
            if event.modifiers() & Qt.ControlModifier:
                # Ctrl+中键：旋转
                self._is_rotating = True
                self._is_panning = False
                self._is_zooming = False
            elif event.modifiers() & Qt.AltModifier:
                # Alt+中键：调整笔刷（与2D一致）
                self._is_adjusting = True
                self._adjust_origin = event.pos()
                try:
                    self._initial_brush_radius = float(getattr(self._canvas, 'brush_radius', 40.0))
                    self._initial_brush_strength = float(getattr(self._canvas, 'brush_strength', 0.5))
                except Exception:
                    self._initial_brush_radius = 40.0
                    self._initial_brush_strength = 0.5
                try:
                    self._brush_cursor.set_adjusting_state(True)
                except Exception:
                    pass
                self._show_brush_cursor(event.pos())
            else:
                self._is_panning = True
        elif event.button() == Qt.RightButton:
            self._is_zooming = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_painting:
                self._is_painting = False
                self._last_hit_uv = None
                self.paint_finished.emit()
                self._hide_brush_cursor()
            self._is_rotating = False
        elif event.button() == Qt.MiddleButton:
            self._is_panning = False
            self._is_rotating = False
            if self._is_adjusting:
                self._is_adjusting = False
                try:
                    self._brush_cursor.set_adjusting_state(False)
                except Exception:
                    pass
        elif event.button() == Qt.RightButton:
            self._is_zooming = False

    def mouseMoveEvent(self, event):
        dx = event.x() - self._last_mouse.x()
        dy = event.y() - self._last_mouse.y()
        self._last_mouse = event.pos()
        # Alt 调整优先级最高（与2D一致，不需要按键鼠标，只要Alt按下并移动即可）
        if self._alt_pressed and self._is_adjusting:
            dx = event.x() - self._adjust_origin.x()
            dy = event.y() - self._adjust_origin.y()
            if abs(dx) > abs(dy):
                scale_factor = 0.1
                new_radius = self._initial_brush_radius + dx * scale_factor
                new_radius = max(5.0, min(200.0, float(new_radius)))
                try:
                    if hasattr(self, '_canvas'):
                        self._canvas.brush_radius = new_radius
                        self._brush_cursor.set_radius(int(new_radius))
                        self._canvas.brush_properties_changed.emit(new_radius, float(getattr(self._canvas, 'brush_strength', 0.5)))
                except Exception:
                    pass
            else:
                scale_factor = 0.005
                new_strength = self._initial_brush_strength - dy * scale_factor
                new_strength = max(0.01, min(1.0, float(new_strength)))
                try:
                    if hasattr(self, '_canvas'):
                        self._canvas.brush_strength = new_strength
                        self._canvas.brush_properties_changed.emit(float(getattr(self._canvas, 'brush_radius', 40.0)), new_strength)
                except Exception:
                    pass
            # 光标显示在锚点位置
            self._show_brush_cursor(self._adjust_origin)
            self.update()
            return
        # Ctrl+左键优先：旋转，不绘制
        if (event.buttons() & Qt.LeftButton) and (event.modifiers() & Qt.ControlModifier):
            self._is_rotating = True
            self._is_painting = False
            self._hide_brush_cursor()
        # Alt+中键：调整笔刷（与2D一致）
        if self._is_adjusting and (event.buttons() & Qt.MiddleButton):
            dx = event.x() - self._adjust_origin.x()
            dy = event.y() - self._adjust_origin.y()
            # 与2D一致：水平主导则调半径，垂直主导则调强度
            if abs(dx) > abs(dy):
                scale_factor = 0.1
                new_radius = self._initial_brush_radius + dx * scale_factor
                new_radius = max(5.0, min(200.0, float(new_radius)))
                try:
                    if hasattr(self, '_canvas'):
                        self._canvas.brush_radius = new_radius
                        # 更新3D光标半径
                        self._brush_cursor.set_radius(int(new_radius))
                        self._canvas.brush_properties_changed.emit(new_radius, float(getattr(self._canvas, 'brush_strength', 0.5)))
                except Exception:
                    pass
            else:
                scale_factor = 0.005
                new_strength = self._initial_brush_strength - dy * scale_factor
                new_strength = max(0.01, min(1.0, float(new_strength)))
                try:
                    if hasattr(self, '_canvas'):
                        self._canvas.brush_strength = new_strength
                        self._canvas.brush_properties_changed.emit(float(getattr(self._canvas, 'brush_radius', 40.0)), new_strength)
                except Exception:
                    pass
            self._show_brush_cursor(event.pos())
            self.update()
            return
        if self._is_painting and (event.buttons() & Qt.LeftButton):
            uv = self._raycast_uv(event.pos())
            if uv is not None and self._last_hit_uv is not None:
                self._invoke_canvas_brush(self._last_hit_uv, uv)
                self._last_hit_uv = uv
                self._show_brush_cursor(event.pos())
                self.update()
            return
        if self._is_rotating:
            self._cam_yaw += dx * 0.005
            self._cam_pitch += -dy * 0.005
            self._cam_pitch = float(np.clip(self._cam_pitch, -1.2, 1.2))
            self.update()
        elif self._is_panning:
            # Pan in view space: use right and up vectors
            cy = np.cos(self._cam_yaw)
            sy = np.sin(self._cam_yaw)
            cp = np.cos(self._cam_pitch)
            sp = np.sin(self._cam_pitch)
            forward = np.array([cy * cp, sp, sy * cp], dtype=np.float32)
            right = np.array([forward[2], 0.0, -forward[0]], dtype=np.float32)
            right = right / (np.linalg.norm(right) + 1e-8)
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            pan_scale = self._cam_distance * 0.0015
            # Direction: drag right -> move right; drag up -> move up
            self._cam_target += right * dx * pan_scale
            self._cam_target += up * dy * pan_scale
            self.update()
        elif self._is_zooming:
            # Drag right -> zoom in; drag left -> zoom out
            zoom_factor = 1.0 - dx * 0.005
            if zoom_factor < 0.1:
                zoom_factor = 0.1
            self._cam_distance = float(np.clip(self._cam_distance * zoom_factor, 0.2, 100.0))
            self.update()
        else:
            # 非绘制状态下也显示3D笔刷光标
            self._show_brush_cursor(event.pos())

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120.0
        scale = 1.0 - delta * 0.1
        self._cam_distance = float(np.clip(self._cam_distance * scale, 0.2, 100.0))
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self._alt_pressed = True
            # 锚定调整起点（与2D一致）
            pos = self.mapFromGlobal(QCursor.pos())
            if not self.rect().contains(pos):
                pos = QPoint(self.width() // 2, self.height() // 2)
            self._adjust_origin = pos
            try:
                self._initial_brush_radius = float(getattr(self._canvas, 'brush_radius', 40.0))
                self._initial_brush_strength = float(getattr(self._canvas, 'brush_strength', 0.5))
            except Exception:
                self._initial_brush_radius = 40.0
                self._initial_brush_strength = 0.5
            self._is_adjusting = True
            try:
                self._brush_cursor.set_adjusting_state(True)
            except Exception:
                pass
            # 光标固定在锚点（与2D一致）
            self._show_brush_cursor(self._adjust_origin)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self._alt_pressed = False
            self._is_adjusting = False
            try:
                self._brush_cursor.set_adjusting_state(False)
            except Exception:
                pass
        super().keyReleaseEvent(event)

    # ---------- Painting helpers ----------
    def _show_brush_cursor(self, pos):
        try:
            self._brush_cursor.radius = getattr(self._canvas, 'brush_radius', 40)
            self._brush_cursor.set_position(pos)
            if not self._brush_cursor.isVisible():
                self._brush_cursor.show()
            self._brush_cursor.update()
        except Exception:
            pass

    def _hide_brush_cursor(self):
        try:
            self._brush_cursor.hide()
        except Exception:
            pass

    # public for external coordination
    def hide_brush_cursor(self):
        self._hide_brush_cursor()

    def _invoke_canvas_brush(self, last_uv, curr_uv):
        if not hasattr(self, '_canvas') or self._canvas is None:
            return
        try:
            # 将UV转换成 2D画布的 scene 坐标（scene_y 与 2D 定义保持同向，上为正）
            last_scene = QPointF(float(last_uv[0]), float(last_uv[1]))
            curr_scene = QPointF(float(curr_uv[0]), float(curr_uv[1]))
            last_widget = self._canvas.mapFromScene(last_scene)
            curr_widget = self._canvas.mapFromScene(curr_scene)
            self._canvas.apply_brush(last_widget, curr_widget)
            self._canvas.update()
        except Exception as e:
            print(f"invoke_canvas_brush error: {e}")

    # ---------- Ray casting ----------
    def _raycast_uv(self, mouse_pos):
        if not self.model_loaded or self._positions.size == 0 or self._indices.size == 0:
            return None
        # Ray in object space
        ray_origin, ray_dir = self._compute_object_space_ray(mouse_pos.x(), mouse_pos.y())
        if ray_origin is None:
            return None
        # 优先使用BVH
        t, tri_idx, u, v = self._raycast_bvh(ray_origin, ray_dir)
        if t is None or tri_idx is None:
            return None
        tris = getattr(self, '_tri_indices', None)
        if tris is None or tris.size == 0:
            return None
        i0, i1, i2 = tris[int(tri_idx)]
        UV = self._uvs if self._uvs.size else None
        if UV is None:
            return None
        w = 1.0 - u - v
        uv0 = UV[int(i0)]; uv1 = UV[int(i1)]; uv2 = UV[int(i2)]
        hit_uv = uv0 * w + uv1 * u + uv2 * v
        # 无缝处理：在[0,1]范围内取模
        u = float(hit_uv[0]) % 1.0
        v = float(hit_uv[1]) % 1.0
        return (u, v)

    def _compute_object_space_ray(self, mx, my):
        try:
            w = max(1, self.width()); h = max(1, self.height())
            x = (2.0 * mx) / w - 1.0
            y = 1.0 - (2.0 * my) / h
            near = np.array([x, y, -1.0, 1.0], dtype=np.float32)
            far  = np.array([x, y,  1.0, 1.0], dtype=np.float32)
            # 使用渲染时缓存的矩阵，避免尺寸变化带来的不一致
            view = getattr(self, '_last_view', self._compute_view_matrix())
            proj = getattr(self, '_last_proj', self._compute_perspective_matrix(45.0, w/float(h), 0.01, 100.0))
            mvp = proj @ view @ self._model_matrix
            inv = np.linalg.inv(mvp)
            near_obj = inv @ near; far_obj = inv @ far
            if abs(near_obj[3]) > 1e-6:
                near_obj = near_obj / near_obj[3]
            if abs(far_obj[3]) > 1e-6:
                far_obj = far_obj / far_obj[3]
            origin = near_obj[:3]
            direction = far_obj[:3] - origin
            norm = np.linalg.norm(direction) + 1e-8
            direction = direction / norm
            return origin, direction
        except Exception as e:
            print(f"compute ray error: {e}")
            return None, None

    def _intersect_moller_trumbore(self, ray_o, ray_d, v0, v1, v2):
        eps = 1e-8
        e1 = v1 - v0
        e2 = v2 - v0
        pvec = np.cross(ray_d, e2)
        det = np.dot(e1, pvec)
        if -eps < det < eps:
            return None, None, None
        inv_det = 1.0 / det
        tvec = ray_o - v0
        u = np.dot(tvec, pvec) * inv_det
        if u < 0.0 or u > 1.0:
            return None, None, None
        qvec = np.cross(tvec, e1)
        v = np.dot(ray_d, qvec) * inv_det
        if v < 0.0 or u + v > 1.0:
            return None, None, None
        t = np.dot(e2, qvec) * inv_det
        if t <= eps:
            return None, None, None
        return t, u, v

    # ------------- BVH ACCELERATION -------------
    def _build_bvh(self, tri_min, tri_max, tri_centroid, leaf_size: int = 16):
        """构建平铺数组BVH（中位数分割），用于快速光线相交。"""
        N = int(tri_min.shape[0])
        order = np.arange(N, dtype=np.int64)
        mins = []
        maxs = []
        left = []
        right = []
        start = []
        count = []

        def emit_node(bmin, bmax, l, r, s, c):
            mins.append(bmin)
            maxs.append(bmax)
            left.append(l)
            right.append(r)
            start.append(s)
            count.append(c)
            return len(mins) - 1

        # seed root
        root_bmin = np.min(tri_min, axis=0) if N > 0 else np.array([0,0,0], dtype=np.float32)
        root_bmax = np.max(tri_max, axis=0) if N > 0 else np.array([0,0,0], dtype=np.float32)
        root = emit_node(root_bmin, root_bmax, -1, -1, 0, N)
        stack = [(root, 0, N)]  # (node_index, l, r)
        tri_min_local = tri_min
        tri_max_local = tri_max
        tri_cent_local = tri_centroid
        while stack:
            node_index, l, r = stack.pop()
            n = r - l
            if n <= 0:
                start[node_index] = l
                count[node_index] = 0
                continue
            idx = order[l:r]
            bmin = np.min(tri_min_local[idx], axis=0)
            bmax = np.max(tri_max_local[idx], axis=0)
            mins[node_index] = bmin
            maxs[node_index] = bmax
            if n <= leaf_size:
                start[node_index] = l
                count[node_index] = n
                left[node_index] = -1
                right[node_index] = -1
                continue
            # choose axis and split
            ext = bmax - bmin
            axis = int(np.argmax(ext))
            cent = tri_cent_local[idx, axis]
            median_val = np.median(cent)
            sort_idx = np.argsort(cent)
            order[l:r] = idx[sort_idx]
            k = l + (n // 2)
            # emit children
            left_idx = emit_node(np.array([0,0,0], dtype=np.float32), np.array([0,0,0], dtype=np.float32), -1, -1, 0, 0)
            right_idx = emit_node(np.array([0,0,0], dtype=np.float32), np.array([0,0,0], dtype=np.float32), -1, -1, 0, 0)
            left[node_index] = left_idx
            right[node_index] = right_idx
            start[node_index] = -1
            count[node_index] = 0
            # push children to stack
            stack.append((right_idx, k, r))
            stack.append((left_idx, l, k))

        self._bvh_min = np.asarray(mins, dtype=np.float32)
        self._bvh_max = np.asarray(maxs, dtype=np.float32)
        self._bvh_left = np.asarray(left, dtype=np.int32)
        self._bvh_right = np.asarray(right, dtype=np.int32)
        self._bvh_start = np.asarray(start, dtype=np.int32)
        self._bvh_count = np.asarray(count, dtype=np.int32)
        self._bvh_order = order.astype(np.int64, copy=False)

    @staticmethod
    def _ray_aabb_intersect(ro, rd, bmin, bmax):
        inv = 1.0 / (rd + 1e-30)
        t0 = (bmin - ro) * inv
        t1 = (bmax - ro) * inv
        tmin = np.minimum(t0, t1)
        tmax = np.maximum(t0, t1)
        t_enter = np.max(tmin)
        t_exit = np.min(tmax)
        if t_exit >= max(0.0, t_enter):
            return t_enter, t_exit
        return None, None

    def _raycast_bvh(self, ray_origin, ray_dir):
        if not hasattr(self, '_bvh_min'):
            return None, None, None, None
        bmin = self._bvh_min; bmax = self._bvh_max
        left = self._bvh_left; right = self._bvh_right
        start = self._bvh_start; count = self._bvh_count
        order = self._bvh_order
        v0 = getattr(self, '_tri_v0', None)
        e1 = getattr(self, '_tri_e1', None)
        e2 = getattr(self, '_tri_e2', None)
        if v0 is None:
            return None, None, None, None
        stack = [0]
        best_t = float('inf')
        best_idx = -1
        best_u = 0.0; best_v = 0.0
        ro = ray_origin.astype(np.float32)
        rd = ray_dir.astype(np.float32)
        # debug counters
        nodes_visited = 0
        tris_tested = 0
        while stack:
            ni = stack.pop()
            nodes_visited += 1
            tpair = self._ray_aabb_intersect(ro, rd, bmin[ni], bmax[ni])
            if tpair[0] is None or tpair[0] > best_t:
                continue
            l = left[ni]; r = right[ni]
            if l < 0 and r < 0:
                s = start[ni]; c = count[ni]
                if c <= 0:
                    continue
                idx = order[s:s+c]
                v0_leaf = v0[idx]
                e1_leaf = e1[idx]
                e2_leaf = e2[idx]
                pvec = np.cross(rd, e2_leaf)
                det = np.einsum('ij,ij->i', e1_leaf, pvec)
                mask = np.abs(det) > 1e-8
                if not np.any(mask):
                    continue
                inv_det = np.zeros_like(det)
                inv_det[mask] = 1.0 / det[mask]
                tvec = ro - v0_leaf
                u = np.einsum('ij,ij->i', tvec, pvec) * inv_det
                mask &= (u >= 0.0) & (u <= 1.0)
                qvec = np.cross(tvec, e1_leaf)
                v = np.einsum('ij,ij->i', rd[None, :], qvec) * inv_det
                mask &= (v >= 0.0) & (u + v <= 1.0)
                t = np.einsum('ij,ij->i', e2_leaf, qvec) * inv_det
                mask &= (t > 1e-8)
                tris_tested += int(mask.sum())
                if np.any(mask):
                    t_hit = t[mask]
                    min_idx_local = int(np.argmin(t_hit))
                    t_val = float(t_hit[min_idx_local])
                    if t_val < best_t:
                        masked_idx = idx[mask]
                        tri_i = int(masked_idx[min_idx_local])
                        best_t = t_val
                        best_idx = tri_i
                        u_hit = float(u[mask][min_idx_local])
                        v_hit = float(v[mask][min_idx_local])
                        best_u = u_hit; best_v = v_hit
            else:
                if l >= 0: stack.append(l)
                if r >= 0: stack.append(r)
                
        if best_idx >= 0:
            return best_t, best_idx, best_u, best_v
        return None, None, None, None

    # Fallback brute-force (debug)
    def _raycast_bruteforce(self, ro, rd):
        tris = getattr(self, '_tri_indices', None)
        if tris is None or tris.size == 0:
            return None, None, None, None
        P = self._positions; UV = self._uvs
        best_t = float('inf'); best = (-1, 0.0, 0.0)
        for i0, i1, i2 in tris:
            t, u, v = self._intersect_moller_trumbore(ro, rd, P[i0], P[i1], P[i2])
            if t is not None and t < best_t:
                best_t = t; best = (int(i0), float(u), float(v))
        if best[0] >= 0:
            return best_t, best[0], best[1], best[2]
        return None, None, None, None

    # Coordinate cursor between 2D/3D: hide 2D brush when cursor enters 3D; restore on leave
    def enterEvent(self, event):
        try:
            if hasattr(self, '_canvas') and hasattr(self._canvas, 'brush_cursor') and self._canvas.brush_cursor:
                self._canvas.brush_cursor.hide()
            # 在进入3D时显示3D笔刷光标于当前鼠标位置
            try:
                pos = self.mapFromGlobal(QCursor.pos())
                if self.rect().contains(pos):
                    self._show_brush_cursor(pos)
            except Exception:
                pass
        except Exception:
            pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            # 退出3D：隐藏3D笔刷，恢复2D光标
            self._hide_brush_cursor()
            if hasattr(self, '_canvas') and hasattr(self._canvas, 'brush_cursor') and self._canvas.brush_cursor:
                self._canvas.brush_cursor.show()
            # 防止卡住：离开时强制退出调整/旋转/绘制状态
            self._is_adjusting = False
            self._alt_pressed = False
            self._is_rotating = False
            if self._is_painting:
                self._is_painting = False
                self._last_hit_uv = None
                try:
                    self.paint_finished.emit()
                except Exception:
                    pass
        except Exception:
            pass
        return super().leaveEvent(event)

    def focusOutEvent(self, event):
        try:
            # 失去焦点同样清理调整/绘制状态，避免Alt卡死
            self._is_adjusting = False
            self._alt_pressed = False
            self._is_rotating = False
            if self._is_painting:
                self._is_painting = False
                self._last_hit_uv = None
                try:
                    self.paint_finished.emit()
                except Exception:
                    pass
            self._hide_brush_cursor()
        except Exception:
            pass
        return super().focusOutEvent(event)

    def resizeEvent(self, event):
        try:
            if self._brush_cursor:
                self._brush_cursor.resize(self.size())
        except Exception:
            pass
        return super().resizeEvent(event)


