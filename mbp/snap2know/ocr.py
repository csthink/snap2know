"""
Snap2Know OCR Module
Image OCR using Claude Sonnet (primary) and GPT-4o (fallback)
"""
import time
import base64
import uuid
from typing import Tuple, Optional
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel
import httpx
from config import settings
from chunking import split_text_into_chunks
from embedding import generate_embeddings_batch
from qdrant_store import store_chunks, ensure_collection_exists

router = APIRouter()


class OCRResponse(BaseModel):
    """OCR 响应"""
    image_id: str
    num_chunks: int
    ingest_ms: int
    ocr_provider: str
    fallback_used: bool
    text_preview: Optional[str] = None  # 前 200 字符预览


async def ocr_with_claude(image_base64: str, mime_type: str) -> str:
    """
    使用 Claude Sonnet Vision 进行 OCR
    
    Args:
        image_base64: Base64 编码的图片
        mime_type: 图片 MIME 类型
    
    Returns:
        识别的文本
    """
    import anthropic
    
    client_kwargs = {"api_key": settings.anthropic_api_key}
    
    if settings.anthropic_base_url:
        client_kwargs["base_url"] = settings.anthropic_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    client = anthropic.Anthropic(**client_kwargs)
    
    # OpenRouter 兼容：使用标准 Claude 模型名
    model_name = "claude-3-5-sonnet-20241022"
    
    message = client.messages.create(
        model=model_name,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的所有文字内容。只输出识别到的文字，不要添加任何解释或评论。如果图片中没有文字，请输出'无文字内容'。"
                    }
                ]
            }
        ],
        timeout=settings.ocr_primary_timeout_sec
    )
    
    return message.content[0].text


async def ocr_with_gpt4o(image_base64: str, mime_type: str) -> str:
    """
    使用 GPT-4o Vision 进行 OCR（回退方案）
    
    Args:
        image_base64: Base64 编码的图片
        mime_type: 图片 MIME 类型
    
    Returns:
        识别的文本
    """
    from openai import OpenAI
    
    client_kwargs = {"api_key": settings.openai_api_key}
    
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    client = OpenAI(**client_kwargs)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的所有文字内容。只输出识别到的文字，不要添加任何解释或评论。如果图片中没有文字，请输出'无文字内容'。"
                    }
                ]
            }
        ],
        max_tokens=4096,
        timeout=settings.ocr_fallback_timeout_sec
    )
    
    return response.choices[0].message.content


async def perform_ocr(image_base64: str, mime_type: str) -> Tuple[str, str, bool]:
    """
    执行 OCR，主路径失败时自动回退
    
    Returns:
        (识别文本, 提供者, 是否使用了回退)
    """
    # 尝试主路径：Claude Sonnet
    try:
        text = await ocr_with_claude(image_base64, mime_type)
        return text, "claude_sonnet", False
    except Exception as e:
        if settings.debug:
            print(f"Claude OCR failed: {e}")
    
    # 回退到 GPT-4o
    try:
        text = await ocr_with_gpt4o(image_base64, mime_type)
        return text, "gpt4o", True
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: both primary (Claude) and fallback (GPT-4o) failed. Last error: {str(e)}"
        )


@router.post("/upload/image", response_model=OCRResponse)
async def upload_image(
    image: UploadFile = File(...),
    session_id: str = Query(..., description="会话 ID")
):
    """
    上传图片进行 OCR 识别并存入向量库
    
    1. 接收图片
    2. OCR 识别（Claude 主路径，GPT-4o 回退）
    3. 文本切块
    4. 生成 Embedding
    5. 存入 Qdrant
    """
    start_time = time.time()
    
    # 验证文件类型
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    content_type = image.content_type
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format: {content_type}. Allowed: jpg, png, webp"
        )
    
    # 读取图片并转 Base64
    image_content = await image.read()
    image_base64 = base64.b64encode(image_content).decode("utf-8")
    
    # 执行 OCR
    ocr_text, ocr_provider, fallback_used = await perform_ocr(image_base64, content_type)
    
    # 检查是否有有效文本
    if not ocr_text or ocr_text.strip() == "无文字内容":
        return OCRResponse(
            image_id=str(uuid.uuid4())[:8],
            num_chunks=0,
            ingest_ms=int((time.time() - start_time) * 1000),
            ocr_provider=ocr_provider,
            fallback_used=fallback_used,
            text_preview="无文字内容"
        )
    
    # 文本切块
    chunks = split_text_into_chunks(ocr_text)
    
    if not chunks:
        return OCRResponse(
            image_id=str(uuid.uuid4())[:8],
            num_chunks=0,
            ingest_ms=int((time.time() - start_time) * 1000),
            ocr_provider=ocr_provider,
            fallback_used=fallback_used,
            text_preview=ocr_text[:200] if ocr_text else None
        )
    
    # 生成 Embeddings
    embeddings = generate_embeddings_batch(chunks)
    
    # 存入 Qdrant
    image_id = str(uuid.uuid4())[:8]
    num_stored = store_chunks(
        chunks=chunks,
        embeddings=embeddings,
        session_id=session_id,
        image_id=image_id,
        ocr_provider=ocr_provider
    )
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return OCRResponse(
        image_id=image_id,
        num_chunks=num_stored,
        ingest_ms=elapsed_ms,
        ocr_provider=ocr_provider,
        fallback_used=fallback_used,
        text_preview=ocr_text[:200] if ocr_text else None
    )


@router.get("/qdrant/stats")
async def get_qdrant_stats():
    """获取 Qdrant 统计信息"""
    from qdrant_store import get_collection_stats
    
    # 确保 Collection 存在
    ensure_collection_exists()
    
    return get_collection_stats()
