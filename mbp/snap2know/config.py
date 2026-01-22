"""
Snap2Know Configuration Management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # Qdrant 配置
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # OpenAI 配置（用于 LLM、Embedding）
    openai_api_key: str = ""
    openai_base_url: str = ""  # 可选：自定义 API 地址
    
    # STT 配置（Whisper API，可单独配置）
    stt_api_key: str = ""      # 如未设置，使用 openai_api_key
    stt_base_url: str = ""     # 如未设置，使用官方 OpenAI API
    
    # Anthropic 配置
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""  # 可选：自定义 API 地址
    
    # 模型配置
    rag_model: str = "anthropic/claude-3.5-sonnet"  # 文档问答模型
    chat_model: str = "openai/gpt-4o-mini"       # 闲聊模型
    
    # 代理配置
    http_proxy: str = ""  # HTTP 代理，如 http://127.0.0.1:7890
    https_proxy: str = ""  # HTTPS 代理
    
    # TTS 配置
    tts_mode: str = "auto"  # auto, edge, local, cloud
    
    # OCR 配置
    ocr_primary_timeout_sec: int = 8    # Claude OCR 超时（秒）
    ocr_fallback_timeout_sec: int = 10  # GPT-4o OCR 超时（秒）
    
    # 文本切块配置
    chunk_size: int = 500      # 每块最大字符数
    chunk_overlap: int = 50    # 块间重叠字符数
    
    # Embedding 配置
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # Qdrant Collection
    qdrant_collection: str = "snap2know_chunks"
    
    # 应用配置
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
