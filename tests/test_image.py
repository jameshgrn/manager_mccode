import pytest
from pathlib import Path
import mss
from manager_mccode.services.image import ImageManager, ScreenshotError, CompressionError
from unittest.mock import patch

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