import pytest
from pathlib import Path
from PIL import Image
import io
from manager_mccode.services.image import ImageManager, ScreenshotError, CompressionError
import os
from datetime import datetime, timedelta
import time

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
    # Create some test images with correct naming pattern
    created_files = []
    for i in range(3):
        path = temp_dir / f"screenshot_{i}.jpg"
        Image.new('RGB', (100, 100), color='white').save(path)
        created_files.append(path)
    
    # Set creation time to past (2 hours ago to ensure it's old enough)
    two_hours_ago = datetime.now() - timedelta(hours=2)
    for path in created_files:
        os.utime(str(path), (two_hours_ago.timestamp(), two_hours_ago.timestamp()))
        assert path.exists(), f"File {path} should exist before cleanup"
    
    # Clean up with max age of 0 minutes (should remove all)
    image_manager.cleanup_old_images(max_age_minutes=0)
    
    # Wait a moment for file operations to complete
    time.sleep(0.1)
    
    # Check for remaining files using the correct pattern
    remaining = list(temp_dir.glob("screenshot_*.jpg"))
    for path in remaining:
        print(f"Found remaining file: {path}")
        creation_time = datetime.fromtimestamp(path.stat().st_ctime)
        print(f"Creation time: {creation_time}")
    
    assert len(remaining) == 0, f"Found {len(remaining)} files that should have been deleted"

def test_error_handling(image_manager):
    """Test error handling"""
    with pytest.raises(ScreenshotError):
        # Force an error by passing invalid path
        image_manager._save_with_compression(None, Path("/invalid/path")) 