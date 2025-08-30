from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GL import shaders
from OpenGL.error import GLError
import numpy as np
import ctypes

from mesh_loader import MeshData


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
    if (u_repeat) {
      color0 = texture(baseMap, fract(uv + offset0));
      color1 = texture(baseMap, fract(uv + offset1));
    } else {
      vec2 s0 = clamp(uv + offset0, 0.0, 1.0);
      vec2 s1 = clamp(uv + offset1, 0.0, 1.0);
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
    def __init__(self, parent=None):
        super().__init__(parent)
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
        # fit
        self._fit_model_matrix()
        # upload
        self.makeCurrent()
        try:
            self._create_buffers()
        finally:
            try: self.doneCurrent()
            except Exception: pass
        self.model_loaded = True
        self.update()

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
            self._is_rotating = True
        elif event.button() == Qt.MiddleButton:
            self._is_panning = True
        elif event.button() == Qt.RightButton:
            self._is_zooming = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_rotating = False
        elif event.button() == Qt.MiddleButton:
            self._is_panning = False
        elif event.button() == Qt.RightButton:
            self._is_zooming = False

    def mouseMoveEvent(self, event):
        dx = event.x() - self._last_mouse.x()
        dy = event.y() - self._last_mouse.y()
        self._last_mouse = event.pos()
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

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120.0
        scale = 1.0 - delta * 0.1
        self._cam_distance = float(np.clip(self._cam_distance * scale, 0.2, 100.0))
        self.update()


