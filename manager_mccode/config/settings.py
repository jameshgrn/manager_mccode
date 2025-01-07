from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Paths and directories
    WORKSPACE_ROOT: Path = Field(
        default=Path(__file__).parent.parent.parent,
        description="Root directory of the workspace"
    )
    TEMP_SCREENSHOTS_DIR: Path = Field(
        default=Path("temp_screenshots"),
        description="Directory for temporary screenshot storage"
    )
    DEFAULT_DB_PATH: Path = Field(
        default=Path("manager_mccode.db"),
        description="Default SQLite database path"
    )
    
    # Gemini API settings
    GEMINI_API_KEY: str = Field(
        default=...,  # Required field
        description="API key for Gemini Vision API"
    )
    GEMINI_MODEL_NAME: str = Field(
        default='gemini-1.5-flash-8b',
        description="Gemini model to use for analysis"
    )
    
    # Screenshot and batch settings
    SCREENSHOT_INTERVAL_SECONDS: int = Field(
        default=10,
        ge=5,  # Minimum 5 seconds
        le=300,  # Maximum 5 minutes
        description="Interval between screenshots"
    )
    DEFAULT_BATCH_SIZE: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Number of screenshots to process in one batch"
    )
    DEFAULT_BATCH_INTERVAL_SECONDS: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Maximum time to wait before processing a batch"
    )
    
    # Image processing settings
    MAX_IMAGE_SIZE_MB: float = Field(
        default=4.0,
        ge=1.0,
        le=10.0,
        description="Maximum size of compressed screenshots in MB"
    )
    IMAGE_COMPRESSION_QUALITY: int = Field(
        default=85,
        ge=30,
        le=100,
        description="JPEG compression quality (30-100)"
    )
    DEFAULT_IMAGE_MAX_AGE_MINUTES: int = Field(
        default=60,
        ge=5,
        le=1440,  # 24 hours
        description="How long to keep screenshots before cleanup"
    )
    
    # Error handling settings
    MAX_ERRORS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of errors before shutdown"
    )
    ERROR_RESET_INTERVAL: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Seconds after which error count resets"
    )
    
    # Database settings
    DB_RETENTION_DAYS: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days to retain data before cleanup"
    )
    
    # Multi-monitor support
    CAPTURE_ALL_MONITORS: bool = Field(
        default=True,
        description="Whether to capture all monitors or just primary"
    )
    
    @field_validator("TEMP_SCREENSHOTS_DIR", "DEFAULT_DB_PATH", mode='before')
    def validate_paths(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v
    
    @field_validator("GEMINI_API_KEY")
    def validate_api_key(cls, v):
        if not v:
            raise ValueError("GEMINI_API_KEY must be set")
        return v

settings = Settings() 