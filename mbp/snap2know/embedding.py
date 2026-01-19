"""
Snap2Know Embedding Module
Generate text embeddings using OpenAI API
"""
from typing import List
import httpx
from openai import OpenAI
from config import settings


def get_openai_client() -> OpenAI:
    """获取配置好的 OpenAI 客户端"""
    client_kwargs = {"api_key": settings.openai_api_key}
    
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    return OpenAI(**client_kwargs)


def generate_embedding(text: str) -> List[float]:
    """
    生成单个文本的 embedding
    
    Args:
        text: 要生成 embedding 的文本
    
    Returns:
        embedding 向量（1536 维）
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    client = get_openai_client()
    
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text.strip(),
        dimensions=settings.embedding_dimensions
    )
    
    return response.data[0].embedding


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    批量生成 embeddings
    
    Args:
        texts: 文本列表
    
    Returns:
        embedding 向量列表
    """
    if not texts:
        return []
    
    # 过滤空文本
    valid_texts = [t.strip() for t in texts if t and t.strip()]
    if not valid_texts:
        return []
    
    client = get_openai_client()
    
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=valid_texts,
        dimensions=settings.embedding_dimensions
    )
    
    # 按顺序返回 embeddings
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
