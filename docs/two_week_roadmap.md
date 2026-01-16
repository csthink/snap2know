# Snap2Know 两周学习地图 (Day 0–14)

> 每天对应：最小功能 → AI 工程知识点 → 客观验收标准

## 前置依赖

- **Pi 端**：Python 3.11+, picamera2, espeak-ng, ffmpeg, edge-tts, alsa-utils, avahi-daemon
- **MBP 端**：Docker (Qdrant), Python 3.11+, FastAPI, OpenAI/Anthropic API Keys
- **网络**：Pi 与 MBP 同一局域网

---

## Day 0（前置）：硬件与系统连通

### 做什么
- **Pi**：Whisplay 驱动、LCD 点亮、按键事件、LED、录音/播放、相机拍照
- **MBP**：Qdrant Docker 启动，FastAPI 能被 Pi 访问

### 学到什么
- 设备 I/O（SPI LCD、ALSA、摄像头）如何"产品化"
- 环境一致性与最小可用系统（MVP first）

### 验收
- [ ] `hardware_test.py`：LCD 刷新、LED、按键、arecord/aplay、picamera2 全通过
- [ ] Pi 能 `curl http://<mbp>:8000/health` 成功

---

## Day 1：会话与最小后端骨架

### 做什么
- **FastAPI**：`/health`、`/session/new`、`/session/{id}`（元数据）
- **Pi**：Device Agent 状态机骨架（idle/recording/busy/answering/done/error）

### 学到什么
- AI 应用的"会话"为什么必须先定义（可观测、可复现、可清理）
- 状态机是 AI 产品体验的核心骨架

### 验收
- [ ] Pi 新建会话成功，LCD 显示会话 ID/计数
- [ ] 任何异常都有 error 状态与可恢复路径

---

## Day 2：STT（语音 → 文本）

### 做什么
- **Pi**：长按录音（arecord），松开停止并上传音频
- **MBP**：`/stt`（Whisper）返回 `text` + `stt_ms`
- 空音频/过短音频判定与忽略（< 1s）

### 学到什么
- 语音输入的"取消/沉默/误触"是主战场
- 真实系统里：超时、错误分类、空输入处理

### 验收
- [ ] 录 3 秒语音，stt 正确率可用，`stt_ms` 记录完整
- [ ] 录 0.5 秒/无声 → 后端返回 `empty_audio=true`，系统回 idle
- [ ] LCD 显示"录音过短/未提交"提示

---

## Day 3：OCR Ingest（图片 → 文本 → 切块）

### 做什么
- **Pi**：短按拍照上传 `/upload/image`
- **MBP**：Sonnet Vision OCR（主）/GPT-4o Vision（备）回退策略
- 文本清洗、切块、chunks 数统计

### 学到什么
- 多模态 → 可检索知识：OCR 输出不是终点，切块与清洗才是
- Provider 策略：性能/成本/稳定性的工程化选择

### 验收
- [ ] 10 次拍照：大部分 `ingest_ms` 达到目标
- [ ] 超时触发 `fallback_used=true` 且仍入库
- [ ] 返回字段完整：`ocr_provider`/`fallback_used`/`ocr_ms`/`chunk_ms`/`ingest_ms`/`num_chunks`/`dedup_skipped`

---

## Day 4：Embedding + Qdrant 入库

### 做什么
- **MBP**：`/embed`、`/qdrant/upsert` 打通
- 每会话独立 collection 或 payload 过滤
- 设计删除/清库（会话级清理）

### 学到什么
- RAG 的"数据模型"：session_id、document_id、chunk_id 的必要性
- 向量库的过滤与生命周期管理

### 验收
- [ ] `/qdrant/count?session_id=xxx` 随拍照增长
- [ ] 清库后 count 归零
- [ ] 同一 session 检索只命中本 session 数据

---

## Day 5：检索 + 结构化回答（非流式）

### 做什么
- **MBP**：`/qa`：query → embedding → search → 组装 context → LLM 输出（步骤化）
- prompt 模板：引用说明书内容、给步骤、可执行

### 学到什么
- Prompt 是"产品规格"的一部分
- 检索参数与回答质量关系（chunk 大小、top_k、context 拼接）

### 验收
- [ ] 给定 5 个固定问题，回答满足"步骤清晰 + 不瞎编 + 不脱离上下文"基本要求

---

## Day 6：WS 流式问答（token streaming）

### 做什么
- **MBP**：`/ws/qa` 推 token + 阶段事件（busy_stage：stt/ingest/qa）
- **Pi**：接 token，LCD 显示阶段与进度；缓存 token 给 TTS 分段器

### 学到什么
- 流式体验来自"协议设计"，不是模型本身
- 阶段事件 + 指标是体验与可观测的桥梁

### 验收
- [ ] Pi 能显示 busy_stage 子阶段（stt → ingest → qa）及 line1/line2 指标
- [ ] token 数持续更新
- [ ] WS 断线能重连/回 error 可恢复

---

## Day 7：TTS Provider 策略（auto）与分段/背压

### 做什么
- **Pi**：TTS 分段器（`.` 保护 + flush 规则 + 背压合并）
- **Pi**：`TTS_MODE=auto`：edge-tts 默认，失败降级 espeak-ng；锁定策略
- **Pi**：播放取消语义（`stop_playback` vs `cancel_round`）

### 学到什么
- AI 产品体验很大一部分是"输出工程"（语音/流式/背压）
- 降级与锁定是企业级稳定性的核心模式

### 验收
- [ ] 10 段连续播报不出现明显怪断句
- [ ] 缩写/版本号/URL 不被 `.` 硬切
- [ ] edge-tts 故障时自动降级且不抖动（锁定生效）
- [ ] 常见短语（如"正在识别…"）第二次播报延迟明显降低（缓存命中）

---

## Day 8：WM8960 Pop/Click 缓解（v2 常驻播放流）

### 做什么
- **Pi**：v2 persistent playback（aplay 常驻 + pipe 喂 PCM）
- oneshot（v1）仅保留调试开关

### 学到什么
- 硬件约束如何反向塑造软件架构
- "体验问题"常常是系统层而非模型层

### 验收
- [ ] 日志显示 `playback_mode=persistent`，且 aplay PID 在整个会话期间不变
- [ ] 连续 20 段播报不出现"每段稳定啪一下"

---

## Day 9：单键交互细化（强反馈 + 误触兜底）

### 做什么
- 300ms/600ms 阈值提示：LED/LCD 强反馈
- 取消逻辑：沉默/过短音频自动忽略；取消问答与停止播报区分

### 学到什么
- 人机交互在 AI 设备里是"第一性问题"
- 误触与高压力场景下的交互设计

### 验收
- [ ] 10 次"犹豫松手"不应误触发拍照或 STT
- [ ] 录音时长 < 1s 自动忽略，提示"录音过短/未提交"
- [ ] 用户不看说明也能凭反馈学会操作

---

## Day 10：端到端集成与回归用例

### 做什么
- 固定 demo 流程脚本与测试问题集
- 回归：OCR 回退、TTS 降级、WS 断线、Qdrant 清库

### 学到什么
- AI 系统回归测试的最小可行做法：固定输入 + 固定指标 + 可重复

### 验收
- [ ] 端到端 demo 一次通过率 ≥ 90%（连续 10 次）

---

## Day 11：可观测性与日志（企业味）

### 做什么
- 统一 trace_id/session_id
- 记录各阶段耗时与 provider 选择
- 简易 metrics endpoint（或日志统计）

### 学到什么
- "能优化"来自"可观测"
- 指标驱动迭代

### 验收
- [ ] 任意一次问答能追溯：`stt_ms`/`ocr_ms`/`embed_ms`/`qdrant_ms`/`qa_ms`/`tts_ms`，总耗时与失败点
- [ ] 错误状态下 LCD 显示标准错误码（NET/STT/OCR/AUDIO），LED 红色常亮

---

## Day 12：部署与一键启动

### 做什么
- **Pi**：systemd service
- **MBP**：docker-compose + uvicorn
- config.toml/env 优先级（env > config > mDNS）

### 学到什么
- AI 应用的交付能力：可部署、可重启、可恢复

### 验收
- [ ] 重启 Pi/MBP 后 2 分钟内恢复可用
- [ ] 无需手工进目录跑命令
- [ ] Pi 能通过 `snap2know-mbp.local:8000` 发现 MBP（avahi-daemon 已启用）

---

## Day 13：文档与最终验收用例整理

### 做什么
- README：快速开始、常见问题（mDNS、音频设备、权限）
- Design：验收用例表最终对齐

### 学到什么
- 文档是"工程的一部分"，也是团队协作的关键资产

### 验收
- [ ] 新机器照 README 走一遍能跑起来（你自己也算"新机器"）

---

## Day 14：最终演示与复盘

### 做什么
- Demo：说明书 → 拍照 → 语音提问 → 语音步骤回答
- 复盘：体验痛点、SLA、下一阶段路线

### 学到什么
- 从"能跑"到"能用"的差距在哪里
- 下一阶段（k8s/MLOps/微调）的入口点

### 验收
- [ ] 现场演示一次通过，并能解释：为何这么设计（回退/降级/可观测/体验）

---

## 两周结束后真正获得的能力

你已经掌握 **AI 工程"主干"**：
- 多模态 ingest
- RAG 检索
- 流式生成
- TTS 输出
- 回退降级
- 可观测
- 设备端体验

这套能力可直接迁移到企业场景：**知识库问答、客服助手、现场巡检、设备运维助手**等。

---

## 风险提示

| Day | 风险 | 建议 |
|-----|------|------|
| Day 3-4 | OCR + Embedding 可能超 1 天 | 如果 Day 3 OCR 延迟，可合并 Day 3-4 为"Ingest Pipeline" |
| Day 7 | TTS 分段规则较复杂 | 可先简化（仅强标点切分），后续迭代加保护规则 |
| Day 8 | v2 常驻流需要 ffmpeg 依赖 | 确保 Day 0 已安装 ffmpeg |
| Day 9 | 单键交互细化可能连带调整状态机 | 预留 buffer 时间 |

---

*最后更新：2026-01-16*
