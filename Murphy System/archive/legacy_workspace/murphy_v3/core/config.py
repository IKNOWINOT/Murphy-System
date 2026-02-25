"""
Configuration Management for Murphy v3.0

Centralized configuration using Pydantic Settings.
Extracted from murphy_integrated and enhanced for production.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List


class Settings(BaseSettings):
    """Murphy v3.0 Configuration - All settings can be overridden via environment variables"""
    
    # Environment
    murphy_env: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # API
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_version: str = Field(default="v1", description="API version prefix")
    cors_origins: List[str] = Field(default=[], description="CORS allowed origins")
    max_request_size: int = Field(default=16*1024*1024, description="Max request size in bytes")
    
    # Database
    database_url: str = Field(default="postgresql+asyncpg://murphy:murphy@localhost:5432/murphy_v3")
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_pool_timeout: float = Field(default=30.0)
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Security
    jwt_secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration: int = Field(default=3600)
    enable_security_plane: bool = Field(default=True)
    
    # LLM
    groq_api_key: Optional[str] = None
    groq_model: str = Field(default="mixtral-8x7b-32768")
    llm_timeout: int = Field(default=30)
    
    # Murphy Validation
    murphy_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    enable_hitl: bool = Field(default=True)
    
    # Shadow Agent
    shadow_agent_enabled: bool = Field(default=True)
    shadow_agent_traffic_percent: float = Field(default=0.1)
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    
    # Business
    enable_business_automation: bool = Field(default=True)
    enable_b2b_negotiation: bool = Field(default=True)
    
    @validator('murphy_env')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError(f"Invalid environment: {v}")
        return v
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(',')] if v else []
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
