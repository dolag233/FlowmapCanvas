"""
资源定位器模块 - 帮助程序在开发模式和PyInstaller打包后都能正确定位资源文件
"""

import os
import sys


def is_bundled():
    """检查程序是否是由PyInstaller打包的"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_base_path():
    """获取基础路径，适用于开发环境和打包环境"""
    if is_bundled():
        # PyInstaller创建临时文件夹，并将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    else:
        # 开发环境下的基础路径
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    return base_path


def get_resource_path(relative_path):
    """
    获取资源的绝对路径，适用于开发环境和打包环境
    
    Args:
        relative_path: 相对于项目根目录的路径
        
    Returns:
        资源的绝对路径
    """
    base_path = get_base_path()
    return os.path.join(base_path, relative_path)


# 示例使用方法
if __name__ == "__main__":
    # 测试资源定位
    shader_path = get_resource_path("flow_shader.glsl")
    preview_shader_path = get_resource_path("preview_shader.glsl")
    print(f"Shader路径: {shader_path}")
    print(f"文件存在: {os.path.exists(shader_path)}")
    print(f"Preview Shader路径: {preview_shader_path}")
    print(f"文件存在: {os.path.exists(preview_shader_path)}")
    # 打印环境信息
    print(f"是否为打包环境: {is_bundled()}")
    print(f"基础路径: {get_base_path()}") 