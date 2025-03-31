from collections import deque
from PyQt5.QtCore import QObject

class Command:
    def execute(self):
        """执行命令，子类必须实现此方法"""
        raise NotImplementedError
    
    def undo(self):
        """撤销命令，子类必须实现此方法"""
        raise NotImplementedError
    
    def redo(self):
        """重做命令，默认调用execute"""
        self.execute()

class CommandManager(QObject):
    def __init__(self, max_history=100):
        super().__init__()
        self.max_history = max_history
        self.undo_stack = []  # 撤销栈，保存已执行的命令
        self.redo_stack = []  # 重做栈，保存已撤销的命令
        self.undo_stack_changed = None  # 钩子函数，撤销栈变化时调用
        self.redo_stack_changed = None  # 钩子函数，重做栈变化时调用

    def execute_command(self, command):
        """执行一个新命令"""
        command.execute()
        self.undo_stack.append(command)
        # 限制撤销栈大小
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)  # 移除最早的命令
        # 清空重做栈
        self.redo_stack.clear()  
        
        # 强制更新UI状态
        print(f"执行命令 - 撤销栈: {len(self.undo_stack)}, 重做栈: {len(self.redo_stack)}")
        # 确保回调被调用
        if self.undo_stack_changed:
            self.undo_stack_changed()
        if self.redo_stack_changed:
            self.redo_stack_changed()

    def undo(self):
        """撤销上一个命令"""
        if not self.undo_stack:
            print("没有操作可以撤销")
            return
        
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        
        # 立即更新UI
        print(f"撤销操作 - 撤销栈: {len(self.undo_stack)}, 重做栈: {len(self.redo_stack)}")
        # 确保回调被立即调用
        if self.undo_stack_changed:
            self.undo_stack_changed()
        if self.redo_stack_changed:
            self.redo_stack_changed()

    def redo(self):
        """重做上一个撤销的命令"""
        if not self.redo_stack:
            print("没有操作可以重做")
            return
        
        command = self.redo_stack.pop()
        # 确保调用的是redo方法而不是execute方法
        if hasattr(command, "redo") and callable(command.redo):
            command.redo()  # 使用redo方法重做操作
        else:
            # 如果没有redo方法，则使用execute作为后备
            command.execute()  # 使用execute方法作为后备
            
        self.undo_stack.append(command)
        
        # 立即更新UI
        print(f"重做操作 - 撤销栈: {len(self.undo_stack)}, 重做栈: {len(self.redo_stack)}")
        # 确保回调被立即调用
        if self.undo_stack_changed:
            self.undo_stack_changed()
        if self.redo_stack_changed:
            self.redo_stack_changed()

    def clear(self):
        """清空命令栈"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        # 触发回调
        if callable(self.undo_stack_changed):
            self.undo_stack_changed()
        if callable(self.redo_stack_changed):
            self.redo_stack_changed()

    def can_undo(self):
        """是否可以撤销"""
        return len(self.undo_stack) > 0

    def can_redo(self):
        """是否可以重做"""
        return len(self.redo_stack) > 0