"""
命令模式模块 - 实现撤销/重做功能的命令类
"""

from command_manager import Command
from parameter_registry import ParameterRegistry
import numpy as np

class BrushStrokeCommand(Command):
    """绘制笔刷命令 - 记录并管理绘制操作的撤销/重做"""
    
    def __init__(self, canvas, flowmap_data_before):
        self.canvas = canvas
        self.flowmap_data_before = flowmap_data_before.copy()
        self.flowmap_data_after = None

    def execute(self):
        # 每次绘制后保存当前状态
        self.flowmap_data_after = self.canvas.flowmap_data.copy()

    def undo(self):
        if self.flowmap_data_before is not None:
            self.canvas.flowmap_data = self.flowmap_data_before.copy()
            self.canvas.update_texture_from_data()
            self.canvas.update()

    def redo(self):
        if self.flowmap_data_after is not None:
            self.canvas.flowmap_data = self.flowmap_data_after.copy()
            self.canvas.update_texture_from_data()
            self.canvas.update()


class ParameterChangeCommand(Command):
    """参数变更命令 - 通过注册表应用，保持 Model+UI 一致"""
    
    def __init__(self, registry: ParameterRegistry, key, old_value, new_value):
        self.registry = registry
        self.key = key
        self.old_value = old_value
        self.new_value = new_value

    def execute(self):
        self.registry.apply(self.key, self.new_value, transient=False)

    def undo(self):
        self.registry.apply(self.key, self.old_value, transient=False)