import asyncio
import logging
from datetime import datetime
from pathlib import Path

from manager_mccode.config.config import config
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.services.analyzer import GeminiAnalyzer

logger = logging.getLogger(__name__)

class ManagerMcCode:
    def __init__(self):
        self.db = DatabaseManager()
        self.image_manager = ImageManager()
        self.batch_processor = BatchProcessor()
        self.analyzer = GeminiAnalyzer()
        self.running = False
        
    async def run(self):
        """Main service loop"""
        self.running = True
        error_count = 0
        last_error_time = None
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Reset error count if enough time has passed
                if last_error_time and (current_time - last_error_time).seconds > config.error_reset_interval:
                    error_count = 0
                
                # Take screenshot
                screenshot_path = await self.image_manager.capture_screenshot()
                if screenshot_path:
                    self.batch_processor.add_screenshot(screenshot_path)
                
                # Process batch if ready
                if self.batch_processor.is_batch_ready():
                    summaries = await self.batch_processor.process_batch()
                    for summary in summaries:
                        self.db.store_summary(summary)
                
                await asyncio.sleep(config.screenshot_interval)
                
            except Exception as e:
                error_count += 1
                last_error_time = current_time
                logger.error(f"Error in main loop: {e}", exc_info=True)
                
                if error_count >= config.max_errors:
                    logger.critical(f"Too many errors ({error_count}), shutting down...")
                    self.running = False
                    break
                    
                await asyncio.sleep(5)  # Brief pause after error
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.image_manager.cleanup()
            self.db.close()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

async def main():
    """Entry point for direct execution"""
    manager = ManagerMcCode()
    try:
        await manager.run()
    finally:
        await manager.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 