from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)

class DatabaseConfig(BaseModel):
    """Database-specific configuration"""
    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days to retain data before cleanup"
    )
    vacuum_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between database vacuum operations"
    )
    max_batch_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum number of records to process in one batch"
    )

class ImageConfig(BaseModel):
    """Image handling configuration"""
    max_size_mb: float = Field(
        default=4.0,
        ge=1.0,
        le=10.0,
        description="Maximum size of compressed screenshots in MB"
    )
    compression_quality: int = Field(
        default=85,
        ge=30,
        le=100,
        description="JPEG compression quality (30-100)"
    )
    retention_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Minutes to retain screenshots before cleanup"
    )
    cleanup_batch_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of files to process in one cleanup batch"
    )

class Config(BaseSettings):
    """Main configuration class"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database settings
    database: DatabaseConfig = DatabaseConfig()
    
    # Image settings
    image: ImageConfig = ImageConfig()
    
    # Paths
    workspace_root: Path = Field(
        default=Path(__file__).parent.parent.parent,
        description="Root directory of the workspace"
    )
    temp_screenshots_dir: Path = Field(
        default=Path("temp_screenshots"),
        description="Directory for temporary screenshot storage"
    )
    
    def initialize(self) -> None:
        """Initialize configuration and create required directories"""
        try:
            # Ensure directories exist
            self.temp_screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Configuration initialized with workspace root: {self.workspace_root}")
            logger.info(f"Using temporary screenshot directory: {self.temp_screenshots_dir}")
            
        except Exception as e:
            logger.error(f"Failed to initialize configuration: {e}")
            raise

    def get_path(self, *parts: str) -> Path:
        """Get a path relative to workspace root"""
        return self.workspace_root.joinpath(*parts)

# Global configuration instance
config = Config() 