import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import mss
from PIL import Image
from manager_mccode.config.config import config

logger = logging.getLogger(__name__)

class ImageError(Exception):
    """Base exception for image-related errors"""
    pass

class ScreenshotError(ImageError):
    """Exception raised when screenshot capture fails"""
    pass

class CompressionError(ImageError):
    """Exception raised when image compression fails"""
    pass

class ImageManager:
    def __init__(self, temp_dir: Path = None):
        """Initialize the image manager"""
        try:
            self.temp_dir = temp_dir or config.temp_screenshots_dir
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self.sct = mss.mss()  # Screenshot utility
            logger.info(f"Initialized ImageManager with temp_dir: {self.temp_dir}")
        except Exception as e:
            raise ScreenshotError(f"Failed to initialize screenshot manager: {e}")

    async def capture_screenshot(self) -> str:
        """Capture and save a screenshot of all monitors"""
        try:
            # Create screenshot directory if it doesn't exist
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            filepath = self.temp_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            try:
                # Take screenshot of all monitors
                screenshots = []
                with mss.mss() as sct:  # This might raise an exception
                    for monitor in sct.monitors[1:]:  # Skip first monitor (combined view)
                        screenshot = sct.grab(monitor)
                        screenshots.append(Image.frombytes('RGB', screenshot.size, screenshot.rgb))
                        
                # Combine screenshots if multiple monitors
                if len(screenshots) > 1:
                    # Calculate total width and max height
                    total_width = sum(img.width for img in screenshots)
                    max_height = max(img.height for img in screenshots)
                    
                    # Create new image with combined dimensions
                    final_image = Image.new('RGB', (total_width, max_height))
                    
                    # Paste screenshots side by side
                    x_offset = 0
                    for img in screenshots:
                        final_image.paste(img, (x_offset, 0))
                        x_offset += img.width
                        
                    logger.info(f"Combined {len(screenshots)} monitor screenshots")
                else:
                    final_image = screenshots[0]
                    logger.info(f"Using single monitor screenshot")
                
                # Save with compression
                final_image.save(filepath, format="PNG", optimize=True)
                return str(filepath)
                
            except Exception as e:
                raise ScreenshotError(f"Failed to capture screenshot: {e}")
                
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            raise ScreenshotError(f"Screenshot capture failed: {e}")

    async def cleanup(self):
        """Clean up old screenshots"""
        try:
            current_time = datetime.now()
            retention_minutes = config.image.retention_minutes
            batch_size = config.image.cleanup_batch_size
            
            # Get list of files older than retention period
            old_files = [
                f for f in self.temp_dir.glob("*.png")
                if (current_time - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() 
                > retention_minutes * 60
            ]

            # Process in batches
            for i in range(0, len(old_files), batch_size):
                batch = old_files[i:i + batch_size]
                for file in batch:
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.error(f"Failed to delete {file}: {e}")
                await asyncio.sleep(0.1)  # Small delay between batches

            logger.info(f"Cleaned up {len(old_files)} old screenshots")

        except Exception as e:
            logger.error(f"Error during screenshot cleanup: {e}")

    def __del__(self):
        """Cleanup mss resources"""
        if hasattr(self, 'sct'):
            self.sct.close() 