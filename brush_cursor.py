"""
笔刷光标模块 - 提供绘图区域的笔刷预览功能
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush

class BrushCursorWidget(QWidget):
    """实现画布上的笔刷光标预览"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.curr_pos = QPoint(0, 0)
        self.radius = 10
        self.is_drawing = False
        self.is_adjusting = False  # 是否正在调整笔刷（Alt+拖拽）
        self.canvas_ref = parent

    def set_radius(self, radius):
        """设置笔刷半径"""
        self.radius = radius
        self.update()

    def set_position(self, pos):
        """设置笔刷位置"""
        self.curr_pos = pos
        self.update()

    def set_drawing_state(self, is_drawing):
        """设置是否正在绘制"""
        self.is_drawing = is_drawing
        self.update()

    def set_adjusting_state(self, is_adjusting):
        """设置是否正在调整笔刷（Alt+拖拽）"""
        self.is_adjusting = is_adjusting
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if hasattr(self, 'canvas_ref') and self.canvas_ref:
            # 从画布获取当前笔刷强度
            strength = self.canvas_ref.brush_strength if hasattr(self.canvas_ref, 'brush_strength') else 0.5

            # 根据状态调整颜色
            if self.is_drawing:
                # 绘制时使用灰色的圆框
                circle_color = QColor(180, 180, 180, 200)
                fill_color = QColor(120, 120, 150, int(100 * strength))
            elif self.is_adjusting:
                # 调整笔刷大小/强度时使用高亮黄色
                circle_color = QColor(255, 255, 0, 200)  # 明亮的黄色
                fill_color = QColor(200, 200, 100, int(100 * strength))  # 明亮的填充色
            else:
                # 普通状态下使用白色圆框
                circle_color = QColor(255, 255, 255, 200)
                fill_color = QColor(100, 100, 255, int(100 * strength))

            # 绘制半透明的画笔轮廓
            line_width = 2 if not self.is_adjusting else 3  # 调整时使用更粗的线
            painter.setPen(QPen(circle_color, line_width))
            painter.setBrush(QBrush(fill_color))
            painter.drawEllipse(self.curr_pos, self.radius, self.radius)

            # 绘制方向指示中心点
            center_radius = 2 if not self.is_adjusting else 3  # 调整时使用更大的中心点
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(self.curr_pos, center_radius, center_radius) 