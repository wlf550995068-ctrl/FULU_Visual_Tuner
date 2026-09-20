# Contributing

本仓库只包含 FULU Visual Tuner / 独立 Visual Runtime 开发工具。请先阅读 README，使用 Python 3.12、requirements-lock.txt 与 OpenGL 3.3+。

## 开发边界

- 增量修改；保留确认过的 NORMAL/HAPPY 几何、材质、亮度与 A/B 节奏。
- 不引入主系统 Decision、Relationship、Memory、Reminder、Persistence、RobotSession、Light 或商业产品逻辑。
- Family 仅是 metadata，不生成可见 ROOT，不改变产品 Visual V2 分类。
- Auto Derive 每次一个结果，Refine 修改当前结果；保持所有手动参数轴。
- Visual Elements 目前只有 QUESTION/EXCLAMATION，不扩展粒子、彩蛋或完整 RESPONSE。
- 不把私有参考图片、个人 Pose 库、截图、基准备份、密钥或虚拟环境提交到 Git。

## 验证与提交

1. 运行 python verify_upgrade.py 与 python verify_gpu.py；真实 OpenGL 上下文是 GPU 测试的前提。
2. UI 变化运行对应的 run.cmd 窗口 smoke 参数，见 README。公开源码缺少个人迁移基准时两个基准测试会 skip；不得把 skip 写成通过。
3. 调整几何或 Shader 必须说明视觉影响并提供经所有者批准的基准，不自动覆盖旧基准使测试通过。
4. PR 说明具体问题、最终行为、验证结果与已知限制。不要打包主系统。
5. 不新增大型框架/模型；依赖变更同步 requirements.txt 和 requirements-lock.txt。

许可证尚未决定。正式接受外部贡献和发布前，项目所有者需要明确代码/视觉资产授权及贡献条款。本文件不是版权转让或许可协议。

## AI 与语音贡献约束

仅通过 Eye Intent 白名单调用本地 Solver；禁止直接执行模型代码或操作 Accent。不要提交 data/*.local.json、录音或真实密钥。API 协议模拟测试不能称为真实 AI 验证。Windows 听写始终先填文字，由用户 Apply。
