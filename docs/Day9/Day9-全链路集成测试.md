# Day 9：全链路集成测试

## 📅 日期：2026-01-21

## 🎯 目标

验证 Snap2Know 端到端功能：
- Pi 设备 ↔ MBP 后端完整通信
- 完整问答链路：拍照 → 录音 → STT → OCR → 问答 → TTS
- 所有状态正确显示和流转
- 新建会话功能

---

## 📋 测试环境准备

### 1. MBP 后端

```bash
# 确保 MBP 后端运行
cd /Users/mars/sourceCode/personal/ai/Snap2Know/mbp/snap2know
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Pi 设备

```bash
# SSH 连接 Pi
ssh mars@raspberrypi

# 启动 Device Agent
cd /opt/snap2know/device_agent
sudo /opt/snap2know/.venv/bin/python main.py
```

---

## ✅ 测试用例

### Test 1：启动与连接

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| Device Agent 启动 | 无报错 | [x] |
| LCD 初始化 | 显示 "就绪" + 蓝色背景 | [x] |
| MBP 连接 | `[MBP] Connected!` | [x] |
| Session 创建 | `[MBP] Session: xxxxxxxx` | [x] |
| LED 状态 | 蓝色常亮 | [x] |

---

### Test 2：短按拍照入库

**操作**：快速短按按钮（<0.3秒），拍摄包含文字的文档（如路由器说明书）

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 状态变化 | `IDLE -> BUSY` | [x] |
| LCD 显示 | 黄色背景 "拍照中..." | [x] |
| 摄像头 | 拍照成功，log 显示字节数 | [x] |
| 上传结果 | `image_id` 返回 | [x] |
| OCR 识别 | `text_preview` 返回文字内容 | [x] |
| 状态恢复 | `BUSY -> DONE -> IDLE` | [x] |

---

### Test 3：长按录音问答

**操作**：按住按钮 2-4 秒，说 "你好，你是谁？"，然后松开

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| Pre-hold | `IDLE -> PRE_HOLD`（~0.6秒后） | [x] |
| 录音开始 | `PRE_HOLD -> RECORDING` | [x] |
| LCD 显示 | 红色背景 "录音中..." | [x] |
| 录音结束 | 松开后 `RECORDING -> PROCESSING` | [x] |
| STT 识别 | `[STT] Result: 你好...` | [x] |
| Q&A 开始 | `PROCESSING -> ANSWERING` | [x] |
| TTS 请求 | 显示 `[TTS] Requesting:` | [x] |
| 音频播放 | 扬声器清晰播放回复 | [x] |
| 状态完成 | `ANSWERING -> DONE -> IDLE` | [x] |

---

### Test 4：拍照后上下文问答

**操作**：
1. 先用 Test 2 拍摄一张包含文字的图片（如路由器说明书）
2. 长按录音问 "如何登录管理后台？" 或 "这张图片说了什么？"

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 图片已入库 | Test 2 成功完成 | [x] |
| 问答回复 | 基于图片内容回答（非通用回复） | [x] |
| TTS 播放 | 清晰播放相关内容 | [x] |

---

### Test 5：超长按进入菜单

**操作**：按住按钮超过 5 秒

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 状态变化 | `RECORDING -> MENU` | [x] |
| 菜单显示 | LCD 显示菜单选项 | [x] |
| 菜单项 | 清除会话/网络设置/返回 | [x] |

> ⚠️ **待实现**：菜单选择（短按切换）和确认（长按）功能尚未开发

---

### Test 6：新建会话（清除上下文）

> ⏳ **待实现**：依赖 Test 5 的菜单交互功能

**操作**：在菜单中选择 "清除会话"

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 会话清除 | 新 Session ID 生成 | [ ] 待开发 |
| 历史清空 | 再次问答不引用之前的图片 | [ ] 待开发 |

---

### Test 7：错误处理

**准备**：关闭 MBP 后端

```bash
# 停止 MBP 后端
pkill -f "uvicorn main:app"

# 验证已停止
curl http://localhost:8000/health || echo "MBP backend stopped"
```

**操作**：在 Pi 上尝试短按拍照或长按录音

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 连接失败 | 显示错误状态 | [x] |
| LCD 显示 | 红色背景 "错误" + 错误信息 | [x] |
| 可恢复 | 重启后端后可正常工作 | [x] |

**恢复**：重启 MBP 后端

```bash
cd /Users/mars/sourceCode/personal/ai/Snap2Know/mbp/snap2know
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Test 8：播放中取消

**操作**：在 TTS 播放过程中按住按钮 ≥1.2 秒

| 检查项 | 预期结果 | 状态 |
|--------|----------|------|
| 播放停止 | 语音立即停止 | [x] |
| 状态恢复 | 返回 IDLE | [x] |

---

## 📊 LCD 状态显示验收

| 状态 | 图标 | LED | 文案 | 状态 |
|------|------|-----|------|------|
| idle | 📷 | 蓝色 | "就绪 / 短按拍照" | [x] |
| recording | 🎤 | 红色 | "录音中..." + 时长 | [x] |
| busy | ⏳ | 黄色 | "处理中..." | [x] |
| answering | ▶ | 绿色 | "播放中..." | [x] |
| error | ⚠ | 红色 | 错误信息 | [x] |
| menu | ☰ | - | 菜单选项 | [x] |

---

## 📊 测试结果汇总

| 测试 | 结果 |
|------|------|
| Test 1：启动与连接 | ✅ |
| Test 2：短按拍照 | ✅ |
| Test 3：长按问答 | ✅ |
| Test 4：上下文问答 | ✅ |
| Test 5：菜单功能 | ✅ 进入菜单（交互待开发） |
| Test 6：新建会话 | ⏳ 待开发 |
| Test 7：错误处理 | ✅ |
| Test 8：播放取消 | ✅ |

---

## 🔗 相关链接

- [Day 8：LCD 状态渲染完善](../Day8/Day8-LCD%20状态渲染完善.md)
- [Design.md](../../design.md)