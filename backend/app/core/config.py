from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4"
    llm_timeout: int = 30
    
    data_dir: str = "../data"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
