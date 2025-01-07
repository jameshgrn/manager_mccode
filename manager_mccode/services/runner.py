import sys
import os
import asyncio
import logging
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

from manager_mccode.config.config import config
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.services.analyzer import GeminiAnalyzer

logger = logging.getLogger(__name__)

class ServiceRunner:
    def __init__(self):
        self.running = False
        self._setup_logging()
        self.db = DatabaseManager()
        self.image_manager = ImageManager()
        self.batch_processor = BatchProcessor()
        self.analyzer = GeminiAnalyzer()
        
    def _setup_logging(self):
        """Configure logging for background service"""
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler with full logging
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Console handler with minimal logging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only show warnings and errors
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers = []  # Remove existing handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    def _write_pid(self):
        """Write PID file"""
        config.pid_file.write_text(str(os.getpid()))
    
    def _cleanup_pid(self):
        """Remove PID file"""
        try:
            config.pid_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to remove PID file: {e}")
    
    async def start(self):
        """Start the service"""
        try:
            self._write_pid()
            self.running = True
            
            # Handle shutdown signals
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_event_loop().add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self.shutdown(s))
                )
            
            logger.info("Starting Manager McCode service...")
            
            # Wait for initial batch processing to complete
            if self.batch_processor.pending_screenshots:
                logger.info("Processing existing screenshots before starting capture...")
                await self.batch_processor.process_batch()
            
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
            
        except Exception as e:
            logger.error(f"Service failed: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self, sig: Optional[signal.Signals] = None):
        """Shutdown the service"""
        if sig:
            logger.info(f"Received signal {sig.name}, shutting down...")
        
        self.running = False
        
        try:
            await self.image_manager.cleanup()
            self.db.close()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        self._cleanup_pid()
        logger.info("Service stopped")

def run_service():
    """Entry point for running the service"""
    runner = ServiceRunner()
    asyncio.run(runner.start())

if __name__ == "__main__":
    run_service() 