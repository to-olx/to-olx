"""
Application configuration module.
Loads configuration from environment variables and provides validation.
"""

from functools import lru_cache
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application Settings
    app_name: str = Field(default="DebtWise API")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # Database Configuration
    database_url: str
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Security Settings
    secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    
    # CORS Settings
    cors_origins: List[str] = Field(default_factory=list)
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    
    # Logging Configuration
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    # Analytics Settings
    analytics_enabled: bool = Field(default=True)
    analytics_batch_size: int = Field(default=100)
    analytics_flush_interval: int = Field(default=30)
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60)
    
    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v
    
    @field_validator("cors_allow_methods", "cors_allow_headers", mode="before")
    def parse_list_fields(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse list fields from string or list."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"
    
    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings instance.
    """
    return Settings()


# Create a global settings instance
settings = get_settings()