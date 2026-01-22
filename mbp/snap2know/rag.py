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


def build_system_prompt(has_context: bool = True) -> str:
    """
    构建系统提示词
    
    Args:
        has_context: 是否有文档上下文
    """
    if has_context:
        return """你是 Snap2Know 智能助手。用户正在通过语音与通过摄像头拍摄的文档进行交互。你需要根据检索到的文档内容回答用户问题。

请严格遵循以下规则，以优化语音播报体验：
1. **口语化表达**：像一个真实的人在说话。使用通俗易懂的语言，避免生硬的书面语。
2. **禁止 Markdown**：严禁使用 **加粗**、# 标题、> 引用等 Markdown 符号，因为 TTS 会读出噪音。
3. **分步说明**：如果是操作步骤，请使用"第一步"、"第二步"、"最后"等连接词，而不要使用 "1."、"2." 这种列表格式。
4. **风险前置**：如果涉及由于复位、恢复出厂设置等高风险操作，必须在回答的最开始说："【注意风险】"，并优先播报风险警告。
5. **控制长度**：单次回答尽量控制在 100 字以内。如果内容很长，先概括重点，然后引导用户追问细节。
6. **使用中文回答**。"""
    else:
        return """你是 Snap2Know 智能助手，一个友好的语音AI伴侣。

请严格遵循以下规则：
1. **口语化表达**：像朋友聊天一样自然，避免机械感。
2. **禁止 Markdown**：严禁使用任何 Markdown 符号。
3. **简洁明了**：回答要简短有力，适合语音收听。
4. **使用中文回答**。"""


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
        # 无文档上下文：直接回答用户问题（混合模式）
        return f"""用户问题：{question}

请直接回答用户的问题。"""
    
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
