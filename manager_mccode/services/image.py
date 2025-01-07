import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import mss
from PIL import Image
import io

from manager_mccode.config.settings import settings
from manager_mccode.services.errors import ImageError

logger = logging.getLogger(__name__)

class ScreenshotError(ImageError):
    """Exception raised when screenshot capture fails"""
    pass

class CompressionError(ImageError):
    """Exception raised when image compression fails"""
    pass

class ImageManager:
    """Manages screenshot capture and optimization"""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        """Initialize the image manager
        
        Args:
            temp_dir: Optional directory for temporary files. Defaults to settings.TEMP_DIR
        """
        self.temp_dir = temp_dir or settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.sct = mss.mss()
        except Exception as e:
            raise ScreenshotError(f"Failed to initialize screenshot manager: {e}")
        
        # Compression settings
        self.JPEG_QUALITY = 85  # Good balance between quality and size
        self.MAX_DIMENSION = 1920  # Max width/height for screenshots
        self.COMPRESSION_FORMAT = "JPEG"  # JPEG is better for screenshots than PNG
        
    async def capture_screenshot(self) -> Path:
        """Capture and optimize a screenshot
        
        Returns:
            Path: Path to the optimized screenshot
            
        Raises:
            ScreenshotError: If screenshot capture fails
        """
        try:
            # Capture screenshot directly as bytes
            try:
                screenshot = self.sct.grab(self.sct.monitors[0])  # Primary monitor (index 0)
            except Exception as e:
                raise ScreenshotError(f"Failed to grab screenshot: {e}")
            
            # Convert to PIL Image
            try:
                img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            except Exception as e:
                raise ScreenshotError(f"Failed to convert screenshot: {e}")
            
            # Process in thread pool to avoid blocking
            return await asyncio.to_thread(self._process_image, img)
            
        except ScreenshotError:
            raise
        except Exception as e:
            raise ScreenshotError(f"Failed to capture screenshot: {e}")
    
    def _process_image(self, img: Image.Image) -> Path:
        """Process and optimize screenshot
        
        Args:
            img: PIL Image to process
            
        Returns:
            Path: Path to processed image
        """
        try:
            # Convert to RGB (remove alpha channel)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Resize if needed
            if max(img.size) > self.MAX_DIMENSION:
                ratio = self.MAX_DIMENSION / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.temp_dir / f"screenshot_{timestamp}.jpg"
            
            img.save(
                output_path,
                format=self.COMPRESSION_FORMAT,
                quality=self.JPEG_QUALITY,
                optimize=True
            )
            
            return output_path
            
        except Exception as e:
            raise CompressionError(f"Failed to process screenshot: {e}")
    
    async def cleanup_old_images(self, max_age_minutes: Optional[int] = None) -> None:
        """Clean up old screenshot files
        
        Args:
            max_age_minutes: Optional override for maximum age of files to keep
        """
        max_age = max_age_minutes or settings.SCREENSHOT_RETENTION_DAYS * 24 * 60
        cutoff_time = datetime.now() - timedelta(minutes=max_age)
        
        try:
            for file in self.temp_dir.glob("screenshot_*.jpg"):
                if file.stat().st_mtime < cutoff_time.timestamp():
                    file.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up old images: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.sct.close()
        except Exception as e:
            logger.error(f"Error closing screenshot manager: {e}") 