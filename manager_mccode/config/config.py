from pathlib import Path
from typing import Dict, Any
from .settings import settings

class Config:
    """Configuration manager that provides access to settings"""
    
    def __init__(self):
        self.settings = settings
        self._validate_paths()
    
    def _validate_paths(self) -> None:
        """Ensure all required paths exist"""
        required_paths = [
            self.settings.DATA_DIR,
            self.settings.TEMP_DIR,
            self.settings.LOG_DIR
        ]
        
        for path in required_paths:
            path.mkdir(parents=True, exist_ok=True)
    
    @property
    def debug(self) -> bool:
        return self.settings.DEBUG
    
    @property
    def is_production(self) -> bool:
        return self.settings.ENV.lower() == "production"
    
    @property
    def log_file(self) -> Path:
        return self.settings.LOG_DIR / "manager_mccode.log"
    
    def get_retention_policy(self) -> Dict[str, Any]:
        """Get data retention configuration"""
        return {
            "screenshots": self.settings.SCREENSHOT_RETENTION_DAYS,
            "activity_data": self.settings.DATA_RETENTION_DAYS
        }

# Global configuration instance
config = Config() 