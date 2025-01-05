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
from manager_mccode.config.settings import SCREENSHOT_INTERVAL_SECONDS
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
        self.db_manager = DatabaseManager()
        self.image_manager = ImageManager()
        self.batch_processor = BatchProcessor()
        self.display = TerminalDisplay()
        self.running = True
        self.last_export_date = datetime.now().date()
        
        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}. Starting graceful shutdown...")
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
        logger.info("Starting Manager McCode...")
        logger.info(f"Taking screenshots every {SCREENSHOT_INTERVAL_SECONDS} seconds")
        
        error_count = 0
        MAX_ERRORS = 5
        ERROR_RESET_INTERVAL = 300  # 5 minutes
        last_error_time = None

        while self.running:
            try:
                current_time = datetime.now()

                # Reset error count if enough time has passed
                if last_error_time and (current_time - last_error_time).total_seconds() > ERROR_RESET_INTERVAL:
                    error_count = 0

                # Take screenshot
                image_path = self.image_manager.save_screenshot()
                self.batch_processor.pending_screenshots.append({
                    'path': image_path,
                    'timestamp': current_time
                })

                # Process batch if it's time
                if (current_time - self.batch_processor.last_batch_time).total_seconds() >= self.batch_processor.batch_interval:
                    summaries = await self.batch_processor.process_batch()
                    
                    # Store summaries
                    for summary in summaries:
                        self.db_manager.store_summary(summary)
                    
                    # Show recent summaries
                    recent_summaries = self.db_manager.get_recent_fifteen_min_summaries(hours=1.0)
                    self.display.show_recent_summaries(recent_summaries)
                    
                    self.batch_processor.last_batch_time = current_time

                # Export daily summary if needed
                if current_time.date() != self.last_export_date:
                    summary_file = self.db_manager.export_daily_summary(self.last_export_date)
                    if summary_file:
                        logger.info(f"Daily summary exported to: {summary_file}")
                    self.last_export_date = current_time.date()

                # Memory management: Force garbage collection periodically
                if current_time.minute % 15 == 0 and current_time.second < SCREENSHOT_INTERVAL_SECONDS:
                    import gc
                    gc.collect()

                await asyncio.sleep(SCREENSHOT_INTERVAL_SECONDS)

            except Exception as e:
                error_count += 1
                last_error_time = current_time
                logger.error(f"Error occurred: {str(e)}")
                logger.error(traceback.format_exc())
                
                if error_count >= MAX_ERRORS:
                    logger.critical(f"Too many errors ({error_count}). Shutting down...")
                    self.running = False
                else:
                    logger.warning(f"Error {error_count}/{MAX_ERRORS}. Continuing...")
                    await asyncio.sleep(5)

        await self.cleanup()
        logger.info("Manager McCode stopped")

async def main():
    check_environment()  # Check first
    manager = ManagerMcCode()  # Then create manager
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main()) 