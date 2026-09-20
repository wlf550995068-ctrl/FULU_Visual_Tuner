# FULU Visual Tuner 增量升级交付

交付日期：2026-09-19。升级在原有工作台上完成，原窗口、GPU/GLSL Renderer、Eye Rig、Shader、Motion、Accent、保存体系继续使用。

## 1. 实际位置与启动

新版目录：**D:\FULU_Visual_Tuner**

最简单：在资源管理器地址栏输入上面的目录，双击 **run.cmd**。也可以在 PowerShell 粘贴：

```powershell
& "D:\FULU_Visual_Tuner\run.cmd"
```

完整 Python 启动命令：

```powershell
Set-Location "D:\FULU_Visual_Tuner"
& "D:\FULU_Visual_Tuner\.venv\Scripts\python.exe" "D:\FULU_Visual_Tuner\simulator.py" --window pyglet
```

旧版实际目录：

```text
C:\Users\WYH\.codex\.chatgpt-projects\g-p-6aa2ad94e2b48191a6369e6cfd936bbc\FULU_Visual_GPU_Prototype
```

升级前备份：**D:\FULU_Visual_Tuner\backups\before_upgrade_20260919.zip**。这是备份，用户运行新版无需解压它。旧 C 盘项目逐文件与该备份一致，本轮没有改动或删除。

新版连同 .venv、备份和验证结果约 **229 MB**。项目依赖与可控缓存放在 D 盘；仍引用现有 C:\Program Files\Python312 基础 Python 3.12.10。不能删除该基础解释器。没有安装 AI 模型，没有新增外部编辑软件。

## 2. 已交付的软件能力

| 能力 | 实际行为 |
|---|---|
| Auto Derive | Base + Semantic + 文本规则 + 可选双主体测量 → 一个自定义 Pose；重复同语义更新一条记录 |
| Refine | 修改同一结果、同一 id，不随机生成下一批候选；仍可手动调所有轴 |
| Style Guard | 衍生形状限制尖锐/扁瘪倾向，保留既有材质；没有嘴/瞳孔/虹膜/眉毛生成通道 |
| Family | NEUTRAL/POSITIVE/LOW/TENSION 只存 metadata，不参与可见过渡 |
| 手动 Shape | 原 14 轴全部保留并扩大有效范围；归一化比例仍遵守 0–1 |
| Reference | 浏览/路径导入、显示隐藏、Overlay 透明度、Fit/Fill/1:1、位置、缩放、左右对照 |
| Runtime | 语义事件测试入口、当前状态/目标/进度、随时 retarget、Pause/Resume、Return |
| Interrupt | NORMAL→HAPPY 进行中立即从当前插值状态转向 SAD，不等上一段结束 |
| Idle | 默认关闭；可开启轻微漂移，显式 Look Left/Right 注视；无随机情绪 |
| 既有能力 | Pose CRUD/保存读取、A/B、Scrub/Step、分组 Reset、Undo/Redo、F/G/V/FPS、QUESTION/EXCLAMATION 全部保留 |
| GitHub-ready | README、依赖、忽略规则、贡献指南、许可证待决定说明、白名单源码导出与独立测试 |

实际库仍只显示 NORMAL / HAPPY；没有预建 SAD、CURIOUS、ANNOYED 或其他 BASE。测试生成的 SAD 放在 test_output 的隔离库中。

源库中 happy 曾被手动命名为 positive root：只恢复显示名称 HAPPY，形状完整保留。旧 low root 自定义记录原样保留形状并设置 archived，现以 IMPORTED_119b4f41 存在个人 JSON 中，不在选择器和 Runtime 中出现；原名称保留在 legacy_name，备份也保留原记录。没有删除成果，没有把 Root 当成中间表情。

## 3. 推荐第一次操作

1. 启动后按 N / H 查看已保存的 NORMAL / HAPPY；按 V 进入/退出 Inspect。
2. 右侧“编辑分区”选 AUTO DERIVE，Base NORMAL、Target SAD。
3. 输入“上眼皮压低，整体变矮，下缘保持圆润，不要收窄，不要水滴形。”，点 Auto Derive。
4. 输入 Refine “上眼缘再压一点，宽度保持。”，点 Refine。
5. 到 SHAPE 精修，再点保存结果；按 S 保存所有工作台设置。
6. RUNTIME 点 Semantic HAPPY，过渡途中点 Semantic SAD，观察立即转向。
7. REFERENCE 导入图片，选择 Overlay 或左右对照；按 S 后重启恢复。

没有目标 Pose 的事件会提示先衍生/加载，不会默默新增表情。触发映射只供开发测试，不定义产品受控组合规则。

## 4. 参数与保存位置

参数范围、键位和分组 Reset 的完整说明在 D:\FULU_Visual_Tuner\README.md。

- 个人库：**D:\FULU_Visual_Tuner\data\pose_library.json**。Pose 各自保存 Shape；同一 JSON 扩展 Reference、Runtime 配置。Accent/Volume/Motion 继续保留，没有第二套配置系统。
- “保存此 Pose/保存结果”只保存当前 Pose；“保存工作台 / S”保存全局设置与所有记录。
- 参考原始文件的副本：**D:\FULU_Visual_Tuner\assets\references\**，不修改用户原图。
- 手动 Shape 安全校验：有限数字、正尺寸、截面厚度、折叠和安全区。非法组合拒绝应用，上一个合法状态继续运行。
- Restore Shape 只作用当前 Pose；Volume/Material 共用原体积数据；Motion 只恢复播放设置；Reset Accent 不影响主眼。Restore All 保留自定义记录、需二次确认，且可 Undo。
- QUESTION / EXCLAMATION 继续使用独立 SDF 合成通道。可拖动或调 X/Y、Scale、Rotation、Opacity；G 显示安全边界。clamp 计算符号缩放和旋转后的完整边界，动画缩放不超过编辑目标尺寸。

## 5. 真实验证结果

测试设备：Windows、Python 3.12.10、NVIDIA GeForce RTX 4060 Ti、OpenGL 3.3 / NVIDIA 610.88。

| 验证 | 结果 |
|---|---|
| 本机单元/集成/GPU 回归 | **59 项通过，0 失败，0 跳过** |
| 迁移前 NORMAL/HAPPY | 两张 960×540 GPU 画面逐像素一致；Shape/Volume 完全一致 |
| 既有渲染与节奏 | eye.frag、eye.vert、renderer.py、geometry.py、rig.py、motion.py 文件哈希不变；360 个 A/B 时间采样完全相等 |
| 历史 GPU 能力脚本 | **670 项检查通过**；50 个端点组合接受，6 个危险组合拒绝 |
| 原 Pose Editor 实际窗口 | 保存/加载、A/B 自动往返、暂停/逐步/拖轴、Undo/Redo、Reset 确认、Inspect/ESC/resize 通过 |
| Accent 实际窗口 | QUESTION/EXCLAMATION、拖动、安全区、ENTER/HOLD/EXIT、暂停/重置、保存恢复通过 |
| 升级链路实际窗口 | 单结果衍生→同结果 Refine→保存→参考导入/Overlay/左右对照→Runtime→打断→SAD→Return→Inspect 通过 |
| 中途打断 | 单元测试精确在 46% 检查无形状跳变；实际窗口在相应进度区间 retarget 并到达 SAD |
| 参考图重新启动 | 全新 Python 进程从已保存配置恢复路径、显示设置和 GPU 纹理，通过 |
| 极端参数 | 接近点状真实 GPU 绘制；其他端点合法则渲染、非法则拒绝；NaN/Infinity/负尺寸拒绝 |
| run.cmd | 原编辑器、Accent、升级窗口三个模式均通过这个入口启动并正常关闭 |
| 干净源码导出 | **57 项通过，2 项明确跳过**（不公开私人基准），0 失败；GPU 脚本也通过 |
| 依赖 | pip check 无缺失/冲突 |

窗口平均 FPS：原编辑器 **58.97**，升级链路 **58.51**，Accent **56.01**。对应 P95 帧耗时约 17.06 / 17.08 / 19.58 ms。接近 60 FPS，**未达到保证稳定锁定 60 FPS 的验收标准**。GPU 单独渲染平均约 0.33 ms，不能用它冒充整个窗口 FPS。

测试通过不等于用户已完成艺术验收。窗口测试采用程序注入 ImGui 操作和窗口按键回调；原生图片选择器只验证 Tk 可用，完整导入链路用文件路径操作测试，未声称人工点击验证原生对话框。

发现并修复的问题：
- 旧 GPU 脚本依赖会变化的用户 HAPPY 参数，固定的早期弯曲阈值与现库不相容；改为固定历史样例。确认画面另以迁移前逐像素基准保护，未调整眼睛来迁就测试。
- 参考恢复曾向只接受字符串的加载方法传入 Path；已支持 Path，并加入新进程恢复验证。
- 干净源码测试缺少父输出目录导致第一次导出验证失败；补齐目录创建后复测通过。

最终没有尚未解决的自动测试失败；稳定 60 FPS、跨设备像素一致、第二台电脑首次联网安装和用户肉眼验收仍未证明。

测试证据：
- D:\FULU_Visual_Tuner\test_output\upgrade\tests.json
- D:\FULU_Visual_Tuner\test_output\upgrade\window_smoke.json
- D:\FULU_Visual_Tuner\test_output\upgrade\export_check.json
- D:\FULU_Visual_Tuner\test_output\pose_editor\window_smoke.json
- D:\FULU_Visual_Tuner\test_output\accent\window_smoke.json
- D:\FULU_Visual_Tuner\baseline\

## 6. 当前限制、未实现内容

- Auto Derive 是有限短语规则和参数拟合，不理解任意自然语言；“最佳拟合”不是训练模型或全局视觉优化。未知描述明确提示。参考图只做双主体宽高间隔粗测量，不重建曲面/材质。
- Reference 大图显示纹理最大 4096；1:1 对应工作纹理像素。复杂背景仅作 Overlay。
- 可打断保证当前形状连续；**未保证打断前后速度连续（C1）**。
- Idle 已有轻微漂移/注视；Blink、Energy 尚未做。AI 扩展点只是 DerivationEngine 调用边界，没有实际 AI 接入。
- MATERIAL 面板复用既有 Volume，未重新设计眼睛，未做最终柔蓝校色、发光精修或新材质模型。
- 没有其他 Visual Elements、粒子、PERFORMANCE、完整 RESPONSE、Sound、Light、Body Motion 或主项目集成。
- 只整理独立工具，未发布 GitHub，没有选定最终许可证。

## 7. 旧版能否删除、开源还缺什么

迁移和回归已通过，但建议先亲自打开新版确认 NORMAL/HAPPY 与个人库符合预期，再考虑删除**旧的 FULU_Visual_GPU_Prototype 项目目录**以释放空间。不要删除 ChatGPT sources 资料库，也不要删除 C:\Program Files\Python312。当前没有替用户删除任何旧文件，升级前备份可继续保留。

上传 GitHub 前还需要：由所有者选择许可证；确认 FULU 名称/视觉资产/字体和参考图授权；选择仓库与公开内容；在干净 Windows 环境验证首次安装。EXPORT 的白名单源码包已通过隔离测试，不包含主系统或私人库，也不会自动上传。

## 8. 文件变更清单

下面路径全部属于 D:\FULU_Visual_Tuner。旧 C 盘同名文件未改。

### 修改文件

- [.gitignore](D:/FULU_Visual_Tuner/.gitignore)
- [README.md](D:/FULU_Visual_Tuner/README.md)
- [requirements.txt](D:/FULU_Visual_Tuner/requirements.txt)
- [run.cmd](D:/FULU_Visual_Tuner/run.cmd)
- [simulator.py](D:/FULU_Visual_Tuner/simulator.py)
- [verify_gpu.py](D:/FULU_Visual_Tuner/verify_gpu.py)
- [data/pose_library.json](D:/FULU_Visual_Tuner/data/pose_library.json)
- [fulu_visual/config.py](D:/FULU_Visual_Tuner/fulu_visual/config.py)
- [tests/test_visual_elements.py](D:/FULU_Visual_Tuner/tests/test_visual_elements.py)

### 新增文件

- [CONTRIBUTING.md](D:/FULU_Visual_Tuner/CONTRIBUTING.md)
- [LICENSE_PENDING.md](D:/FULU_Visual_Tuner/LICENSE_PENDING.md)
- [verify_upgrade.py](D:/FULU_Visual_Tuner/verify_upgrade.py)
- [data/pose_library.example.json](D:/FULU_Visual_Tuner/data/pose_library.example.json)
- [fulu_visual/derive.py](D:/FULU_Visual_Tuner/fulu_visual/derive.py)
- [fulu_visual/export_tools.py](D:/FULU_Visual_Tuner/fulu_visual/export_tools.py)
- [fulu_visual/reference.py](D:/FULU_Visual_Tuner/fulu_visual/reference.py)
- [fulu_visual/runtime.py](D:/FULU_Visual_Tuner/fulu_visual/runtime.py)
- [fulu_visual/tuner_extensions.py](D:/FULU_Visual_Tuner/fulu_visual/tuner_extensions.py)
- [tests/test_upgrade.py](D:/FULU_Visual_Tuner/tests/test_upgrade.py)
- [tests/upgrade_smoke.py](D:/FULU_Visual_Tuner/tests/upgrade_smoke.py)
- [UPGRADE_REPORT.md](D:/FULU_Visual_Tuner/UPGRADE_REPORT.md)（本交付报告）

另新增 baseline、backups、测试证据与 D 盘 .venv/.cache；这些不进入源码导出。requirements-lock.txt、所有眼睛及符号 Shader、原 Eye Rig/Renderer/Motion 保持不变。
