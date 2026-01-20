"""
Snap2Know MBP Backend - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from session import router as session_router
from stt import router as stt_router
from tts import router as tts_router
from ocr import router as ocr_router
from ws_chat import router as ws_chat_router

app = FastAPI(
    title="Snap2Know API",
    description="智能问答设备后端服务",
    version="0.1.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(session_router, prefix="/session", tags=["Session"])
app.include_router(stt_router, tags=["STT"])
app.include_router(tts_router, tags=["TTS"])
app.include_router(ocr_router, tags=["OCR"])
app.include_router(ws_chat_router, tags=["Chat"])


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Snap2Know API",
        "version": "0.1.0",
        "docs": "/docs"
    }
