# Flowmap Canvas | 流向图画布

<div align="center">
  <a href="#english" id="en-btn">English</a> | 
  <a href="#中文" id="zh-btn">中文</a>
</div>

---

<div id="english">

# Flowmap Canvas

Flowmap Canvas is a powerful and easy-to-use flowmap drawing tool, designed for game developers and 3D artists.

## Why Choose Flowmap Canvas?

Compared to other flowmap editing tools on the market, Flowmap Canvas offers these advantages:

- **Open Source & Extensible**: Built with Python, making it highly customizable and extensible
- **Seamless Texture Support**: Create perfectly tileable flowmaps with built-in seamless texture editing
- **3D Model Drawing Support**: Draw flow effects directly on 3D models
- **Better Drawing Experience**: Unlike other drawing tools, our brush system uses additive mode instead of overwrite mode, making it easy to draw flow branches and improving the drawing experience
- **Real-time Preview**: Adjust flow speed and distortion in real-time for intuitive preview
- **High-Precision Export**: Export flowmaps in high-resolution TGA format for professional use

Flowmap Canvas makes creating flowmaps simple and efficient for both beginners and professional artists.

## What is a Flowmap?

A flowmap is a special texture used in game development to control the directional flow of materials, commonly used in:
- Controlling water, lava, and other liquid material directions
- Guiding fabric and hair material directions

- UV distortion and dynamic texture deformation

Flowmaps typically encode direction vectors in the red and green channels:
- Red channel (R) represents flow in the X direction
- Green channel (G) represents flow in the Y direction

## Features

### Easy-to-Use Drawing System
- Drawing strokes don't overwrite previous drawing results
- Real-time flow effect preview for intuitive understanding of results

### Powerful Editing Features
- Seamless texture editing support
- Support for drawing on 3D models and collaborative drawing between 2D and 3D interfaces

### Advanced Preview Features
- Tile preview mode support
- Real-time flow animation preview
- Adjustable flow speed and distortion

### Complete File Operations
- Load and save flowmaps
- Export to high-resolution TGA format

## Download Application
If you want to use this tool directly, please download the latest software from the Release page. Currently only `x86 windows` version is released.
`https://github.com/dolag233/FlowmapCanvas/releases`

## Build Development Environment
If you want to run from source code rather than using the packaged executable, please check `docs/build_dev_environment.md` to set up the development environment.

## System Requirements

- Windows 7/8/10/11
- OpenGL 3.2+ support
- Python 3.9+ (if running from source)
- 4GB RAM recommended
- GPU with OpenGL 3.2 support

## License

GPL v3 License - See the LICENSE file in the project for details.

</div>

---

<div id="中文">

# 流向图画布

流向图画布是一个功能强大、易于使用的流向图(Flowmap)绘制工具，专为游戏开发者、3D艺术家设计。

![](img/Flowmap%20Canvas.gif)

## 为什么选择流向图画布？

相比市面上其他流向图编辑工具，流向图画布具有以下优势：

- **开源可扩展**：使用Python开发，高度可定制和扩展
- **四方连续支持**：内置四方连续贴图编辑功能，轻松创建无缝贴图
- **支持模型绘制**: 支持在三维模型上直接绘制流动效果
- **更优的绘制体验**：与其他绘制工具不同，我们的笔刷系统采用叠加模式而不是覆盖模式，能够轻松绘制流向分支，提升绘制体验
- **实时预览**：支持实时调整流动速度和扭曲程度，直观预览效果
- **高精度导出**：支持导出高精度TGA格式，满足专业需求

流向图画布让流向图的创建变得简单而高效，无论是初学者还是专业艺术家，都能轻松掌握并创建出精美的流向效果。

## 什么是流向图(Flowmap)？

流向图是游戏开发中使用的一种特殊纹理贴图，用于控制材质的流动方向，常用于以下场景：
- 水流、岩浆等液体材质的方向控制
- 布料、毛发等材质的方向引导
- UV扰动和动态纹理变形

流向图通常将方向向量编码在红绿通道中：
- 红色通道(R)代表X方向的流动
- 绿色通道(G)代表Y方向的流动

## 功能特性

### 好用的绘制系统
- 绘制笔触不会覆盖之前的绘制结果
- 实时预览流动效果，直观了解绘制结果

### 强大的编辑功能
- 支持四方连续(Seamless)贴图编辑
- 支持在3D模型上绘制以及2D和3D界面协同绘制

### 高级预览功能
- 支持预览重复(Tile)模式
- 实时流动动画预览
- 可调整流动速度和扭曲程度

### 完善的文件操作
- 支持加载和保存流向图
- 支持导出为高精度TGA格式

## 下载应用
如果您想要直接使用此工具，请在Release页面下载最新的软件。目前仅发布`x86 windows`版本软件。
`https://github.com/dolag233/FlowmapCanvas/releases`

## 搭建开发环境
如果您想从源代码运行而不是使用打包好的可执行文件，请按查看 `docs/build_dev_environment.md` 搭建开发环境。

## 系统要求

- Windows 7/8/10/11
- OpenGL 3.2+支持
- Python 3.9+（如果从源代码运行）
- 建议4GB RAM
- 支持OpenGL 3.2的GPU

## 许可证

GPL v3许可证 - 请查看项目中的LICENSE文件了解详情。

</div>
