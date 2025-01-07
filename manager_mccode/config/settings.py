from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
import os

class Settings(BaseSettings):
    """Unified configuration settings for Manager McCode"""
    
    # API Settings
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")
    GEMINI_MODEL_NAME: str = Field(
        'gemini-1.5-flash',  # Updated to latest model
        description="Gemini model to use for analysis"
    )
    
    # Service Settings
    SCREENSHOT_INTERVAL_SECONDS: int = Field(10, ge=1, description="Interval between screenshots")
    DEFAULT_BATCH_SIZE: int = Field(12, ge=1, description="Number of screenshots to process in a batch")
    DEFAULT_BATCH_INTERVAL_SECONDS: int = Field(120, ge=1, description="Interval between batch processing")
    
    # Path Settings
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path.home() / ".manager_mccode")
    DEFAULT_DB_PATH: Path = Field(default_factory=lambda: Path.home() / ".manager_mccode" / "data.db")
    TEMP_DIR: Path = Field(default_factory=lambda: Path.home() / ".manager_mccode" / "temp")
    LOG_DIR: Path = Field(default_factory=lambda: Path.home() / ".manager_mccode" / "logs")
    
    # Retention Settings
    SCREENSHOT_RETENTION_DAYS: int = Field(7, ge=1, description="Days to keep screenshots")
    DATA_RETENTION_DAYS: int = Field(90, ge=1, description="Days to keep activity data")
    
    # Security Settings
    ENCRYPT_SCREENSHOTS: bool = Field(False, description="Enable screenshot encryption")
    WEB_AUTH_REQUIRED: bool = Field(True, description="Require authentication for web interface")
    
    # Development Settings
    DEBUG: bool = Field(False, description="Enable debug mode")
    ENV: str = Field("production", description="Environment (development/production)")

    @field_validator("DATA_DIR", "TEMP_DIR", "LOG_DIR", mode="before")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Ensure required directories exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# Global settings instance
settings = Settings() 