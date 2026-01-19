"""
Snap2Know TTS (Text-to-Speech) API
Supports: edge-tts (default), OpenAI TTS (cloud)
"""
import asyncio
import io
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal
from config import settings

router = APIRouter()


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str
    voice: Optional[str] = None  # 语音选择
    mode: Optional[Literal["auto", "edge", "cloud"]] = None  # TTS 模式


class TTSInfo(BaseModel):
    """TTS 信息响应"""
    available_modes: list
    current_mode: str
    edge_voices: list
    openai_voices: list


# Edge-TTS 中文语音列表
EDGE_VOICES = {
    "zh-CN-XiaoxiaoNeural": "晓晓（女，温柔）",
    "zh-CN-YunxiNeural": "云希（男，年轻）",
    "zh-CN-YunjianNeural": "云健（男，新闻）",
    "zh-CN-XiaoyiNeural": "晓伊（女，活泼）",
}

# OpenAI TTS 语音列表
OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


async def tts_edge(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """使用 edge-tts 生成语音"""
    import edge_tts
    
    communicate = edge_tts.Communicate(text, voice)
    audio_data = io.BytesIO()
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])
    
    return audio_data.getvalue()


async def tts_openai(text: str, voice: str = "alloy") -> bytes:
    """使用 OpenAI TTS 生成语音"""
    from openai import OpenAI
    import httpx
    
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    
    client_kwargs = {"api_key": settings.openai_api_key}
    
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    client = OpenAI(**client_kwargs)
    
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3"
    )
    
    return response.content


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    文字转语音 API
    
    - 接收文本
    - 根据模式选择 TTS 引擎
    - 返回 MP3 音频流
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # 确定 TTS 模式
    mode = request.mode or settings.tts_mode
    
    try:
        if mode == "cloud":
            # OpenAI TTS
            voice = request.voice if request.voice in OPENAI_VOICES else "alloy"
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: asyncio.run(tts_openai_sync(text, voice))
            )
        else:
            # edge-tts (auto 或 edge 模式)
            voice = request.voice if request.voice in EDGE_VOICES else "zh-CN-XiaoxiaoNeural"
            audio_data = await tts_edge(text, voice)
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=tts_output.mp3"
            }
        )
        
    except Exception as e:
        # 如果 edge-tts 失败，尝试降级到 espeak-ng（本地）
        if mode == "auto":
            try:
                audio_data = await tts_espeak_fallback(text)
                return StreamingResponse(
                    io.BytesIO(audio_data),
                    media_type="audio/wav"
                )
            except Exception:
                pass
        
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


async def tts_openai_sync(text: str, voice: str) -> bytes:
    """同步包装 OpenAI TTS（用于 run_in_executor）"""
    from openai import OpenAI
    import httpx
    
    client_kwargs = {"api_key": settings.openai_api_key}
    
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    client = OpenAI(**client_kwargs)
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3"
    )
    return response.content


async def tts_espeak_fallback(text: str) -> bytes:
    """espeak-ng 本地降级方案"""
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = f.name
    
    try:
        subprocess.run(
            ["espeak-ng", "-v", "zh", "-w", output_path, text],
            check=True,
            capture_output=True,
            timeout=10
        )
        
        with open(output_path, "rb") as f:
            return f.read()
    finally:
        import os
        if os.path.exists(output_path):
            os.unlink(output_path)


@router.get("/tts/info", response_model=TTSInfo)
async def get_tts_info():
    """获取 TTS 配置信息"""
    return TTSInfo(
        available_modes=["auto", "edge", "cloud"],
        current_mode=settings.tts_mode,
        edge_voices=list(EDGE_VOICES.keys()),
        openai_voices=OPENAI_VOICES
    )
