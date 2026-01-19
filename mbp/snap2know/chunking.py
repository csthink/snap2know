"""
Snap2Know Text Chunking
Split text into overlapping chunks for embedding
"""
from typing import List
from config import settings


def split_text_into_chunks(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None
) -> List[str]:
    """
    将文本分割成重叠的块
    
    Args:
        text: 要分割的文本
        chunk_size: 每块最大字符数（默认使用配置）
        chunk_overlap: 块间重叠字符数（默认使用配置）
    
    Returns:
        文本块列表
    """
    if not text or not text.strip():
        return []
    
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    
    # 清理文本
    text = text.strip()
    
    # 如果文本短于 chunk_size，直接返回
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # 计算结束位置
        end = start + chunk_size
        
        # 如果不是最后一块，尝试在句子边界处分割
        if end < len(text):
            # 寻找最近的句子结束符
            best_break = -1
            for sep in ['。', '！', '？', '\n', '；', '.', '!', '?']:
                pos = text.rfind(sep, start, end)
                if pos > best_break:
                    best_break = pos
            
            # 如果找到了句子边界，在那里分割
            if best_break > start + chunk_size // 2:
                end = best_break + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 计算下一块的起始位置（考虑重叠）
        start = end - chunk_overlap
        
        # 确保不会无限循环
        if start >= len(text) - chunk_overlap:
            break
    
    return chunks


def estimate_chunks_count(text: str) -> int:
    """估算文本会产生多少个块"""
    if not text:
        return 0
    
    text_len = len(text.strip())
    if text_len <= settings.chunk_size:
        return 1
    
    # 估算：每个有效块 = chunk_size - overlap
    effective_chunk_size = settings.chunk_size - settings.chunk_overlap
    return max(1, (text_len + effective_chunk_size - 1) // effective_chunk_size)
