import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = 'gemini-1.5-flash-8b'

# Database settings
DEFAULT_DB_PATH = "screen_summaries.db"

# Image settings
TEMP_SCREENSHOTS_DIR = "temp_screenshots"

# Batch processing settings
DEFAULT_BATCH_SIZE = 12
DEFAULT_BATCH_INTERVAL_SECONDS = 120
SCREENSHOT_INTERVAL_SECONDS = 10

# Cleanup settings
DEFAULT_IMAGE_MAX_AGE_MINUTES = 60 

# Error handling settings
MAX_ERRORS = 5
ERROR_RESET_INTERVAL = 300  # 5 minutes 