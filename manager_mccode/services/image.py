import os
from datetime import datetime, timedelta
import pyautogui
from PIL import Image
import mss
import mss.tools
import logging
from pathlib import Path
from typing import List, Optional
from manager_mccode.config.settings import settings

logger = logging.getLogger(__name__)

class ScreenshotError(Exception):
    """Base exception for screenshot-related errors"""
    pass

class CompressionError(ScreenshotError):
    """Raised when image compression fails"""
    pass

class ImageManager:
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or settings.TEMP_SCREENSHOTS_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.mss = mss.mss()
        self.max_size_mb = settings.MAX_IMAGE_SIZE_MB
        logger.info(f"Initialized ImageManager with temp_dir: {self.temp_dir}")

    def save_screenshot(self) -> str:
        """Take and save a screenshot with compression
        
        Returns:
            str: Path to the saved screenshot
            
        Raises:
            ScreenshotError: If screenshot capture fails
            CompressionError: If image compression fails
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.temp_dir / f"screenshot_{timestamp}.jpg"
            
            # Capture screenshot(s)
            if settings.CAPTURE_ALL_MONITORS:
                # Capture all monitors
                screenshots = []
                for monitor in self.mss.monitors[1:]:  # Skip first as it's a duplicate
                    screenshot = self.mss.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                    screenshots.append(img)
                
                # Combine horizontally if multiple monitors
                if len(screenshots) > 1:
                    total_width = sum(img.width for img in screenshots)
                    max_height = max(img.height for img in screenshots)
                    combined = Image.new('RGB', (total_width, max_height))
                    x_offset = 0
                    for img in screenshots:
                        combined.paste(img, (x_offset, 0))
                        x_offset += img.width
                    screenshot = combined
                else:
                    screenshot = screenshots[0]
            else:
                # Capture primary monitor only
                monitor = self.mss.monitors[1]  # Primary monitor
                screenshot = self.mss.grab(monitor)
                screenshot = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
            
            # Compress with quality adjustment
            self._save_with_compression(screenshot, filename)
            logger.debug(f"Screenshot saved to {filename}")
            
            return str(filename)
            
        except mss.exception.ScreenShotError as e:
            raise ScreenshotError(f"Failed to capture screenshot: {e}")
        except Exception as e:
            raise ScreenshotError(f"Unexpected error during screenshot: {e}")

    def _save_with_compression(self, image: Image.Image, filepath: Path) -> None:
        """Save image with adaptive compression to meet size limits
        
        Args:
            image: PIL Image to save
            filepath: Target path for saved image
            
        Raises:
            CompressionError: If compression fails or can't meet size limit
        """
        try:
            # Start with default quality
            quality = settings.IMAGE_COMPRESSION_QUALITY
            max_size = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
            
            # First attempt with default quality
            image.save(filepath, 'JPEG', quality=quality, optimize=True)
            
            # Check size and compress more if needed
            size = filepath.stat().st_size
            if size > max_size:
                # Try progressively lower qualities
                for quality in [70, 50, 30]:
                    image.save(filepath, 'JPEG', quality=quality, optimize=True)
                    size = filepath.stat().st_size
                    if size <= max_size:
                        break
                
                if size > max_size:
                    raise CompressionError(
                        f"Could not compress image below {settings.MAX_IMAGE_SIZE_MB}MB "
                        f"(final size: {size/1024/1024:.1f}MB)"
                    )
            
            logger.debug(f"Saved image with quality {quality}, size: {size/1024/1024:.1f}MB")
            
        except Exception as e:
            if filepath.exists():
                filepath.unlink()  # Clean up failed file
            raise CompressionError(f"Failed to compress and save image: {e}")

    def cleanup_old_images(self, max_age_minutes: Optional[int] = None) -> None:
        """Remove screenshots older than max_age_minutes"""
        max_age = max_age_minutes or settings.DEFAULT_IMAGE_MAX_AGE_MINUTES
        cutoff = datetime.now() - timedelta(minutes=max_age)
        
        try:
            count = 0
            for filepath in self.temp_dir.glob("screenshot_*.jpg"):
                # Use creation time for comparison
                creation_time = datetime.fromtimestamp(filepath.stat().st_ctime)
                if creation_time < cutoff:
                    try:
                        filepath.unlink()
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {filepath}: {e}")
            
            if count > 0:
                logger.info(f"Cleaned up {count} old screenshots")
                
        except Exception as e:
            logger.error(f"Error during image cleanup: {e}")

    def __del__(self):
        """Cleanup MSS resources"""
        if hasattr(self, 'mss'):
            self.mss.close() 