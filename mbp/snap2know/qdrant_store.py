"""
Snap2Know Qdrant Client
Vector database operations for storing and querying chunks
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)
from config import settings


def get_qdrant_client() -> QdrantClient:
    """获取 Qdrant 客户端"""
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port
    )


def ensure_collection_exists() -> bool:
    """
    确保 Collection 存在，不存在则创建
    
    Returns:
        是否新创建了 Collection
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection
    
    # 检查是否存在
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if not exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dimensions,
                distance=Distance.COSINE
            )
        )
        return True
    
    return False


def store_chunks(
    chunks: List[str],
    embeddings: List[List[float]],
    session_id: str,
    image_id: str,
    ocr_provider: str
) -> int:
    """
    存储文本块和向量到 Qdrant
    
    Args:
        chunks: 文本块列表
        embeddings: 对应的向量列表
        session_id: 会话 ID
        image_id: 图片 ID
        ocr_provider: OCR 提供者（claude_sonnet/gpt4o）
    
    Returns:
        存储的块数量
    """
    if not chunks or not embeddings:
        return 0
    
    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings count mismatch")
    
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection
    
    # 确保 Collection 存在
    ensure_collection_exists()
    
    now = datetime.now().isoformat()
    
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "session_id": session_id,
                    "image_id": image_id,
                    "chunk_index": i,
                    "text": chunk,
                    "ocr_provider": ocr_provider,
                    "created_at": now
                }
            )
        )
    
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    return len(points)


def search_similar_chunks(
    query_embedding: List[float],
    session_id: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    搜索相似的文本块
    
    Args:
        query_embedding: 查询向量
        session_id: 可选，限制在特定会话内搜索
        limit: 返回结果数量
    
    Returns:
        相似块列表，包含 text, score, payload
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection
    
    # 构建过滤条件
    query_filter = None
    if session_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="session_id",
                    match=MatchValue(value=session_id)
                )
            ]
        )
    
    # 使用新版 API: query_points
    results = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=query_filter,
        limit=limit
    )
    
    return [
        {
            "text": hit.payload.get("text", "") if hit.payload else "",
            "score": hit.score,
            "session_id": hit.payload.get("session_id") if hit.payload else None,
            "image_id": hit.payload.get("image_id") if hit.payload else None,
            "chunk_index": hit.payload.get("chunk_index") if hit.payload else None,
            "ocr_provider": hit.payload.get("ocr_provider") if hit.payload else None
        }
        for hit in results.points
    ]


def get_collection_stats() -> Dict[str, Any]:
    """获取 Collection 统计信息"""
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection
    
    try:
        info = client.get_collection(collection_name)
        # 兼容不同版本的 qdrant-client
        points_count = getattr(info, 'points_count', None)
        if points_count is None:
            points_count = info.points_count if hasattr(info, 'points_count') else 0
        
        return {
            "name": collection_name,
            "points_count": points_count,
            "status": info.status.value if hasattr(info.status, 'value') else str(info.status)
        }
    except Exception as e:
        return {
            "name": collection_name,
            "error": str(e)
        }


def delete_session_chunks(session_id: str) -> int:
    """
    删除指定会话的所有块
    
    Returns:
        删除的块数量
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection
    
    result = client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="session_id",
                    match=MatchValue(value=session_id)
                )
            ]
        )
    )
    
    return result.status.value == "completed"
