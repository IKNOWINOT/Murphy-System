"""
Configuration Management for Murphy System
Centralized configuration using Pydantic settings
"""

import logging
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
        default="127.0.0.1",
        description="API server host (use 0.0.0.0 to expose on all interfaces)"
    )

    api_port: int = Field(
        default=8000,
        description="API server port"
    )

    api_debug: bool = Field(
        default=False,
        description="Enable debug mode (DO NOT use in production)"
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

    deepinfra_key_count: int = Field(
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
        default="http://localhost:3000,http://localhost:8080,http://localhost:8000",
        description="CORS allowed origins (comma-separated). Do NOT use '*' in production."
    )

    # ============================================================================
    # Test Mode Configuration
    # ============================================================================

    test_mode_enabled: bool = Field(
        default=False,
        description="Enable test mode — uses disposable test API keys with call/time limits"
    )

    test_mode_max_calls: int = Field(
        default=50,
        ge=1,
        description="Maximum API calls allowed in a test session"
    )

    test_mode_max_seconds: int = Field(
        default=300,
        ge=1,
        description="Maximum duration of a test session in seconds (default 5 minutes)"
    )

    test_mode_api_keys: str = Field(
        default="",
        description=(
            "Comma-separated disposable test API keys. "
            "These are visible in config since they are short-lived throwaway keys."
        )
    )

    # ============================================================================
    # Self-Learning Toggle
    # ============================================================================

    self_learning_enabled: bool = Field(
        default=False,
        description=(
            "Master toggle for all self-learning subsystems. "
            "When False, no training data is collected or stored to disk."
        )
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
        extra="ignore",
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
