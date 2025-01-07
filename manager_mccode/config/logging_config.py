import logging
import os
from pathlib import Path

def setup_logging():
    """Configure logging for the application"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "manager_mccode.log"),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Test logging
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized") 