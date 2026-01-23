# Snap2Know 项目阶段性总结

> 生成时间：2026-01-23  
> 项目周期：Day 0 - Day 12 (共 13 个开发日)

---

## 📊 项目进度概览

| 阶段 | 天数 | 状态 | 关键交付 |
|------|------|------|----------|
| **硬件准备** | Day 0 | ✅ 完成 | Pi OS、Whisplay 驱动、IMX500 驱动 |
| **后端基础** | Day 1-4 | ✅ 完成 | 会话管理、STT、TTS、OCR、WS 流式问答 |
| **设备端开发** | Day 5-8 | ✅ 完成 | 硬件封装、状态机、LCD 渲染、MBP 通信 |
| **集成测试** | Day 9-10 | ✅ 完成 | 全链路测试、稳定性优化、边界情况处理 |
| **Demo 打磨** | Day 11 | ✅ 完成 | Wake-to-Photo、Prompt 固化、TTS 优化 |
| **工程收尾** | Day 12 | ✅ 完成 | 一键启动、文档完善、动态声卡检测 |
| **最终验收** | Day 13 | 🔜 待进行 | 完整演示、Bug 修复 |

**总体完成度：约 92%**

---

## ✅ 已完成的核心功能

### 后端 (MBP)
- [x] FastAPI 服务框架
- [x] 会话管理 (Session API)
- [x] STT：Groq Whisper API + 本地 Faster-Whisper 回退
- [x] TTS：edge-tts + Markdown 清洗
- [x] OCR：Claude Sonnet → GPT-4o 双路回退
- [x] RAG：Qdrant 向量检索 + Claude 问答
- [x] WebSocket 流式问答

### 设备端 (Pi)
- [x] 硬件封装（LED、LCD、Camera、Audio、Button）
- [x] 状态机（7 状态 + Busy 子阶段）
- [x] LCD 渲染（PIL/Pillow 直驱 ST7789P3）
- [x] 唤醒词检测（Vosk 离线识别）
- [x] VAD 录音（基于 RMS 静音检测）
- [x] Wake-to-Photo（唤醒即拍）
- [x] Smart Session（60s 上下文保持）
- [x] 动态声卡检测（WM8960 / USB 麦克风）

### 工程化
- [x] 一键启动脚本 (`start_agent.sh`)
- [x] Systemd 服务配置 (`snap2know.service`)
- [x] 摄像头调试工具 (`camera_stream.py`)
- [x] 项目文档 (README.md 重构)

---

## ⚠️ 已知问题与遗留项

### 1. OCR 服务不稳定
- **现象**：Claude Sonnet Vision 偶尔返回 404 (OpenRouter 限制)
- **影响**：需回退到 GPT-4o，响应变慢
- **建议**：考虑直接使用 Anthropic 官方 API 或本地 OCR

### 2. 摄像头对焦问题
- **现象**：IMX500 定焦镜头，部分距离下图像模糊
- **影响**：OCR 识别准确率下降
- **建议**：固定设备距离 (30-50cm)，或更换可调焦镜头

### 3. 麦克风回声 (AEC)
- **现象**：TTS 播放时麦克风可能拾取声音
- **影响**：可能误触发唤醒或干扰 STT
- **建议**：后续集成 WebRTC AEC 或硬件 AEC 方案

### 4. TTS 偶发 500 错误
- **现象**：edge-tts 或后端 TTS 接口偶尔返回 500
- **影响**：语音播报中断
- **建议**：增加重试机制或本地 TTS 降级

---

## 🚀 优化建议 (Roadmap)

### 短期 (Day 13-14)
- [ ] 完整演示视频录制
- [ ] 修复剩余 Bug
- [ ] 优化首次响应延迟

### 中期 (Day 15+)
- [ ] **Chroma 1.0 集成**：探索端到端语音模型，替代 STT+LLM+TTS 级联
- [ ] **声音克隆**：使用 Few-shot 克隆用户偏好的声音
- [ ] **多语言支持**：扩展英文/粤语等语言

### 长期
- [ ] **边缘部署**：尝试将部分模型迁移到 Pi 本地
- [ ] **产品化**：外壳设计、电池供电、生产固件

---

## 📁 项目文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 详细设计 | `design.md` | 完整技术设计文档 |
| 快速开始 | `README.md` | 部署指南 + 故障排查 |
| 学习路径 | `docs/learning_path.md` | 技术栈学习资源 |
| 两周路线图 | `docs/two_week_roadmap.md` | 开发计划 |
| 摄像头调试 | `docs/camera-debug-guide.md` | 对焦调试指南 |
| Day 0-12 | `docs/Day*/` | 每日开发文档 |

---

## 📈 开发统计

- **开发周期**：13 个工作日
- **代码提交**：40+ commits
- **核心文件**：
  - 后端：~15 个 Python 文件
  - 设备端：~20 个 Python 文件
- **文档**：20+ Markdown 文件

---

## 💡 总结

Snap2Know 项目已完成 Day 0 到 Day 12 的全部开发任务，实现了从硬件验证到软件集成的完整闭环。核心的 **Wake-to-Photo** 无感交互模式已验证可行，**Smart Session** 会话管理提升了多轮对话体验。

剩余的 **Day 13：最终验收** 将聚焦于端到端演示验证和细节打磨。
