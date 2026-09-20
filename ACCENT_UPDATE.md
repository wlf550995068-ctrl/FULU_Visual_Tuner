# QUESTION / EXCLAMATION 增量升级说明

完成日期：2026-09-17。✓ 当前同一个 FULU Visual Tuner 增量升级，没有第二套项目、没有新增压缩包。本轮只加入两个 Visual Elements，不创建产品顶层 Accent System。

## 从哪里打开

原目录：
C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype

在文件资源管理器地址栏粘贴上面的路径，回车，然后双击 **run.cmd**。已经开着的旧版窗口需先保存、关闭，再重新启动，才会加载新代码。无需解压任何 ZIP。

实际运行命令：

~~~powershell
cd "C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype"
.\.venv\Scripts\python.exe simulator.py --window pyglet
~~~

依赖没有增加；继续使用原 Python 3.12、ModernGL、moderngl-window/pyglet 和窗口内的 ImGui。

## 直接上手

1. 启动后选择右侧 **ACCENT** 标签，区域标题为 **ACCENT / VISUAL ELEMENTS**。
2. Accent Type 选择 QUESTION 或 EXCLAMATION；选择具体符号时自动勾选 Enabled，并立即显示静态编辑预览。NONE 或取消 Enabled 时不绘制符号。
3. 在预览画面中按住符号拖动，也可调整 Position X / Position Y。X 正值向右，Y 正值向上，原点在画面中心，单位相对于设计画面高度。
4. Scale 调整大小，Rotation 调整旋转角度，Opacity 调整透明度。小窗口中参数区可滚动。
5. 点击 **Preview / Play** 完整播放 ENTER → HOLD → EXIT，结束后符号透明。再次点击从 ENTER 重播。
6. **Pause** 暂停当前 Accent 游标；**Resume** 从当前游标继续。**Reset Animation** 回到可见的静态编辑预览，不改任何已调参数。
7. **Reset Accent** 只恢复 Accent 参数并回到静态编辑预览；默认是 disabled / NONE，不影响 Pose、Shape、Volume、原 A/B Motion 或眼睛 Shader。
8. **S / 保存工作台** 保存 Accent 与现有工作台设置；**R / 重新加载库** 经确认后加载已保存配置。
9. **G** 打开原安全区线，同时以绿色细框显示当前符号旋转后的轴对齐包围范围。**V / Esc**、**F** 和原 A/B 播放仍可用。

默认元素位置在主眼外侧上方，可自行移动。编辑器不强制 NORMAL 配 QUESTION 或 HAPPY 配 EXCLAMATION；它们只是两种组合预览例子。编辑器允许手动放到眼睛前方，尚未实现产品级遮挡策略或 Controlled Composition 规则。

## 保存在哪里

仍是 [data/pose_library.json](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/data/pose_library.json)，在原有顶层字段旁增加独立的 accent 记录：

~~~json
{
  "accent": {
    "enabled": false,
    "type": "NONE",
    "position": {"x": 0.53, "y": 0.28},
    "scale": 1.0,
    "rotation": 0.0,
    "opacity": 1.0,
    "animation": "simple_pop"
  }
}
~~~

旧配置缺少 accent 时自动补默认值；原 Pose、Shape、Volume、Motion 和选择值保持不变。当前实际文件已追加默认 Accent，未改已有参数。

保存的是矢量渲染参数与动画配置引用，不是最终图片或序列帧。重新启动加载参数，但不恢复正在播放到第几秒：启动进入静态编辑预览，可再次 Play。

「保存此 Pose」仍只保存那个 Pose，不会保存 Accent；要保存组合编辑设置，使用 **S / 保存工作台**。

参数调整与拖动复用原 TuningSession Undo / Redo；一次连续拖动是一条历史。Reset Accent 可撤销。原 Shape / Volume / Motion Reset 都不改 Accent；原「恢复全部默认」的确认说明新增 Accent，并一起恢复其默认值。

## 如何渲染

新增独立 VisualElementRenderer，通过现有 OpenGL 上下文在眼睛绘制之后，对同一帧缓冲进行透明叠加。

- QUESTION：两段三次贝塞尔曲线离散为连续短线段，加短竖段和独立圆点。
- EXCLAMATION：圆端竖线段加独立圆点。
- 新片元 Shader 计算到线段胶囊体、圆点的距离，做按屏幕尺寸计算的抗锯齿。
- 缩放、旋转在符号自己的局部坐标中计算，不依赖固定屏幕像素。
- 单一临时浅蓝填色，没有卡通描边、霓虹、外部光晕或贴图动画。
- NONE、未启用或零透明度直接跳过绘制。
- 现有 EyeRenderer、Eye Rig、主眼 GLSL 文件、Volume 与 Shape 数学文件均未改。

这是工程验证符号，曲线与笔画未作最终艺术定稿。贝塞尔采用固定的细分矢量线段，本轮 UI 允许的缩放范围内已经检查渲染效果；不是无限精度曲线求距器。

## 安全区如何限制

根据实际绘制的线段和圆点，逐点变换缩放与旋转，再计入笔画/圆点半径，计算 x/y 的完整外接范围。安全区中心可移动范围由“安全矩形减去整个符号边界”得到，而不是只限制中心。

- 拖动、Position、Scale、Rotation 或 Type 改变时统一重新 clamp。
- 必要时减小 Scale 以容纳整个元素，再调整中心。
- 为抗锯齿预留 0.008 个设计高度单位的余量。
- 动画最大尺寸不超过设定 Scale，所以 ENTER/EXIT 期间也保持安全。
- Shader 额外以实际安全矩形裁掉外部像素，作为极小预览尺寸下的最终保护。
- 原窗口按统一设计坐标缩放；高 DPI 拖动使用 ImGui 逻辑尺寸，GPU 使用实际帧缓冲尺寸。
- 已保存的非法越界配置会被校验拒绝，不悄悄带着越界状态运行。

绿色包围框是诊断辅助；它的轴对齐空白角落不代表符号真实填充。

## 动画与时间来源

生命周期配置集中在 [fulu_visual/config.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/fulu_visual/config.py) 的 ACCENT_ANIMATIONS：

| 配置 | 当前值 |
|---|---|
| 配置引用 | simple_pop |
| ENTER | 0.24 秒，不透明度 0→1，尺寸 0.86→1 |
| HOLD | 0.90 秒，保持目标尺寸与透明度 |
| EXIT | 0.28 秒，不透明度 1→0，尺寸 1→0.94 |
| easing | minimum_jerk，连续五次缓动 |

复用原窗口 on_render 的 frame_time，同一帧的时间增量分别推进原 A/B 播放和 Accent 的生命周期游标；没有第二个系统时钟、定时器或后台动画循环。Accent Pause 只暂停 Accent，不控制主眼 A/B。没有改写原 MotionPlayer。

## 修改与新增文件

修改：
- [simulator.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/simulator.py)：ACCENT 区、鼠标拖动、同帧叠加、沿用时间增量、Reset/保存入口及测试开关；原面板继续保留。
- [fulu_visual/config.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/fulu_visual/config.py)：追加 Accent 默认值、校验、编辑 clamp、分组恢复、旧 JSON 兼容。
- [data/pose_library.json](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/data/pose_library.json)：只追加默认 accent 记录。
- [README.md](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/README.md)、[TEST_REPORT.md](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/TEST_REPORT.md)：增加本轮说明入口和结果。

新增：
- [fulu_visual/visual_elements.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/fulu_visual/visual_elements.py)：两个符号的矢量定义、实际范围、clamp 和最小生命周期游标。
- [fulu_visual/element_renderer.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/fulu_visual/element_renderer.py)：独立透明叠加 Renderer。
- [shaders/visual_element.frag](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/shaders/visual_element.frag)：符号距离场与抗锯齿。
- [tests/test_visual_elements.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/tests/test_visual_elements.py)：17 项配置、动画、GPU 增量测试。
- [tests/accent_smoke.py](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/tests/accent_smoke.py)：真实窗口交互回归。
- 本说明，以及 test_output/accent 内的测试证据和截图。

未改：主眼 Shader / Renderer / Rig、原 MotionPlayer、几何模块、帧率计时器、原逻辑与 GPU 测试、依赖和启动脚本。主项目与 sources 资料均未改。

## 实际测试

✓ 共 **38 项测试通过**：原 21 项 + 新增 17 项。

新增测试覆盖：NONE/禁用/零透明度时逐像素等于原眼睛画面；两种符号可区分；X/Y、Scale、Rotation、Opacity 实际改变 GPU 像素；旋转、大尺寸和四个角落 clamp；ENTER/HOLD/EXIT；暂停续播；Reset 隔离；Undo/Redo；原 Pose 保存不覆盖 Accent；旧配置兼容；另起 Python 进程读回已保存 Accent。

✓ 原 **655 条 GPU 检查**继续通过，原眼睛 Renderer 与 Shader 文件哈希未变。

✓ 原 15 秒窗口回归通过，实测平均 **58.81 FPS**。覆盖 Pose 编辑、A/B 往返、暂停/续播/步进、保存、各 Reset 和 Inspect。

✓ Accent 11 秒真实窗口回归通过，实测平均 **59.10 FPS**，P95 **17.07 ms**。实际注入 ImGui 下拉选择、按钮、滑杆和拖动事件，验证拖到屏幕外被 clamp、一次 Undo 撤销拖动、动画完整生命周期、暂停不推进、Reset 只改 Accent、保存重载、Inspect/F/G 与眼睛动画同时运行。

上述是实际 GPU 窗口加软件输入事件，不是人工鼠标肉眼验收。用户最终艺术验收尚未完成；不宣称恒定锁 60 FPS。

证据：
- [Accent 窗口报告](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/accent/window_smoke.json)
- [原窗口回归报告](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/window_smoke.json)
- [原 GPU 回归报告](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/gpu_report.json)
- [NORMAL + QUESTION](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/accent/normal_question.png)
- [HAPPY + EXCLAMATION](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/accent/happy_exclamation.png)
- [ACCENT 工作台](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/accent/accent_final_workbench.png)
- [旋转大符号与安全框](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/accent/exclamation_safe_bounds_workbench.png)

复现：

~~~powershell
cd "C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_gpu.py
.\.venv\Scripts\python.exe simulator.py --window pyglet --smoke-seconds 15
.\.venv\Scripts\python.exe simulator.py --window pyglet --accent-smoke --smoke-seconds 11
~~~

窗口测试使用独立 test_output/accent/smoke_library.json，不会向实际 Pose 库写入测试组合。

## 明确未做

没有其他 Visual Elements、泪水、腮红、火焰、光效、粒子、Performance/彩蛋、其他 BASE、完整 RESPONSE、Controlled Composition 产品语义规则、Sound、Light、身体 Motion 或主项目集成。没有引入大型框架、素材数据库、插件系统或通用时间线。

本轮到“两个元素能编辑 → 实时预览 → 动画 → 保存 → 重启恢复 → 安全区限制”完成为止。

