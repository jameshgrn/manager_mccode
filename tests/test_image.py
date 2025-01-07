import pytest
from pathlib import Path
from PIL import Image
import io
from manager_mccode.services.image import ImageManager, ScreenshotError, CompressionError
import os

def test_save_screenshot(image_manager, temp_dir):
    """Test saving a screenshot"""
    # Create a test image
    test_image = Image.new('RGB', (800, 600), color='white')
    test_image_path = temp_dir / "test.jpg"
    test_image.save(test_image_path)
    
    # Save screenshot
    screenshot_path = image_manager.save_screenshot()
    assert Path(screenshot_path).exists()
    assert Path(screenshot_path).suffix == '.jpg'

def test_image_compression(image_manager, temp_dir):
    """Test image compression"""
    # Create a large test image
    large_image = Image.new('RGB', (3840, 2160), color='white')
    test_path = temp_dir / "large.jpg"
    
    # Save with compression
    image_manager._save_with_compression(large_image, test_path)
    
    # Check file size is within limits
    size_mb = test_path.stat().st_size / (1024 * 1024)
    assert size_mb <= image_manager.max_size_mb

def test_cleanup_old_images(image_manager, temp_dir):
    """Test cleaning up old images"""
    # Create some test images
    for i in range(3):
        path = temp_dir / f"screenshot_{i}.jpg"
        Image.new('RGB', (100, 100), color='white').save(path)
    
    # Set creation time to past
    for path in temp_dir.glob("*.jpg"):
        os.utime(str(path), (0, 0))  # Set access/modify time to epoch
    
    # Clean up
    image_manager.cleanup_old_images(max_age_minutes=0)
    remaining = list(temp_dir.glob("*.jpg"))
    assert len(remaining) == 0

def test_error_handling(image_manager):
    """Test error handling"""
    with pytest.raises(ScreenshotError):
        # Force an error by passing invalid path
        image_manager._save_with_compression(None, Path("/invalid/path")) 