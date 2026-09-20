# FULU Visual Tuner｜本轮原地升级报告

日期：2026-09-20。唯一修改项目：**D:\FULU_Visual_Tuner**。原目录原地修改，没有创建新项目、平行版本或交付压缩包，没有安装新依赖、大模型或外部编辑器。

## 打开

资源管理器进入 **D:\FULU_Visual_Tuner**，双击 **run.cmd**。已打开的旧进程请保存自己的编辑后关闭，再重新运行。

```powershell
& "D:\FULU_Visual_Tuner\run.cmd"
```

## 当前功能

- 默认打开 Shape，手动编辑始终可用。AI 未连接时不显示文本、麦克风、图片、生成区，不以 Rule Fallback 冒充 AI。
- 真实连接后同一个 AI 区：文字 / 麦克风 / 导入图片 / Generate Apply。修改当前眼睛，可以 AI→手调→AI 继续。异步期间手调会使旧结果失效，避免覆盖。
- Shape 增量支持共享或左右独立闭合 Contour：3–64 点，拖点、加点、删点、现有参数精修、圆角、Undo/Redo、保存读取。圆/矩形/三角是种子，不是底层固定类型。
- NORMAL/HAPPY 未自动转成点集，仍通过原解析分支渲染。主动从内置 Pose 开始轮廓编辑会创建一条编辑结果，原记录保持。导出的 Contour 是参数，不是贴图。
- 图片经所选视觉模型输出顶点和参数意图，经过本地校验后进入同一 Eye Engine。不是 PNG 最终贴图，也不自动分析 Reference Overlay。原图不改。
- System.Speech 固定短语逻辑已移除，speech_capture.ps1 停用；speech.py 是可替换 STT 接口 + Windows 录音适配器。默认待接。配置后 Mic 录音，转文字进入同一输入框，不自动 Apply。
- Volume Depth=0 为纯 2D；增加后回到 2.5D。新 Contour 的曲面光感经过平滑，避免距离场中轴的明显折面。原 NORMAL/HAPPY 的 Depth=.85 像素不变。
- Material UI 改为 Light / 光感，只显示 Center Fill、Side/Bottom/Edge Falloff、Edge Softness。沿用原 volume 存储结构，没有第二套 Renderer。Volume Reset 仍按原兼容范围恢复这整个共享数据组。
- Runtime 仅看左/回中/看右、Wake/Shake、实际 Pose 下拉和播放过渡。看左/右明显移动、停留、平滑回中。Center 可立即从当前位置平滑回中。Shake 是短暂横向摆动，不依赖或创建 ANNOYED 等 Pose。
- Motion 继续只管 A/B 过渡。Gaze/Shake 节奏集中在 Runtime，不增加 Gaze 页面。
- Accent、Reference、Inspect、Export、保存、A/B 自动往返、Left/Right 独立实体与可打断过渡保留。

## 保存在哪里

- Pose、Shape、Contour、Volume/Light、Motion、Accent、Reference：**D:\FULU_Visual_Tuner\data\pose_library.json**。
- AI/STT 本机设置：**D:\FULU_Visual_Tuner\data\ai_settings.local.json**，Key 通过 DPAPI 加密，Git/Export 排除。首次点 Save 才建立设置文件。
- 录音临时文件：项目 `.cache/tmp`，读取后删除；参考图片只有主动导入 AI 区再 Apply 才发送所选模型。
- 本轮自动测试使用 test_output 内的独立测试配置，未覆盖个人库。
- 个人库 SHA256 前后均为 `ac45c18edb4f2fa4d4f83fd80bee9d29f303156461cb7de9f5eee94ed3e78c5c`。

## 实际运行与测试

Windows / Python 3.12.10 / NVIDIA GeForce RTX 4060 Ti / OpenGL 3.3。

| 验证 | 实际结果 |
|---|---|
| 自动回归 | 102 项通过，0 失败，0 跳过 |
| 原 GPU 验证 | 670 项检查通过 |
| NORMAL/HAPPY | 当前开工前基准及历史基准逐像素一致 |
| Contour | 原窗口拖点、Undo/Redo、Roundness 像素变化、保存、新进程恢复、左右独立轮廓通过 |
| AI 显示门控 | 未连接/503 后无创作控件，手动编辑继续可用 |
| 统一输入/图片 | 真实 ImGui 中文输入和 Apply，模拟 HTTP 返回单个参数/Contour，通过 |
| STT | multipart 协议和文字进入同一输入框通过模拟服务测试；不是实际识别测试 |
| Depth=0 | GPU 内部像素均匀，真实窗口截图已检查 |
| Runtime | 实际 Pose 下拉播放、46% 处 interrupt、Current State retarget、注视停留/回中通过 |
| 原工作台 | 自动往返、Pause/Step/Scrub、保存加载、Reset、Undo/Redo、F/G/V/ESC、resize 通过 |
| Accent | 原两个元素、拖动、安全区、生命周期、暂停恢复、Reset、保存通过 |
| 窗口平均 FPS | 原工作台 59.70；本轮链路 58.34；Accent 59.32 |

测试命令：

```powershell
Set-Location "D:\FULU_Visual_Tuner"
.\.venv\Scripts\python.exe verify_upgrade.py
.\.venv\Scripts\python.exe verify_gpu.py
.\run.cmd --smoke-seconds 15
.\run.cmd --upgrade-smoke --smoke-seconds 12
.\run.cmd --accent-smoke --smoke-seconds 11
```

证据：[自动测试](D:/FULU_Visual_Tuner/test_output/upgrade/tests.json)、[本轮窗口测试](D:/FULU_Visual_Tuner/test_output/upgrade/window_smoke.json)、[Depth=0 截图](D:/FULU_Visual_Tuner/test_output/upgrade/depth_zero_workbench.png)、[轮廓编辑截图](D:/FULU_Visual_Tuner/test_output/upgrade/contour_workbench_workbench.png)。窗口测试通过程序注入真实 ImGui 输入，不能替代用户视觉验收。

## 未验证、限制与未实现

- 当前自动测试没有剩余失败。第一次运行时有 6 项旧测试仍要求 fallback、Touch/Pet 等已被明确删除的行为；测试已改为验证本轮新要求，非渲染失败。
- **没有真实 API Key，因此真实 OpenAI 调用、图片眼睛识别准确率、真实 STT 转写均未验证。** 模拟 HTTP 服务只验证协议和编辑链路，不代表 AI 能力已验收。
- Windows 默认麦克风录音适配器及真人口音/噪声表现尚需在真实 STT 配置后实测。当前默认 Disabled，未伪造文字。
- 图片识别需要支持视觉输入的模型；不支持时明确报错。自动追踪不承诺与参考图像素级一致，点集仍需手动精修。
- Contour 为有限顶点和有限圆角采样，复杂凹形、尖角、点数差异很大的形变、极端参数及新的体积光感待用户肉眼验收；非法自交/折叠会拒绝，而不是修改范围蒙混。
- Contour/解析形状之间通过距离场与参数连续混合；保证当前状态重定向，不承诺速度 C1 连续。
- 保留原 NORMAL/HAPPY 并不等于新轮廓的艺术效果已经验收；**本轮没有用户肉眼确认，不写“视觉已验收”。**
- 未增加其他 BASE、辅助元素、粒子、Element Lab、RESPONSE/PERFORMANCE、主系统集成；没有图像/视频眼睛动画。

## 修改的现有文件

- [README.md](D:/FULU_Visual_Tuner/README.md)
- [fulu_visual/ai_provider.py](D:/FULU_Visual_Tuner/fulu_visual/ai_provider.py)
- [fulu_visual/ai_settings.py](D:/FULU_Visual_Tuner/fulu_visual/ai_settings.py)
- [fulu_visual/ai_ui.py](D:/FULU_Visual_Tuner/fulu_visual/ai_ui.py)
- [fulu_visual/config.py](D:/FULU_Visual_Tuner/fulu_visual/config.py)
- [fulu_visual/eye_intent.py](D:/FULU_Visual_Tuner/fulu_visual/eye_intent.py)
- [fulu_visual/geometry.py](D:/FULU_Visual_Tuner/fulu_visual/geometry.py)
- [fulu_visual/reference.py](D:/FULU_Visual_Tuner/fulu_visual/reference.py)
- [fulu_visual/renderer.py](D:/FULU_Visual_Tuner/fulu_visual/renderer.py)
- [fulu_visual/runtime.py](D:/FULU_Visual_Tuner/fulu_visual/runtime.py)
- [fulu_visual/speech.py](D:/FULU_Visual_Tuner/fulu_visual/speech.py)
- [fulu_visual/speech_capture.ps1](D:/FULU_Visual_Tuner/fulu_visual/speech_capture.ps1)
- [fulu_visual/tuner_extensions.py](D:/FULU_Visual_Tuner/fulu_visual/tuner_extensions.py)
- [shaders/eye.frag](D:/FULU_Visual_Tuner/shaders/eye.frag)
- [simulator.py](D:/FULU_Visual_Tuner/simulator.py)
- [tests/test_closeout.py](D:/FULU_Visual_Tuner/tests/test_closeout.py)
- [tests/test_upgrade.py](D:/FULU_Visual_Tuner/tests/test_upgrade.py)
- [tests/upgrade_smoke.py](D:/FULU_Visual_Tuner/tests/upgrade_smoke.py)
- [CLOSEOUT_REPORT.md](D:/FULU_Visual_Tuner/CLOSEOUT_REPORT.md)

没有新增源码模块或项目。新增的像素基准、截图与机器测试报告仅位于原项目 `test_output` 内。
