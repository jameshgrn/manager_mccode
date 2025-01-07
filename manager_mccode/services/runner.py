import sys
import os
import asyncio
import logging
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

from manager_mccode.config.settings import settings
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.services.analyzer import GeminiAnalyzer

logger = logging.getLogger(__name__)

class ServiceRunner:
    """Main service runner with graceful shutdown handling"""
    
    def __init__(self):
        self.running = False
        self.shutdown_event = asyncio.Event()
        self._setup_logging()
        
        # Initialize core services
        self.db = DatabaseManager()
        self.image_manager = ImageManager()
        self.batch_processor = BatchProcessor()
        self.analyzer = GeminiAnalyzer()
        
        # Track service state
        self.last_screenshot_time: Optional[datetime] = None
        self.last_batch_time: Optional[datetime] = None
        self.last_cleanup_time: Optional[datetime] = None
        self.error_count = 0
        
        # Constants
        self.MAX_ERRORS = 3
        self.CLEANUP_INTERVAL_HOURS = 24
        
    def _setup_logging(self):
        """Configure logging for background service"""
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(settings.LOG_DIR / "manager_mccode.log")
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    def _setup_signal_handlers(self):
        """Set up handlers for system signals"""
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self.shutdown(sig))
            )
    
    async def shutdown(self, sig: Optional[signal.Signals] = None):
        """Gracefully shutdown the service"""
        if sig:
            logger.info(f"Received exit signal {sig.name}...")
        
        logger.info("Initiating graceful shutdown...")
        self.running = False
        self.shutdown_event.set()
        
        # Wait for batch processing to complete
        if self.batch_processor.is_processing:
            logger.info("Waiting for batch processing to complete...")
            await self.batch_processor.wait_until_done()
        
        # Cleanup resources
        try:
            await self.cleanup()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def cleanup(self):
        """Cleanup service resources"""
        tasks = []
        
        # Cleanup image manager
        if self.image_manager:
            tasks.append(self.image_manager.cleanup())
        
        # Close database connections
        if self.db:
            tasks.append(asyncio.to_thread(self.db.close))
        
        # Wait for all cleanup tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def run(self):
        """Run the service"""
        logger.info("Starting Manager McCode service...")
        self._setup_signal_handlers()
        self.running = True
        
        try:
            while self.running:
                try:
                    # Take screenshot
                    screenshot_path = await self.image_manager.capture_screenshot()
                    self.last_screenshot_time = datetime.now()
                    
                    # Add to batch processor
                    self.batch_processor.add_screenshot(screenshot_path)
                    
                    # Process batch if ready
                    if self.batch_processor.is_batch_ready():
                        summaries = await self.batch_processor.process_batch()
                        if summaries:
                            await asyncio.to_thread(self.db.store_summaries, summaries)
                    
                    # Periodic cleanup
                    await self._maybe_cleanup()
                    
                    # Reset error count on successful iteration
                    self.error_count = 0
                    
                    # Wait for next interval or shutdown
                    try:
                        await asyncio.wait_for(
                            self.shutdown_event.wait(),
                            timeout=settings.SCREENSHOT_INTERVAL_SECONDS
                        )
                        if self.shutdown_event.is_set():
                            break
                    except asyncio.TimeoutError:
                        continue
                        
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    
                    if self.error_count >= self.MAX_ERRORS:
                        logger.critical(f"Too many errors ({self.error_count}), initiating shutdown...")
                        await self.shutdown()
                        break
                    
                    # Brief pause before retry
                    await asyncio.sleep(1)
            
        finally:
            if self.running:  # If we didn't already shutdown
                await self.shutdown()
    
    async def _maybe_cleanup(self):
        """Perform periodic cleanup if needed"""
        now = datetime.now()
        if (not self.last_cleanup_time or 
            (now - self.last_cleanup_time).total_seconds() > self.CLEANUP_INTERVAL_HOURS * 3600):
            
            logger.info("Running periodic cleanup...")
            await self.image_manager.cleanup_old_images()
            await asyncio.to_thread(self.db.cleanup_old_data)
            self.last_cleanup_time = now

# Global service runner instance
service_runner = ServiceRunner()

def run_service():
    """Entry point for running the service"""
    runner = ServiceRunner()
    asyncio.run(runner.run())

if __name__ == "__main__":
    run_service() 