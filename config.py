import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from typing import Optional

# 显式加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")


class Settings(BaseSettings):
    """系統配置類別"""
    
    # Gemini API
    gemini_api_key: Optional[str] = Field(default="demo_key", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", env="GEMINI_MODEL")
    
    # NanoBanana API
    nanobanana_api_key: Optional[str] = Field(None, env="NANOBANANA_API_KEY")
    nanobanana_endpoint: str = Field(default="https://api.nanobanana.com", env="NANOBANANA_ENDPOINT")
    
    # Veo3.1 API (使用 Google GenAI)
    veo_api_key: Optional[str] = Field(None, env="VEO_API_KEY")
    
    # Wan2.2 / Kling AI
    wan2_api_key: Optional[str] = Field(None, env="WAN2_API_KEY")
    wan2_endpoint: str = Field(default="https://api.wan2.com", env="WAN2_ENDPOINT")
    kling_api_key: Optional[str] = Field(None, env="KLING_API_KEY")
    kling_endpoint: str = Field(default="https://api.klingai.com", env="KLING_ENDPOINT")
    
    # System Settings
    max_retry_attempts: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    timeout_seconds: int = Field(default=30, env="TIMEOUT_SECONDS")
    ctx_window: int = Field(default=8192, env="CTX_WINDOW")
    enable_memory: bool = Field(default=True, env="ENABLE_MEMORY")
    default_temperature: float = Field(default=0.7, env="DEFAULT_TEMPERATURE")
    
    @model_validator(mode='after')
    def set_veo_key_from_gemini(self) -> 'Settings':
        if not self.veo_api_key and self.gemini_api_key:
            print("VEO API key is not set, using GEMINI API key as fallback.")
            self.veo_api_key = self.gemini_api_key
        return self

    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置實例
settings = Settings()

