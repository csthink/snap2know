# Day 8：LCD 状态渲染完善 + TTS 播放修复

## 📅 日期：2026-01-20

## ✅ 完成状态

### 1. LCD 驱动集成

- [x] 使用官方 `WhisplayBoard` 驱动（位于 `/opt/whisplay-ai-chatbot/python/`）
- [x] 修复 GPIO 冲突：LCD 和 Button 共享 WhisplayBoard 实例
- [x] 中文字体渲染：使用 `NotoSansCJK-Bold.ttc`
- [x] 状态颜色映射：
  - idle → 蓝色
  - recording → 红色
  - processing → 黄色
  - answering → 绿色
  - error → 红色
  - done → 青色

### 2. 按钮处理优化

- [x] 使用 WhisplayBoard 的 `on_button_press` / `on_button_release` 回调
- [x] 超长按阈值从 3s 调整为 5s（允许更长录音）
- [x] 修复短按/长按检测

### 3. TTS 语音播放修复

- [x] 添加 `_pending_requests` 计数器防止播放循环过早退出
- [x] 添加 `_expecting_more` 标志控制播放循环生命周期
- [x] 添加 `mark_done()` 方法标记内容结束
- [x] 修复 MP3 格式检测（支持 `0xFF 0xFx` 同步字）
- [x] 安装 `mpg123` 播放器

### 4. 其他修复

- [x] STT 端点从 `/stt` 修正为 `/upload/audio`
- [x] STT 响应字段从 `text` 修正为 `question_text`
- [x] 音频设备从 `plughw:1,0` 更新为 `plughw:2,0`
- [x] venv 使用系统 RPi.GPIO（支持 Pi 5）

---

## 📁 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `hardware/lcd.py` | 使用 WhisplayBoard 驱动，添加 `get_board()` 方法 |
| `hardware/button.py` | 使用 WhisplayBoard 回调，添加 `set_board()` 方法 |
| `hardware/audio.py` | 修复 MP3 格式检测 |
| `services/tts_player.py` | 添加 pending 计数器和 expecting 标志 |
| `services/mbp_client.py` | 修复 STT 端点和响应字段 |
| `services/button_handler.py` | 超长按阈值改为 5s |
| `services/lcd_renderer.py` | 添加 Noto CJK 字体路径，使用 `draw_image()` |
| `main.py` | LCD/Button 共享 WhisplayBoard，调用 `mark_done()` |

---

## ✅ 验收结果

| 测试项 | 结果 |
|--------|------|
| LCD 显示就绪状态 | ✅ 蓝色背景 + "就绪" + 中文正常 |
| LCD 显示录音状态 | ✅ 红色背景 + "录音中..." |
| LCD 显示处理状态 | ✅ 黄色背景 + "处理中..." |
| LCD 显示回答状态 | ✅ 绿色背景 + "播放中..." |
| 短按拍照 | ✅ 拍照 → 上传 → OCR 完成 |
| 长按录音 | ✅ 录音 → STT → Q&A → TTS 播放 |
| TTS 语音播放 | ✅ 清晰播放回复内容 |

---

## 🔗 相关链接

- [Day 7 文档](../Day7/Day7-Device-Agent-MBP通信-音频处理.md)
- [Design.md](../../design.md)
