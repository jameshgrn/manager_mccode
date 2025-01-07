import asyncio
import traceback
import signal
import logging
from datetime import datetime
from pathlib import Path
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.services.display import TerminalDisplay
from manager_mccode.config.settings import (
    SCREENSHOT_INTERVAL_SECONDS,
    MAX_ERRORS,
    ERROR_RESET_INTERVAL
)
import sys
import platform

# Set up logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "manager_mccode.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if the environment meets requirements"""
    if sys.version_info < (3, 10):
        print("Python 3.10 or higher is required")
        sys.exit(1)
    
    if platform.system() not in ['Darwin', 'Linux', 'Windows']:
        print(f"Unsupported operating system: {platform.system()}")
        sys.exit(1)

class ManagerMcCode:
    def __init__(self):
        logger.info("Initializing ManagerMcCode...")
        self.db_manager = DatabaseManager()
        self.image_manager = ImageManager()
        self.batch_processor = BatchProcessor()
        self.display = TerminalDisplay()
        self.running = True
        self.last_export_date = datetime.now().date()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        logger.info("ManagerMcCode initialized successfully")

    def shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal. Cleaning up resources...")
        self.running = False

    async def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Cleaning up resources...")
            if self.batch_processor.pending_screenshots:
                summaries = await self.batch_processor.process_batch()
                for summary in summaries:
                    self.db_manager.store_summary(summary)
            self.image_manager.cleanup_old_images(max_age_minutes=0)
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def run(self):
        """Main run loop"""
        error_count = 0
        last_error_time = None
        logger.info("Starting main run loop...")
        
        try:
            while self.running:
                current_time = datetime.now()
                try:
                    # Reset error count if enough time has passed
                    if last_error_time and (current_time - last_error_time).total_seconds() > ERROR_RESET_INTERVAL:
                        error_count = 0

                    logger.debug(f"Taking screenshot at {current_time}")
                    screenshot_path = self.image_manager.save_screenshot()
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Add to batch processor
                    self.batch_processor.add_screenshot(screenshot_path)
                    logger.debug(f"Current batch size: {len(self.batch_processor.pending_screenshots)}")
                    
                    # Process batch if ready
                    if self.batch_processor.is_batch_ready():
                        logger.info("Processing batch...")
                        summaries = await self.batch_processor.process_batch()
                        for summary in summaries:
                            self.db_manager.store_summary(summary)
                        logger.info(f"Processed {len(summaries)} summaries")

                    await asyncio.sleep(SCREENSHOT_INTERVAL_SECONDS)

                except Exception as e:
                    error_count += 1
                    last_error_time = current_time
                    logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                    
                    if error_count >= MAX_ERRORS:
                        logger.critical(f"Too many errors ({error_count}). Shutting down...")
                        self.running = False
                    else:
                        logger.warning(f"Error {error_count}/{MAX_ERRORS}. Continuing...")
                        await asyncio.sleep(5)
        finally:
            await self.cleanup()
            logger.info("ManagerMcCode stopped")

async def main():
    check_environment()  # Check first
    manager = ManagerMcCode()  # Then create manager
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main()) 