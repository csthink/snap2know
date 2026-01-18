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
    
    # OpenAI 配置
    openai_api_key: str = ""
    
    # Anthropic 配置
    anthropic_api_key: str = ""
    
    # TTS 配置
    tts_mode: str = "auto"  # auto, edge, local, cloud
    
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
