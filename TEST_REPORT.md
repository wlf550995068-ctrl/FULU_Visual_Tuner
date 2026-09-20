# FULU Pose Editor 升级验收记录

## 2026-09-17 Visual Elements 增量验证

✓ 当前共 38 项逻辑/渲染测试通过（原 21 + 新增 17）；原 655 条 GPU 检查与原窗口回归继续通过。QUESTION / EXCLAMATION 的实际窗口拖动、动画、独立 Reset、保存重载与安全区检查通过，平均 59.10 FPS。主眼 Shader / Renderer / Rig 和原 MotionPlayer 未修改。完整新增结果见 [ACCENT_UPDATE.md](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/ACCENT_UPDATE.md)。下文保留上轮 Pose Editor 阶段的记录与限制，性能数字属于各自运行，不混用。

日期：2026-09-16。本报告对应本轮升级，不沿用旧 Tuner 测试结果。

## 环境与范围

Windows / Python 3.12.10 / RTX 4060 Ti / OpenGL 3.3.0 NVIDIA 610.88。
ModernGL 5.12.0、moderngl-window 3.1.1、pyglet 2.1.16、imgui-bundle 1.6.3。
现有依赖未变，pip check 通过；Python 编译检查通过。
本轮只修改独立 FULU_Visual_GPU_Prototype 和更新交付 ZIP。sources、正式 Visual V2 分类及主系统未修改。

## 实际结果

| 验证 | 实测结果 |
|---|---|
| 逻辑测试 | 21 项全部通过 |
| 持久化 | NORMAL/HAPPY 分别保存，复制/新建/重命名/删除，JSON 原子写入；另起 Python 进程确认自定义记录仍存在 |
| Undo / Redo | 滑杆拖动合并、分组恢复、全部恢复、库操作通过 |
| 默认保护 | NORMAL 不能删除或改名；内置 HAPPY 不能删除 |
| 分组 Reset | Shape 只改当前 Pose；Volume 与 Motion 相互隔离；全部恢复保留自定义记录 |
| 时间轴 | 自动完整往返、暂停不推进、续播保留游标、拖动后暂停、小步前进、不同帧率结果一致 |
| 几何 | Whole Bend 正负方向上下边界共同弯曲；Thickness/Center Bulge 改轮廓；标准对称截面保形面积误差小于 2% |
| GPU 回归 | 655 条断言通过，41 个过渡采样、参数实际像素变化、黑背景、双眼实体、无内部空洞、安全区 |
| 极端参数 | 47 组允许的边界值通过；9 组折叠/过薄等危险组合被验证器拒绝 |
| GPU 单帧 | 960×540，同一 Renderer 含 rig 与 GPU 完成等待：平均 0.374 ms，P95 0.556 ms |
| 实际连续播放 | 1460×920 完整工作台，12 秒独立测量：平均 58.69 FPS，P95 18.29 ms；最慢单帧 97.08 ms |
| 操作回归窗口 | 15 秒、749 个计入统计的帧，平均 53.45 FPS、P95 17.07 ms；含多次截图、保存、确认弹窗与缩放 |
| Inspect | V→V、V→Esc、文字输入捕获期间 V/ESC 均通过；退出不换 Renderer、不丢参数 |
| 关闭保护 | 未保存修改触发弹窗；取消后继续工作通过 |

帧率目标为 60。当前连续播放接近 60，但本机测试出现偶发长帧，**不能宣称全程锁定 60 FPS**。操作回归与连续播放分别报告；不将 GPU 离屏速度冒充窗口 FPS。

## 窗口操作测试方法

实际创建 pyglet / OpenGL 窗口；通过 ImGui 鼠标事件点击滑杆、播放、时间轴、确认与取消按钮，通过窗口键盘回调检查快捷键。未使用物理鼠标键盘自动化；Pose 库的命名/保存等数据操作同时由逻辑测试直接验证。

自动播放开启后，连续记录 4 秒多的 blend 和 phase；期间不拖动时间轴，观测到 A→B、HOLD B、B→A、HOLD A，混合值覆盖 0 和 1。独立 GPU 测试也验证自动播放帧的像素变化。

全部恢复弹窗在确认前没有改参数；确认后恢复并可 Undo。测试用独立 smoke_library.json，不向实际用户库写入测试 Pose。实际库仍只包含 NORMAL 与 HAPPY。

## 证据文件

- [GPU 断言与计时](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/gpu_report.json)
- [窗口操作与自动播放采样](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/window_smoke.json)
- [连续播放帧率](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/window_benchmark.json)
- [NORMAL 工作台](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/editor_normal_workbench.png)
- [HAPPY 工作台](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/editor_happy_workbench.png)
- [Volume 调参区](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/editor_volume_workbench.png)
- [缩放后的最终工作台](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/editor_final_workbench.png)
- [Inspect 平面与安全区](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/editor_inspect_workbench.png)
- [NORMAL 实际渲染](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/normal.png)
- [HAPPY 实际渲染](C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype/test_output/pose_editor/happy.png)

已检查截图的文字、主要按钮、滚动区域、预览与中性体积表现。参数面板较长，需要滚动查看下半部分。图像结果仍需用户肉眼决定是否符合 FULU 审美。

## 当前限制

- 高度场 2.5D，不是真实 3D 网格，也不是物理体积守恒。
- HAPPY 整体上拱已实现，厚度/收端/下缘弧度尚可继续精调。
- 曲面法线与滚暗在极端参数下可能显得厚重；默认中性材质是造型检查用途。
- 自动测试允许抗锯齿边缘一像素阈值抖动，不将其误判为主体内部空洞。
- 未做 Soft Azure 最终色相、最终电子光体发光材质、AMOLED 实机色彩/gamma 校准。
- 未开发其他 BASE、RESPONSE、PERFORMANCE、声音、灯光或主项目集成。
- 当前不存在“已通过用户肉眼验收”的结论。

## 复现

~~~powershell
cd "C:/Users/WYH/.codex/.chatgpt-projects/g-p-6aa2ad94e2b48191a6369e6cfd936bbc/FULU_Visual_GPU_Prototype"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_gpu.py
.\.venv\Scripts\python.exe simulator.py --window pyglet --smoke-seconds 15
.\.venv\Scripts\python.exe simulator.py --window pyglet --benchmark-seconds 12
~~~

