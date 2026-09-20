# FULU Visual Tuner

独立程序化电子眼工作台。Python 3.12 + ModernGL + moderngl-window + GLSL，两个独立 Eye 实体逐帧渲染。保持 NORMAL/HAPPY、Pose、手动形变、体积/光感、Motion、Reference、Runtime、Inspect、Export 和两个实验性辅助元素。没有 PNG/GIF/视频眼睛动画，不接 FULU 主系统。

## 直接打开

当前唯一工作目录：**D:\FULU_Visual_Tuner**

在资源管理器输入此路径，双击 **run.cmd**。PowerShell：

~~~powershell
& "D:\FULU_Visual_Tuner\run.cmd"
~~~

如果之前已经开着工作台，关闭旧窗口后重新打开，才能载入本轮代码。

## 当前编辑入口

默认打开 **形状 Shape**。没有真实 AI 连接时，AI 页只显示未连接状态；不显示文字、麦克风、图片或生成按钮，也不使用规则 fallback 代替 AI。手动编辑始终可用。

Shape 顶部提供闭合 Contour：

1. 点击“转换当前轮廓 Edit contour”，或用圆 / 矩形 / 三角作为起点。
2. 选择双眼 / 左眼 / 右眼，在轮廓框中拖动顶点；加点插入当前点与下一点的中点，删点移除当前点。
3. 继续调整下方尺寸、Bend、Curve、Bulge、Roundness 等轴。Roundness 在 Contour 上控制顶点圆润过渡。
4. 保存此 Pose；下次启动仍可继续编辑这些点。

底层保存的是隐式闭合的 3–64 个归一化顶点，不保存“圆 / 矩形 / 三角”固定类型。每个左右眼可保存自己的轮廓。拒绝非有限坐标、自交、零面积和重复相邻点；需要消失时用 Scale / Opacity=0。圆角采用有限采样，极端尖角和复杂凹形仍需肉眼检查。

旧 NORMAL/HAPPY 保留原解析轮廓渲染，未自动转换或重画。主动转成 Contour 时，从内置 Pose 建立一个可编辑结果，保护原记录。转换曲线为顶点会有有限采样误差；可 Undo。轮廓继续经过同一个 Eye Rig、GLSL、体积和实时过渡管线。

## AI：统一修改当前眼睛

在 **设置 Settings → AI** 配置 OpenAI / DeepSeek / Local AI / Custom，保存后测试连接。API Key 不需要发到聊天。只有真实服务请求返回有效 Eye Intent 后，AI 区才出现：

**文本 + 麦克风 + 导入图片 + 生成 / 应用**。

文本、转写文字和可选图片都使用当前 Eye State；再次 Apply 继续修改当前结果。手调以后仍可继续 AI 修改。请求期间又手调或切了上下文，过时结果会被丢弃。AI 不生成最终图片、不直接写像素，也不控制 Accent。

流程：文字 / 语音文字 / 可选图片 → AI Interpreter → Structured Eye Intent（参数操作、闭合轮廓）→ 本地 Solver / Validator → 当前眼睛 → GPU。

图片入口支持 PNG/JPG/JPEG/WEBP/BMP；点击 Apply 才发送一个最大 1024 边长的工作副本到所选模型，原图不变。模型需支持视觉输入，并返回可编辑轮廓；未返回有效轮廓则拒绝应用。不支持图像的模型会明确失败，不能保证所有 Provider 都具有视觉能力。Reference Overlay 是独立的人工对照，不自动发送到 AI。

OpenAI 默认 `gpt-4.1-mini`，API 基础地址 `https://api.openai.com/v1`。Custom 使用 OpenAI-compatible Chat Completions；远程要求 HTTPS，本机允许 HTTP。OpenAI 使用 JSON Schema，兼容服务使用 JSON 模式；所有结果都会再校验。

设置保存在 `data/ai_settings.local.json`；Key 使用 Windows DPAPI 加密，并被 Git/Export 排除。支持 OPENAI_API_KEY / DEEPSEEK_API_KEY 环境变量。ChatGPT 订阅不能代替 API Key。保存后下一次启动后台尝试连接，失败不影响工作台。

**当前真实 AI 和图片识别效果未验证：用户暂时没有 API Key。本地模拟 HTTP 协议测试不等于真实模型验证。**

## 语音 STT

已移除 Windows System.Speech 及固定短语识别。`speech.py` 提供 STTRegistry / STTProvider 接口。Settings 同一页选择 Disabled、OpenAI 或 Custom compatible，设置模型、Key 和必要的 Endpoint。默认 Disabled，显示“STT 待接”，没有假识别结果。

OpenAI STT 留空独立 Key 时复用本机 OpenAI Key；默认模型 `gpt-4o-mini-transcribe`。Mic 使用默认麦克风录音，最长 10 秒；再点结束录音会开始转写。转写结果只填入同一个文本框，不自动 Apply。录音短暂保存在项目 `.cache/tmp`，读取后删除，再送给所配置 STT 服务。退出时取消录音。

STT 的 multipart 请求、返回文本进入同一框已通过本地模拟服务验证；**真实 API 转写、真人麦克风识别准确率尚未验证**。

接口依据：[OpenAI 图像输入](https://developers.openai.com/api/docs/guides/images-vision)、[语音转文字](https://developers.openai.com/api/docs/guides/speech-to-text)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)。

## 参数与实时形变

原 14 个 Shape 轴全部保留，范围扩大：

| 参数 | 范围 |
|---|---:|
| Width / Height | 0–3 |
| Gap | 0–3 |
| Roundness | 0–1（完整归一化圆角范围） |
| Whole Bend | -3–3 rad |
| Thickness | 0–6 |
| Center Bulge | -0.95–5 |
| End Taper | -3–0.99 |
| Volume Preserve | 0–1 |
| Top / Bottom Curve | -2–2 |
| Tilt | -180–180° |
| Squash | 0–1 |
| Stretch | -1–8 |

SHAPE 下“左右眼与位置 Eyes / Transform”：

- 整体 Position X/Y：-3–3；Scale：0–8；Rotation：-720–720°；Opacity：0–1。
- 左右各自 Width Scale / Opening：0–8；Gaze X/Y：-3–3；Rotation：-720–720°；Opacity：0–1；Bend offset：-3–3。
- 两只眼保留各自独立实时实体，可不对称、单眼关闭/消失，仍参与插值与 retarget。
- Width/Height/Thickness/Scale 为 0、Squash 为 1、Stretch 为 -1 或 Opacity 为 0 时主体可完全消失。内部 EPSILON 防除零；不可见实体直接跳过着色。
- 大眼睛/大偏移允许被画布裁切。非法有限值、轮廓交叉和折叠仍被拒绝；不通过缩小滑杆范围解决数值问题。
- Roundness、Opacity、Volume Preserve 保留有物理意义的 0–1 范围。
- Whole Bend 同时带动上下轮廓；不是在固定方块内画线。

Shape=形状；Volume=立体程度；Light / 光感=怎么亮。Volume 放 Depth、Surface Roundness、Bulge Influence；Light 放 Center Fill、Side/Bottom/Edge Falloff、Edge Softness。为兼容保存格式，两者仍存于原 volume 数据组；现有 Volume Reset 恢复这整个组。

Volume Depth 0–5、Surface Roundness 2–12、Bulge Influence 0–4、Falloff 0–1.5、Edge Softness 0–4。Motion 响应 0.1–60，往返间隔 0.05–30 秒。Depth=0 为均匀亮度的纯 2D（边缘仍抗锯齿），增大后渐变到 2.5D。原已保存参数、Depth=.85 时 NORMAL/HAPPY 像素保持不变。

## 保存、Reset 与快捷键

- Pose 参数、Accent、Reference、Volume/Light、Motion 等仍在 **data/pose_library.json**。
- “保存此 Pose”只保存当前记录；“保存工作台 / S”保存全部可调工作台数据。AI 密钥与连接偏好单独保存在本机私有设置文件。
- Shape Reset 只恢复当前 Pose；Volume Reset 恢复原体积/光感组；Motion Reset 只恢复播放；Reset Accent 不影响主眼。Restore All 二次确认，保留自定义记录，可 Undo，不清除 AI 密钥。
- N/H：NORMAL/HAPPY；SPACE/P：A/B 播放或暂停/继续；右箭头：小步。
- F：平面轮廓；G：安全区；V：Inspect 开关，Inspect 内 ESC 优先退出。
- Z/Y：Undo/Redo；S：保存；R：确认后重载；F12：截图。输入文本时普通快捷键让位于输入框，V 仍为全局切换。

## Reference、Runtime 与 Accent

Reference 保留导入、Overlay、透明度、Fit/Fill/1:1、位置/缩放及左右对照。原始字节复制到 assets/references，不改原图。显示纹理最大 4096，1:1 指显示纹理像素。Reference 用于人工对照；只有在 AI 区主动导入的图片才随 Apply 发给视觉模型。

Runtime 只有看左 / 回中 / 看右、Wake / Shake、实际 Pose Library 下拉框和播放过渡。看左/右使用约 .22 秒移动、.75 秒停留、.55 秒平滑回中；回中可随时打断。Shake 是当前眼睛的短暂程序化横向摆动，不创建或强制切换情绪 Pose；Wake 返回 NORMAL。无 Touch/Pet/Person Detected 或固定 Semantic 按钮。

Pose 过渡可随时 retarget：从当前插值状态立即转向新目标，不等旧动画播完。保证形状连续，未承诺速度 C1 连续。Motion 页仍只负责 A/B 过渡响应、间隔和小步时间；Gaze/Shake 的内部节奏在 Runtime 中，不混入 Motion。

Accent 仅保留 QUESTION / EXCLAMATION，明确标记 **Experimental / Unverified**。独立 SDF pass 合成，保留拖动、完整尺寸和旋转安全区 clamp、ENTER/HOLD/EXIT、暂停/继续、Reset。Scale 0–10，实际大尺寸会按安全区适配；0 完全消失，Rotation ±720°，Opacity 0–1。AI 无权控制 Accent。

extensions.py 保留 EyeExtension、AccentPlugin 和导入 manifest 校验接口。Brow/Eyelash/Pupil/Iris/Highlight/Style/Realism 全部默认 disabled，未实现视觉内容，不自动加载插件、不出现在普通 UI。Accent Registry 只有现有两个符号；没有新元素或 Element Lab。

## 环境与测试

Windows、Python 3.12、OpenGL 3.3+；Microsoft YaHei 系统字体。现有 .venv 在 D 盘，引用原有 C 盘基础 Python。不要删除基础解释器。本轮不新增 Python 包、不安装模型。窗口依赖保持 requirements-lock.txt。

~~~powershell
Set-Location "D:\FULU_Visual_Tuner"
.\.venv\Scripts\python.exe verify_upgrade.py
.\.venv\Scripts\python.exe verify_gpu.py
.\run.cmd --smoke-seconds 15
.\run.cmd --accent-smoke --smoke-seconds 11
.\run.cmd --upgrade-smoke --smoke-seconds 12
~~~

窗口测试操作真实 ImGui/GLSL，但采用程序注入输入，不代替用户肉眼验收。upgrade-smoke 使用本次窗口截图及模拟音频/HTTP 返回，不要求旧的 Windows 语音测试文件。自动测试中的 HTTP 服务是协议模拟，不是实际 AI。详见 **CLOSEOUT_REPORT.md**。

## 代码结构与开源准备

- simulator.py：保留原窗口、帧循环、编辑与 Inspect。
- config.py / geometry.py / rig.py / renderer.py：原参数/形变/独立 Eye/渲染，增量加入闭合 Contour，保留零尺寸和独立控制。
- ai_ui.py：统一输入与后台任务；ai_settings.py：私有偏好、DPAPI。
- ai_provider.py：可替换解释器；eye_intent.py：白名单结构与本地 Solver。
- speech.py：录音适配器与可替换 STT，仅输出文字；speech_capture.ps1 为已停用入口。
- tuner_extensions.py / reference.py / runtime.py：现有面板、参考图和实时语义层。
- extensions.py：默认禁用的眼部扩展接口、Accent Registry/导入接口。
- visual_elements.py / element_renderer.py / shaders/：现有矢量符号与实时眼睛。
- tests/：既有及本轮回归。

Export 白名单源码排除个人库、私有 AI 设置、密钥、图片、基准、测试录音、缓存和备份；不会上传 GitHub。CONTRIBUTING.md 说明贡献边界，LICENSE_PENDING.md 仍是占位。主系统、其他 BASE/RESPONSE/PERFORMANCE、声音/灯光/身体运动、粒子、图片生成和最终颜色精修均不在本轮范围。
