# Day 12：文档完善与一键启动

## 📅 目标
本阶段将系统从"开发模式"转变为"准生产模式"，确保系统能够方便地启动、运行，并具备完善的文档支持。

## 📦 1. 一键启动 (One-Key Start)

目前的启动方式依然较为分散 (Pi 端手动 python main.py, MBP 端 manual start)。我们将创建一个统一的启动脚本。

### 1.1 Pi 端服务化
- 创建 `start_agent.sh`：自动激活 venv 并运行 `main.py`
- (可选) 创建 Systemd 服务文件 `snap2know.service`，实现开机自启。

### 1.2 MBP 后端启动
- 现有的 `start_server.sh` 已经不错，但可以增加后台运行模式。

## 📝 2. 文档体系 (Documentation)

### 2.1 README.md 重构
当前的 README 可能还停留在项目初期。需要更新为最终交付版本：
- **项目简介**：Wake-to-Photo 核心特性介绍
- **硬件清单**：Raspberry Pi 5 + IMX500 + Whisplay HAT
- **快速开始**：如何部署 Backend 和 Agent
- **操作指南**：Hello World, 交互流程 (唤醒 -> 拍照 -> 问答)

### 2.2 故障排查 (Troubleshooting)
基于这两天的调试经验，整理 FAQ：
- 摄像头模糊？(定焦问题)
- 唤醒不灵敏？(麦克风增益)
- 报错 500？(Backend 连接问题)

## ✅ 验收标准
1. **启动测试**：在 Pi 上执行 `./start_agent.sh` 即可进入工作状态。
2. **文档完整**：新人阅读 README.md 能够理解系统架构并完成部署。

---

## 🛠️ 下一步行动 (Action Plan)

1. **Pi 端脚本**：编写 `device_agent/start_agent.sh` 并同步。
2. **README 更新**：重写根目录 `README.md`。
3. **验证**：模拟用户操作，从零启动系统。