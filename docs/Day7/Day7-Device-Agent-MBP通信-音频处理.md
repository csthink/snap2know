# Day 7：Device Agent MBP 通信 + 音频处理

**交付**
- Backend Client：HTTP 上传图片/音频、WS 问答
- TTS 分段播报（buffer → flush → 播放队列 → WM8960 扬声器）
- 静音切换、长按停止
- 错误状态处理（网络断开、API 失败等）

**验收**
- [ ] 上传图片 → MBP OCR 入库成功
- [ ] 上传音频 → MBP STT 返回文字
- [ ] WS 问答 → 流式 token 到达
- [ ] TTS 分段播报，不是"每 token 一声"
- [ ] 短按可静音/恢复
- [ ] 长按停止：立即停止播放 + 清空队列
- [ ] 断网时进入 Error 状态，短按可重试