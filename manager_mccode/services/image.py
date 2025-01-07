import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import mss
from PIL import Image
from manager_mccode.config.config import config

logger = logging.getLogger(__name__)

class ImageManager:
    def __init__(self, temp_dir: Path = None):
        """Initialize the image manager"""
        self.temp_dir = temp_dir or config.temp_screenshots_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.sct = mss.mss()  # Screenshot utility
        logger.info(f"Initialized ImageManager with temp_dir: {self.temp_dir}")

    async def capture_screenshot(self) -> Path:
        """Capture and save a screenshot of all monitors"""
        try:
            # Log monitor information
            logger.info(f"Available monitors: {len(self.sct.monitors)}")
            for i, m in enumerate(self.sct.monitors):
                logger.info(f"Monitor {i}: {m}")

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"screenshot_{timestamp}.png"
            filepath = self.temp_dir / filename

            # Capture all monitors (including first one this time)
            screenshots = []
            for monitor in self.sct.monitors:  # Try capturing all monitors
                if monitor == self.sct.monitors[0]:  # Skip the "all monitors" monitor
                    continue
                screenshot = self.sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                screenshots.append(img)
                logger.info(f"Captured monitor with size: {img.size}")

            # If we have multiple monitors, combine them horizontally
            if len(screenshots) > 1:
                # Calculate total width and max height
                total_width = sum(img.width for img in screenshots)
                max_height = max(img.height for img in screenshots)
                logger.info(f"Combining {len(screenshots)} monitors into image of size {total_width}x{max_height}")

                # Create new image with combined size
                combined = Image.new('RGB', (total_width, max_height))

                # Paste each screenshot side by side
                x_offset = 0
                for img in screenshots:
                    combined.paste(img, (x_offset, 0))
                    x_offset += img.width

                final_image = combined
            else:
                final_image = screenshots[0]  # Just use the single screenshot
                logger.info(f"Using single monitor screenshot of size {final_image.size}")

            # Save with compression
            final_image.save(
                filepath,
                format="PNG",
                optimize=True,
                quality=config.image.compression_quality
            )

            logger.info(f"Saved screenshot of {len(screenshots)} monitor(s) to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}", exc_info=True)
            return None

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