# Qdrant 向量数据库知识普及

> 本文档介绍 Qdrant 向量数据库的基础概念及其在 Snap2Know 项目中的应用

## 什么是 Qdrant？

**Qdrant**（读作 "quadrant"）是一个开源的向量相似性搜索引擎，专门用于存储和检索高维向量数据。它是构建 AI 应用（如语义搜索、推荐系统、RAG 等）的核心基础设施。

### 核心特性

| 特性 | 说明 |
|------|------|
| **向量存储** | 高效存储高维向量（如 1536 维的 OpenAI Embedding）|
| **相似性搜索** | 基于余弦相似度、欧氏距离等进行快速检索 |
| **Payload 存储** | 向量可附带结构化元数据（JSON）|
| **过滤查询** | 支持在搜索时添加条件过滤 |
| **水平扩展** | 支持分布式部署和分片 |
| **REST/gRPC API** | 提供多种接口方式 |

---

## 核心概念

### 1. Collection（集合）

类似于关系数据库中的"表"，用于存储同类型的向量数据。

```python
# 创建 Collection
client.create_collection(
    collection_name="snap2know_chunks",
    vectors_config=VectorParams(
        size=1536,           # 向量维度
        distance=Distance.COSINE  # 相似度计算方式
    )
)
```

### 2. Point（点）

Collection 中的一条记录，包含：
- **ID**：唯一标识符
- **Vector**：向量数据
- **Payload**：附加的元数据

```python
# 一个 Point 的结构
{
    "id": "uuid-xxx",
    "vector": [0.1, 0.2, ..., 0.9],  # 1536 维
    "payload": {
        "session_id": "abc123",
        "text": "原始文本内容",
        "image_id": "img001"
    }
}
```

### 3. Vector（向量）

文本/图片等数据通过 Embedding 模型转换后的数值表示。

```
"你好世界" → Embedding 模型 → [0.1, -0.3, 0.5, ..., 0.2] (1536维)
```

### 4. Distance（距离度量）

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `COSINE` | 余弦相似度 | 文本语义相似 |
| `EUCLID` | 欧氏距离 | 图像特征 |
| `DOT` | 点积 | 推荐系统 |

---

## Qdrant 在 Snap2Know 中的应用

### 整体架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   用户拍照   │────▶│   OCR 识别   │────▶│  文本切块   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌──────────────┐            ▼
                    │   Qdrant     │◀──── OpenAI Embedding
                    │ 向量数据库   │
                    └──────┬───────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
      ▼                    ▼                    ▼
┌──────────┐        ┌──────────┐        ┌──────────┐
│ 相似搜索  │        │ 上下文构建 │        │  回答生成 │
└──────────┘        └──────────┘        └──────────┘
```

### 数据流程

1. **图片上传** → OCR 识别出文字
2. **文本切块** → 按 500 字符分块，50 字符重叠
3. **生成 Embedding** → OpenAI `text-embedding-3-small`
4. **存入 Qdrant** → 向量 + 元数据
5. **用户提问** → 问题 Embedding → 相似搜索 → 构建上下文 → LLM 回答

### Collection 设计

**集合名称**：`snap2know_chunks`

**向量配置**：
```python
VectorParams(
    size=1536,              # OpenAI embedding 维度
    distance=Distance.COSINE  # 余弦相似度
)
```

**Payload 结构**：
```json
{
    "session_id": "会话ID，用于隔离不同用户/场景的数据",
    "image_id": "图片ID，关联原始图片",
    "chunk_index": 0,  // 块序号
    "text": "原始文本内容",
    "ocr_provider": "claude_sonnet",  // OCR 使用的模型
    "created_at": "2026-01-19T14:30:00"
}
```

---

## 项目中的代码实现

### 1. 客户端封装 (`qdrant_store.py`)

```python
from qdrant_client import QdrantClient
from config import settings

def get_qdrant_client() -> QdrantClient:
    """获取 Qdrant 客户端"""
    return QdrantClient(
        host=settings.qdrant_host,  # localhost
        port=settings.qdrant_port   # 6333
    )
```

### 2. Collection 管理

```python
def ensure_collection_exists() -> bool:
    """确保 Collection 存在，不存在则创建"""
    client = get_qdrant_client()
    
    # 检查是否存在
    collections = client.get_collections().collections
    exists = any(c.name == "snap2know_chunks" for c in collections)
    
    if not exists:
        client.create_collection(
            collection_name="snap2know_chunks",
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE
            )
        )
    return not exists
```

### 3. 存储向量

```python
def store_chunks(chunks, embeddings, session_id, image_id, ocr_provider):
    """存储文本块和向量"""
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "session_id": session_id,
                "image_id": image_id,
                "chunk_index": i,
                "text": chunk,
                "ocr_provider": ocr_provider,
                "created_at": datetime.now().isoformat()
            }
        ))
    
    client.upsert(collection_name="snap2know_chunks", points=points)
```

### 4. 相似搜索

```python
def search_similar_chunks(query_embedding, session_id=None, limit=5):
    """搜索相似的文本块"""
    
    # 构建过滤条件（限定会话范围）
    query_filter = None
    if session_id:
        query_filter = Filter(
            must=[FieldCondition(
                key="session_id",
                match=MatchValue(value=session_id)
            )]
        )
    
    results = client.search(
        collection_name="snap2know_chunks",
        query_vector=query_embedding,
        query_filter=query_filter,
        limit=limit
    )
    
    return [{"text": hit.payload["text"], "score": hit.score} for hit in results]
```

---

## 常用操作命令

### 启动 Qdrant

```bash
cd mbp
docker-compose up -d
```

### 健康检查

```bash
curl http://localhost:6333/healthz
# healthz check passed
```

### Web UI

访问 [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### 查看 Collection

```bash
curl http://localhost:6333/collections/snap2know_chunks
```

### 查看数据量

```bash
curl http://localhost:8000/qdrant/stats
# {"name":"snap2know_chunks","points_count":1,"status":"green"}
```

---

## 为什么选择 Qdrant？

| 对比项 | Qdrant | Pinecone | Milvus |
|--------|--------|----------|--------|
| **部署方式** | 本地 Docker / 云 | 仅云服务 | 本地 / 云 |
| **开源** | ✅ 完全开源 | ❌ | ✅ |
| **Payload** | ✅ 原生支持 | ✅ | ✅ |
| **过滤** | ✅ 强大 | ✅ | ✅ |
| **学习成本** | 低 | 低 | 中 |
| **资源占用** | 轻量 | N/A | 较重 |

**Snap2Know 选择 Qdrant 的原因**：
1. ✅ 轻量级，适合边缘设备场景
2. ✅ 完全开源，无云服务依赖
3. ✅ 本地部署，数据隐私可控
4. ✅ REST API 简单易用
5. ✅ Python SDK 完善

---

## 参考资料

- [Qdrant 官方文档](https://qdrant.tech/documentation/)
- [Qdrant Python SDK](https://github.com/qdrant/qdrant-client)
- [Qdrant 快速入门](https://qdrant.tech/documentation/quickstart/)
- [向量搜索原理](https://qdrant.tech/articles/vector-search/)
