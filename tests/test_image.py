import pytest
from pathlib import Path
import mss
from PIL import Image
from manager_mccode.services.image import ImageManager, ScreenshotError, CompressionError
from unittest.mock import patch, Mock
import asyncio
import os
from PIL import ImageDraw
from datetime import datetime

# Create a MockMSS class for testing
class MockMSS:
    def __init__(self):
        # MSS monitor list format: 
        # monitors[0] is a dict containing the union of all monitors
        # monitors[1] is the first monitor, etc.
        self.monitors = [
            {"top": 0, "left": 0, "width": 1920, "height": 1080},  # Monitor union
            {"top": 0, "left": 0, "width": 1920, "height": 1080}   # Primary monitor
        ]
    
    def grab(self, monitor):
        mock_screenshot = Mock()
        mock_screenshot.size = (monitor['width'], monitor['height'])
        
        # Create proper BGRA data (4 bytes per pixel)
        pixels = monitor['width'] * monitor['height']
        mock_screenshot.bgra = b'\xff' * (pixels * 4)  # White pixels in BGRA format
        
        return mock_screenshot
    
    def close(self):
        pass

@pytest.mark.asyncio
async def test_screenshot_capture(tmp_path):
    """Test capturing a screenshot"""
    manager = ImageManager(temp_dir=tmp_path)
    screenshot_path = await manager.capture_screenshot()
    
    assert Path(screenshot_path).exists()
    assert Path(screenshot_path).suffix == '.jpg'
    
    # Cleanup
    await manager.cleanup()

@pytest.mark.asyncio
async def test_screenshot_error(mocker):
    """Test handling screenshot capture errors"""
    # Mock mss before creating ImageManager
    mock_mss = mocker.patch('mss.mss')
    mock_mss.side_effect = Exception("Screenshot failed")  # Use Exception instead of ScreenshotError
    
    with pytest.raises(ScreenshotError) as exc_info:
        ImageManager()  # This should raise ScreenshotError
    assert "Failed to initialize screenshot manager" in str(exc_info.value)

@pytest.mark.asyncio
async def test_compression_error(tmp_path):
    """Test handling of image compression errors"""
    image_manager = ImageManager(temp_dir=tmp_path)
    
    # Mock the Image.frombytes method instead of Image.new
    with patch('PIL.Image.frombytes', side_effect=Exception("Compression failed")):
        # Attempt screenshot
        with pytest.raises(ScreenshotError) as exc_info:
            await image_manager.capture_screenshot()
        
        assert "Failed to convert screenshot" in str(exc_info.value) 

@pytest.mark.asyncio
async def test_image_compression_settings(tmp_path):
    """Test that compression settings are properly applied"""
    # Mock the entire mss module
    with patch('mss.mss', return_value=MockMSS()):
        manager = ImageManager(temp_dir=tmp_path)
        
        # Create a test image that's larger than MAX_DIMENSION
        test_img = Image.new('RGB', (3840, 2160), color='white')
        
        # Override the mock screenshot size and data
        manager.sct.grab = lambda x: Mock(
            size=test_img.size,
            bgra=b'\xff' * (test_img.width * test_img.height * 4)  # 4 bytes per pixel for BGRA
        )
        
        # Capture and process
        output_path = await manager.capture_screenshot()
        
        # Verify the output image
        with Image.open(output_path) as img:
            # Check dimensions are scaled down
            assert max(img.size) <= manager.MAX_DIMENSION
            # Check format
            assert img.format == manager.COMPRESSION_FORMAT
            # Check it's RGB
            assert img.mode == 'RGB'

@pytest.mark.asyncio
async def test_cleanup_old_images(tmp_path):
    """Test cleanup of old screenshot files"""
    manager = ImageManager(temp_dir=tmp_path)
    
    # Create some test files with different dates
    from datetime import datetime, timedelta
    import time
    
    # Create old file
    old_file = tmp_path / "screenshot_old.jpg"
    old_file.touch()
    old_time = time.time() - (60 * 60 * 24 * 2)  # 2 days old
    os.utime(old_file, (old_time, old_time))
    
    # Create new file
    new_file = tmp_path / "screenshot_new.jpg"
    new_file.touch()
    
    # Run cleanup with 1 day retention
    await manager.cleanup_old_images(max_age_minutes=24*60)
    
    # Check results
    assert not old_file.exists(), "Old file should be deleted"
    assert new_file.exists(), "New file should be kept"

@pytest.mark.asyncio
async def test_image_quality_settings(tmp_path):
    """Test that image quality settings are maintained"""
    with patch('mss.mss', return_value=MockMSS()):
        manager = ImageManager(temp_dir=tmp_path)
        
        # Create a test image with known content
        test_img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(test_img)
        draw.text((100, 100), "Quality Test", fill='white')
        
        # Override the mock screenshot with proper BGRA data
        manager.sct.grab = lambda x: Mock(
            size=test_img.size,
            bgra=b'\xff' * (test_img.width * test_img.height * 4)  # 4 bytes per pixel for BGRA
        )
        
        # Capture and process
        output_path = await manager.capture_screenshot()
        
        # Verify the output image
        with Image.open(output_path) as img:
            # Check basic properties
            assert img.format == 'JPEG'
            
            # Get file size
            file_size = output_path.stat().st_size
            
            # Should be reasonably compressed but not too small
            assert 1000 < file_size < 1000000, "File size should be reasonable"

@pytest.mark.asyncio
async def test_concurrent_captures(tmp_path, monkeypatch):
    """Test handling multiple concurrent screenshot captures"""
    # Mock datetime to ensure unique timestamps
    class MockDateTime:
        _counter = 0
        
        @classmethod
        def now(cls):
            cls._counter += 1
            return datetime(2025, 1, 7, 16, 19, 14 + cls._counter)
    
    monkeypatch.setattr('manager_mccode.services.image.datetime', MockDateTime)
    
    with patch('mss.mss', return_value=MockMSS()):
        manager = ImageManager(temp_dir=tmp_path)
        
        # Try to capture multiple screenshots concurrently
        tasks = [manager.capture_screenshot() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify each capture produced a unique file
        paths = [Path(result) for result in results]
        assert len(set(paths)) == len(paths), "Each capture should produce a unique file"
        
        # Verify all files exist
        for path in paths:
            assert path.exists(), "Screenshot file should exist"
            assert path.suffix == '.jpg', "Should be JPEG format"
        
        # Cleanup
        await manager.cleanup() 