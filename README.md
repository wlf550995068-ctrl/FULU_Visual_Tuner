# FULU Visual Tuner

Procedural real-time robot eye visual editor.

独立的电子眼视觉编辑工作台。Python 3.12、ModernGL、moderngl-window 和 GLSL 在每一帧绘制左右两只独立眼睛；Pose 是参数与闭合轮廓，动画由实时插值产生。工作台与 FULU 主产品系统分离。

## Windows 安装与启动

需要 Python 3.12（安装时启用 Python Launcher）、支持 OpenGL 3.3 的显卡驱动，以及 Windows 自带的微软雅黑字体。当前实际验证平台为 Windows，其他平台未验证。

```powershell
git clone https://github.com/wlf550995068-ctrl/FULU_Visual_Tuner.git
cd FULU_Visual_Tuner
.\run.cmd
```

也可以直接双击项目目录里的 `run.cmd`。首次启动会创建本地 `.venv` 并安装锁定依赖；首次安装需要网络。后续使用现有环境。环境、可控缓存和个人数据保存在项目目录，不需要提交到仓库。

手动安装：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe simulator.py --window pyglet
```

## 编辑流程

- **Pose**：选择、新建、复制、重命名、保存、加载；NORMAL 保护，内置 Pose 不可删除，自定义 Pose 可删除。新建自定义记录不会改写产品 BASE 分类。
- **Shape / Contour**：保留宽高、间隔、圆角、整体弯曲、上下缘、厚度、鼓起、收缩、压缩、拉伸、位置、旋转、透明度，以及左右眼独立参数。零尺寸或零透明度可隐藏眼睛，非法值会被验证器拒绝。
- **Contour**：圆、矩形、三角只是闭合轮廓的创建起点；在编辑区拖动控制点，添加/删除点，并选择双眼或单眼轮廓。内置 Pose 创建轮廓时生成自定义记录，保护原图。支持不同轮廓之间的连续过渡。复杂轮廓与极端形变仍标记 **Experimental / 待验收**，不保证所有自交或折叠造型可用。
- **Volume**：Depth 控制立体程度，0 为纯平面（边缘仍抗锯齿）；增加后进入当前 2.5D 曲面效果。Surface Roundness 和 Bulge Influence 调整曲面。不是三维网格模型。
- **Light**：Center Fill、Side Falloff、Bottom Falloff、Edge Falloff、Edge Softness。最终颜色待批准参考图校准。
- **Motion**：选择 Source / Target，自动 A → B → A；暂停、继续、拖动时间轴和小步检查。响应越大，过渡越快。
- **Runtime**：看左 / 回中 / 看右、Shake；从实际 Pose Library 选择目标并播放。正在过渡时可重新指定目标，从当前插值状态继续。看向一侧后短暂停留、平滑回中；Shake 短暂摆动后恢复当前状态。Look / Shake 待肉眼验收。
- **Accent**：仅 QUESTION / EXCLAMATION，独立调整位置、大小、旋转、透明度与 ENTER / HOLD / EXIT。边界包含尺寸和旋转，限制在安全区。**Experimental / Unverified**。
- **Reference**：导入 PNG/JPG/WEBP/BMP，显示隐藏、透明叠加、Fit/Fill/1:1、位置、缩放、左右对照。只用于人工比对，不改变眼睛参数；原文件不修改，工作台保存自己的参考副本。
- **Inspect**：平面检查、安全区、清洁画面、截图。

## 保存与恢复

`data/pose_library.json` 保存 Pose、轮廓、工作台参数、Accent、参考图设置与当前选择。首次启动自动建立 NORMAL/HAPPY 默认库。**保存此 Pose** 只保存当前 Pose；**保存工作台** 保存整个编辑状态。重新加载库会恢复已保存数据。

Shape Reset 只恢复当前 Pose；Volume Reset 恢复现有体积/光感参数组；Motion Reset 只恢复播放设置；Reset Accent 只恢复辅助元素。Restore All 需要确认；Undo / Redo 保留。参考副本在 `assets/references/`，截图在 `captures/`。这些个人文件被 Git 忽略，请自行备份，发布源码不会携带它们。

文本框支持 Ctrl+C/V/X/A 和右键菜单，长中文自动换行与纵向滚动；视觉换行不会写入路径或名称。

## 键位

仅在不输入文本、没有 Ctrl/Shift/Alt 修饰键时生效：

| 键 | 功能 |
| --- | --- |
| N / H | NORMAL / HAPPY |
| Space / P | 播放或暂停 |
| → | 小步前进 |
| V | 进入 / 退出 Inspect |
| Esc | Inspect 中返回编辑；编辑中请求关闭 |
| F / G | 平面检查 / 安全区 |
| S / R | 保存工作台 / 重新加载库 |
| Z / Y | Undo / Redo |
| F12 | 截图 |

## 测试

```powershell
.\.venv\Scripts\python.exe -B verify_upgrade.py
.\.venv\Scripts\python.exe -B verify_gpu.py
.\run.cmd --upgrade-smoke --smoke-seconds 12
.\run.cmd --accent-smoke --smoke-seconds 12
.\run.cmd --input-smoke --smoke-seconds 30
```

窗口测试会打开实际 GPU 窗口、注入控件与按键事件，使用独立测试配置，结果写到忽略的 `test_output/`；输入测试使用系统剪贴板并在退出时恢复。测试运行期间请不要操作测试窗口或剪贴板。私人像素基线不在仓库，相关回归测试在缺少基线时会明确 skip。自动测试不能代替视觉验收。

## 目录

```text
simulator.py           窗口、编辑 UI、每帧循环
fulu_visual/
  config.py            Pose 库、参数约束、保存、Undo/Redo
  geometry.py          几何、闭合轮廓、变形与插值
  rig.py               左右眼实时实体
  renderer.py          现有 GPU 渲染器
  motion.py            A/B 播放
  runtime.py           可打断过渡与动作预览
  reference.py         人工参考图
  tuner_extensions.py  轮廓、参考、Runtime、文本输入控件
  visual_elements.py   两种独立辅助元素
shaders/               GLSL
tests/                 有效单元、GPU 和窗口测试
run.cmd                Windows 启动
requirements*.txt      依赖
```

贡献方式见 CONTRIBUTING.md。许可证尚未确定，见 LICENSE_PENDING.md；当前不声明已采用任何正式开源许可证。当前工作仅限独立视觉编辑工具，不包含产品主系统或新的表情内容制作。
