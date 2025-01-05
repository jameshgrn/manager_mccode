import os
from datetime import datetime, timedelta
import pyautogui
from PIL import Image
from io import BytesIO
from manager_mccode.config.settings import TEMP_SCREENSHOTS_DIR

class ImageManager:
    def __init__(self, temp_dir: str = TEMP_SCREENSHOTS_DIR):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def save_screenshot(self) -> str:
        """Take and save a screenshot with compression"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.temp_dir, f"screenshot_{timestamp}.png")
        
        # Take screenshot and compress
        screenshot = pyautogui.screenshot()
        
        # Convert to RGB (removing alpha channel) and compress
        rgb_im = screenshot.convert('RGB')
        
        # Save with compression
        rgb_im.save(filename, 'JPEG', quality=85, optimize=True)
        
        # Verify file size and compress more if needed
        if os.path.getsize(filename) > 4_000_000:  # 4MB limit per image
            for quality in [70, 50, 30]:
                rgb_im.save(filename, 'JPEG', quality=quality, optimize=True)
                if os.path.getsize(filename) <= 4_000_000:
                    break
        
        return filename

    def cleanup_old_images(self, max_age_minutes: int = 60):
        """Remove screenshots older than max_age_minutes"""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        for filename in os.listdir(self.temp_dir):
            filepath = os.path.join(self.temp_dir, filename)
            if os.path.getctime(filepath) < cutoff.timestamp():
                os.remove(filepath) 