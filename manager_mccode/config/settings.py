from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # API Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"
    
    # Service Configuration
    SCREENSHOT_INTERVAL_SECONDS: int = 10
    DEFAULT_BATCH_SIZE: int = 12
    DEFAULT_BATCH_INTERVAL_SECONDS: int = 120
    CLEANUP_INTERVAL_MINUTES: int = 60  # Run cleanup hourly instead of every 10 seconds
    
    # Path Configuration
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    TEMP_DIR: Path = BASE_DIR / "temp_screenshots"
    LOG_DIR: Path = BASE_DIR / "logs"
    DEFAULT_DB_PATH: Path = BASE_DIR / "manager_mccode.db"
    
    # Web Configuration
    WEB_PORT: int = 8000
    WEB_HOST: str = "localhost"
    WEB_AUTH_REQUIRED: bool = True
    
    # Retention Configuration
    SCREENSHOT_RETENTION_DAYS: int = 7
    DATA_RETENTION_DAYS: int = 90
    
    # Security Configuration
    ENCRYPT_SCREENSHOTS: bool = False
    
    # Development Configuration
    DEBUG: bool = False
    ENV: str = "production"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    def validate_paths(self) -> None:
        """Ensure all required paths exist"""
        for path in [self.DATA_DIR, self.TEMP_DIR, self.LOG_DIR]:
            path.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.validate_paths() 