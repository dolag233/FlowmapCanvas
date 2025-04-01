# Flowmap Canvas | 流向图画布

<div align="center">
  <a href="#english" id="en-btn">English</a> | 
  <a href="#中文" id="zh-btn">中文</a>
</div>

---

<div id="english">

# Flowmap Canvas

Flowmap Canvas is a powerful and easy-to-use tool for creating and editing flowmaps, designed for 3D artists, game developers, and technical artists.

## Why Choose Flowmap Canvas?

Compared to other flowmap editing tools on the market, Flowmap Canvas offers these advantages:

- **User-friendly interface**: Designed for artists, no programming knowledge required
- **Real-time preview**: Instantly see flow effects, eliminating repetitive export testing
- **Performance optimization**: Maintains smooth operation even with high-resolution textures
- **Seamless tiling support**: Create perfectly tileable flowmaps with ease
- **Open source**: Completely free and open source, customizable to your needs

Flowmap Canvas makes creating flowmaps simple and efficient for both beginners and professional artists.

## What is a Flowmap?

A flowmap is a special texture used to control the directional flow of materials, commonly used in:
- Controlling water, lava, and other liquid material directions
- Guiding fabric and hair material directions
- Simulating wind effects
- UV distortion and dynamic texture deformation

Flowmaps typically encode direction vectors in the red and green channels:
- Red channel (R) represents flow in the X direction
- Green channel (G) represents flow in the Y direction

## Key Features

### Intuitive Drawing System
- Pressure-sensitive brush support for precise flow drawing
- Real-time flow effect preview
- Seamless texture editing support
- High-precision and standard precision modes

### Powerful Editing Tools
- Left-click to draw, right-click to erase
- Middle-click to pan canvas, scroll wheel to zoom
- Alt+drag to adjust brush size and strength
- Flow fill functionality

### Advanced Preview Features
- Adjustable preview window position
- Tile preview mode support
- Real-time flow animation preview
- Adjustable flow speed and distortion

### Comprehensive File Operations
- Load and save flowmaps
- Export to TGA format
- High-resolution export support

## Technical Features

- High-performance real-time rendering based on OpenGL
- Modular design with clear code structure
- High-resolution texture processing
- Optimized brush engine for smooth drawing experience
- Support for both DirectX and OpenGL coordinate systems

## How to Use

1. Run `run_flowmap_canvas.bat` to start the program
2. Use left-click to draw flow, right-click to erase
3. Use middle-click to drag canvas, scroll wheel to zoom
4. Alt+drag to adjust brush properties
5. Adjust various parameters through the settings panel
6. Export as TGA format for use

</div>

---

<div id="中文">

# 流向图画布

流向图画布是一个功能强大、易于使用的流向图(Flowmap)创建和编辑工具，专为3D艺术家、游戏开发者和技术美术工作者设计。

## 为什么选择流向图画布？

相比市面上其他流向图编辑工具，流向图画布具有以下优势：

- **用户友好界面**：专为艺术家设计，无需编程知识
- **实时预览**：即时看到流动效果，避免反复导出测试
- **性能优化**：即使处理高分辨率纹理也能保持流畅
- **四方连续支持**：无缝贴图绘制功能，解决拼接问题
- **开源免费**：完全开源，可根据需求自由扩展

流向图画布让流向图的创建变得简单而高效，无论是初学者还是专业艺术家，都能轻松掌握并创建出精美的流向效果。

## 什么是流向图(Flowmap)？

流向图是一种特殊的纹理贴图，用于控制材质的流动方向，常用于以下场景：
- 水流、岩浆等液体材质的方向控制
- 布料、毛发等材质的方向引导
- 风场效果模拟
- UV扰动和动态纹理变形

流向图通常将方向向量编码在红绿通道中：
- 红色通道(R)代表X方向的流动
- 绿色通道(G)代表Y方向的流动

## 主要功能

### 直观的绘制系统
- 支持压力感应笔刷，让流向绘制更加精准
- 实时预览流动效果，直观了解绘制结果
- 支持四方连续(Seamless)贴图编辑
- 支持高精度和标准精度模式

### 强大的编辑工具
- 左键绘制，右键擦除
- 中键拖动画布，滚轮缩放
- Alt+拖动调整笔刷大小和强度
- 支持流向填充功能

### 高级预览功能
- 可调整预览窗口显示位置
- 支持预览重复(Tile)模式
- 实时流动动画预览
- 可调整流动速度和扭曲程度

### 完善的文件操作
- 支持加载和保存流向图
- 支持导出为TGA格式
- 支持高分辨率导出

## 技术特点

- 基于OpenGL的高性能实时渲染
- 模块化设计，代码结构清晰
- 支持高分辨率纹理处理
- 优化的笔刷引擎，支持流畅的绘制体验
- 支持DirectX和OpenGL坐标系统切换

## 使用方法

1. 运行`run_flowmap_canvas.bat`启动程序
2. 使用左键绘制流向，右键擦除
3. 使用中键拖动画布，滚轮缩放
4. Alt+拖动调整笔刷属性
5. 通过设置面板调整各种参数
6. 导出为TGA格式使用

![](img/Flowmap%20Canvas.gif)

</div>
