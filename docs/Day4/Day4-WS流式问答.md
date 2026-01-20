# Day 4：WS 流式问答

> **目标**：实现 WebSocket 流式问答 API，支持 RAG 检索 + Claude Sonnet 回答

## 前置要求

- ✅ Day 3 完成（OCR 入库 + Qdrant 存储就绪）
- Qdrant 中有已入库的文档数据
- Anthropic API Key（Claude Sonnet）

---

## 交付内容

- `WS /ws/chat` → 检索相关文档 → Claude Sonnet 回答 → 流式返回
- 三种消息类型：`meta` / `token` / `done` / `error`

---

## 项目结构更新

```
mbp/snap2know/
├── main.py          # 更新：注册 WebSocket 路由
├── ws_chat.py       # 新增：WebSocket 流式问答
├── rag.py           # 新增：RAG 检索与上下文构建
├── test_ws_chat.py  # 新增：测试脚本
├── qdrant_store.py  # 更新：使用 query_points API
├── embedding.py     # 已有：Embedding 生成
└── ...
```

---

## 消息协议

### 客户端请求

```json
{
  "question_text": "如何登录管理后台",
  "top_k": 6,
  "session_id": "可选"
}
```

### 服务端响应

**1. Meta 消息**
```json
{
  "type": "meta",
  "trace_id": "4a3eec39",
  "retrieved": [{"text": "...", "score": 0.92}],
  "retrieved_count": 1,
  "context_tokens": 133
}
```

**2. Token 消息（多条）**
```json
{
  "type": "token",
  "text": "根据文档"
}
```

**3. Done 消息**
```json
{
  "type": "done",
  "trace_id": "4a3eec39",
  "total_ms": 6960,
  "total_tokens": 112
}
```

**4. Error 消息**
```json
{
  "type": "error",
  "message": "错误描述"
}
```

---

## 验收测试

### 1. 启动服务

```bash
cd mbp/snap2know
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Python 测试脚本

```bash
python test_ws_chat.py
```

**实际输出**：
```
连接 WebSocket...
发送问题: 如何登录管理后台

[META] trace_id=4a3eec39
  检索到 1 条文档
  上下文 tokens: 133

回答: 根据文档内容，您有以下两种方式可以登录华为路由器管理后台：

1. 通过手机App登录：
- 下载并安装华为路由器管理App
- 打开App进行登录操作

2. 通过现场路由器登录：
- 连接到路由器的WiFi网络
- 通过浏览器访问路由器管理页面

[DONE] 耗时 6960ms, tokens=112

完整回答长度: 225 字符
```

---

## 技术说明

### API 代理 Streaming 限制

当前使用的 API 代理服务（api.gptsapi.net）不支持 Claude streaming API。解决方案：

1. 使用非流式 API 获取完整回答
2. 将回答分块（每 5 字符）模拟流式发送
3. 添加 10ms 延迟使输出更流畅

### Qdrant Client API 更新

新版 `qdrant-client` 使用 `query_points()` 替代旧版 `search()` 方法：

```python
# 旧版（已弃用）
client.search(collection_name, query_vector=...)

# 新版
client.query_points(collection_name, query=...)
```

---

## 验收清单

- [x] `rag.py` 模块创建（检索 + 上下文构建）
- [x] `ws_chat.py` 模块创建（WebSocket 处理）
- [x] `main.py` 注册 WebSocket 路由
- [x] 收到 `{type: "meta", trace_id, retrieved}` ✅
- [x] 收到多条 `{type: "token", text}` ✅
- [x] 最后收到 `{type: "done", total_ms}` ✅
- [x] RAG 检索正确（1 条文档，133 tokens）✅
- [x] Claude 回答质量良好 ✅

---

## 下一步

✅ Day 4 完成，继续 [Day 5：Pi Device Agent 骨架 + 硬件封装](../Day5/Day5-Pi-Device-Agent骨架-硬件封装.md)
