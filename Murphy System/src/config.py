"""
Configuration Management for Murphy System
Centralized configuration using Pydantic settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """
    Murphy System Configuration
    
    All settings can be overridden via environment variables.
    Example: API_HOST=0.0.0.0 python demo/api_server.py
    """
    
    # ============================================================================
    # API Configuration
    # ============================================================================
    
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    
    api_port: int = Field(
        default=8052,
        description="API server port"
    )
    
    api_debug: bool = Field(
        default=False,
        description="Enable Flask debug mode (DO NOT use in production)"
    )
    
    # ============================================================================
    # Database Configuration
    # ============================================================================
    
    db_path: str = Field(
        default="murphy_logs.db",
        description="Path to SQLite database file"
    )
    
    db_timeout: float = Field(
        default=30.0,
        description="Database connection timeout in seconds"
    )
    
    # ============================================================================
    # LLM Configuration
    # ============================================================================
    
    groq_key_count: int = Field(
        default=0,
        description="Number of Groq API keys (auto-detected from encrypted storage)"
    )
    
    llm_timeout: int = Field(
        default=30,
        description="LLM API call timeout in seconds"
    )
    
    llm_max_retries: int = Field(
        default=3,
        description="Maximum LLM API call retries"
    )
    
    use_key_rotation: bool = Field(
        default=True,
        description="Enable Groq API key rotation"
    )
    
    # ============================================================================
    # Safety Thresholds (MFGC-AI Core Parameters)
    # ============================================================================
    
    confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for execution"
    )
    
    murphy_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Maximum Murphy index (risk) allowed"
    )
    
    gate_satisfaction_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum gate satisfaction percentage"
    )
    
    max_unknowns: int = Field(
        default=2,
        ge=0,
        description="Maximum number of unknowns allowed"
    )
    
    # ============================================================================
    # Conversation Manager Configuration
    # ============================================================================
    
    max_messages_per_conversation: int = Field(
        default=100,
        ge=10,
        description="Maximum messages to keep per conversation"
    )
    
    max_conversation_age_hours: int = Field(
        default=24,
        ge=1,
        description="Maximum age of conversations before cleanup (hours)"
    )
    
    conversation_cleanup_interval: int = Field(
        default=3600,
        ge=60,
        description="Conversation cleanup interval (seconds)"
    )
    
    # ============================================================================
    # Caching Configuration
    # ============================================================================
    
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for caching (e.g., redis://localhost:6379)"
    )
    
    cache_ttl: int = Field(
        default=3600,
        ge=60,
        description="Cache TTL in seconds"
    )
    
    enable_caching: bool = Field(
        default=False,
        description="Enable response caching"
    )
    
    # ============================================================================
    # Rate Limiting Configuration
    # ============================================================================
    
    rate_limit_storage: str = Field(
        default="memory://",
        description="Rate limit storage backend (memory:// or redis://...)"
    )
    
    rate_limit_chat: str = Field(
        default="10 per minute",
        description="Rate limit for chat endpoint"
    )
    
    rate_limit_governance: str = Field(
        default="20 per minute",
        description="Rate limit for governance endpoints"
    )
    
    rate_limit_monitoring: str = Field(
        default="100 per minute",
        description="Rate limit for monitoring endpoints"
    )
    
    rate_limit_global: str = Field(
        default="200 per hour",
        description="Global rate limit"
    )
    
    # ============================================================================
    # Logging Configuration
    # ============================================================================
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    log_file: str = Field(
        default="murphy_system.log",
        description="Log file path"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    
    log_max_bytes: int = Field(
        default=10485760,  # 10MB
        description="Maximum log file size before rotation"
    )
    
    log_backup_count: int = Field(
        default=5,
        description="Number of log file backups to keep"
    )
    
    # ============================================================================
    # Security Configuration
    # ============================================================================
    
    murphy_master_key: Optional[str] = Field(
        default=None,
        description=(
            "Master encryption key for API keys. "
            "WARNING: Never commit this value to source control or store in plaintext .env files in production. "
            "Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.) for production deployments."
        )
    )
    
    encrypted_keys_path: str = Field(
        default="encrypted_keys.json",
        description="Path to encrypted API keys file"
    )
    
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080,http://localhost:6666",
        description="CORS allowed origins (comma-separated). Do NOT use '*' in production."
    )
    
    # ============================================================================
    # Environment Configuration
    # ============================================================================
    
    murphy_env: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create the global settings instance.
    
    Returns:
        Settings: Global settings instance
    """
    global _settings_instance
    
    if _settings_instance is None:
        _settings_instance = Settings()
    
    return _settings_instance


def reload_settings():
    """Reload settings from environment/file"""
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance


# Convenience access
settings = get_settings()