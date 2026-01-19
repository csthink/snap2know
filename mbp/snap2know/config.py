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
    openai_base_url: str = ""  # 可选：自定义 API 地址
    
    # Anthropic 配置
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""  # 可选：自定义 API 地址
    
    # 代理配置
    http_proxy: str = ""  # HTTP 代理，如 http://127.0.0.1:7890
    https_proxy: str = ""  # HTTPS 代理
    
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
