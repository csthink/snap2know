"""
Snap2Know RAG Module
Retrieval-Augmented Generation: context retrieval and prompt building
"""
from typing import List, Dict, Any, Tuple
from config import settings
from embedding import generate_embedding
from qdrant_store import search_similar_chunks


# RAG 配置
RAG_TOP_K = 6           # 默认检索文档数量
RAG_MAX_CONTEXT = 4000  # 上下文最大字符数


async def retrieve_context(
    question: str,
    session_id: str = None,
    top_k: int = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    检索与问题相关的文档上下文
    
    Args:
        question: 用户问题
        session_id: 会话 ID（限定检索范围）
        top_k: 检索文档数量
    
    Returns:
        (检索结果列表, 拼接后的上下文文本)
    """
    top_k = top_k or RAG_TOP_K
    
    # 生成问题的 Embedding
    question_embedding = generate_embedding(question)
    
    # 搜索相似文档
    results = search_similar_chunks(
        query_embedding=question_embedding,
        session_id=session_id,
        limit=top_k
    )
    
    if not results:
        return [], ""
    
    # 构建上下文（按相关性排序，截断到最大长度）
    context_parts = []
    total_length = 0
    
    for i, result in enumerate(results):
        text = result.get("text", "")
        if not text:
            continue
        
        # 检查是否超过最大长度
        if total_length + len(text) > RAG_MAX_CONTEXT:
            # 截断最后一部分
            remaining = RAG_MAX_CONTEXT - total_length
            if remaining > 100:  # 至少保留 100 字符
                context_parts.append(f"[文档{i+1}] {text[:remaining]}...")
            break
        
        context_parts.append(f"[文档{i+1}] {text}")
        total_length += len(text)
    
    context_text = "\n\n".join(context_parts)
    
    return results, context_text


def build_system_prompt() -> str:
    """构建系统提示词"""
    return """你是 Snap2Know 智能助手。用户会拍摄产品说明书、使用手册等文档，你需要根据检索到的文档内容回答用户问题。

请遵循以下规则：
1. 只根据提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请明确告知用户
3. 回答要简洁、准确、易懂
4. 如果是操作步骤，请分点列出
5. 使用中文回答"""


def build_user_prompt(question: str, context: str) -> str:
    """
    构建用户提示词
    
    Args:
        question: 用户问题
        context: 检索到的文档上下文
    
    Returns:
        完整的用户提示词
    """
    if not context:
        return f"""用户问题：{question}

注意：未找到相关文档内容。请告知用户需要先拍摄相关文档。"""
    
    return f"""以下是从用户拍摄的文档中检索到的相关内容：

{context}

---

用户问题：{question}

请根据以上文档内容回答用户的问题。"""


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量（粗略估算）
    中文约 1.5 字符/token，英文约 4 字符/token
    """
    # 简单估算：平均 2 字符/token
    return len(text) // 2
