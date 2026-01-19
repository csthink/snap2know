"""
Snap2Know STT (Speech-to-Text) API
Using OpenAI Whisper API
"""
import time
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from config import settings

router = APIRouter()


class STTResponse(BaseModel):
    """STT 响应"""
    question_text: str
    stt_ms: int
    session_id: str


@router.post("/upload/audio", response_model=STTResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    session_id: str = Query(..., description="会话 ID")
):
    """
    语音转文字 API
    
    - 接收音频文件（wav/mp3/webm）
    - 调用 OpenAI Whisper API 进行转写
    - 返回识别文本和耗时
    """
    # 验证 API Key
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY not configured"
        )
    
    # 验证文件类型
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/x-wav"]
    content_type = audio.content_type
    if content_type not in allowed_types:
        # 也接受没有明确 content_type 的文件
        if audio.filename and not audio.filename.endswith(('.wav', '.mp3', '.webm')):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {content_type}. Allowed: wav, mp3, webm"
            )
    
    # 读取音频内容
    audio_content = await audio.read()
    
    # 配置 OpenAI 客户端（支持代理和自定义地址）
    import httpx
    
    client_kwargs = {"api_key": settings.openai_api_key}
    
    # 自定义 API 地址
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    
    # 代理配置
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    client = OpenAI(**client_kwargs)
    
    start_time = time.time()
    try:
        # 创建临时文件对象用于 API 调用
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=(audio.filename or "audio.wav", audio_content),
            language="zh",  # 中文
            response_format="text"
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return STTResponse(
            question_text=transcription.strip(),
            stt_ms=elapsed_ms,
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"STT failed: {str(e)}"
        )
