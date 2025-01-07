import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from manager_mccode.services.batch import BatchProcessor, BatchProcessingError

@pytest.mark.asyncio
async def test_batch_processing(batch_processor, temp_dir):
    """Test processing a batch of screenshots"""
    # Create test screenshots
    screenshots = []
    for i in range(batch_processor.batch_size):  # Use batch_size from processor
        path = temp_dir / f"test_{i}.jpg"
        Image.new('RGB', (800, 600), color='white').save(path)
        screenshots.append(str(path))
        batch_processor.add_screenshot(str(path))
    
    # Process batch
    assert batch_processor.is_batch_ready()
    summaries = await batch_processor.process_batch()
    
    assert len(summaries) > 0
    for summary in summaries:
        assert summary.timestamp is not None
        assert summary.summary is not None
        assert len(summary.activities) > 0

@pytest.mark.asyncio
async def test_batch_timing(batch_processor):
    """Test batch timing logic"""
    # Add one screenshot
    batch_processor.add_screenshot("test.jpg")
    assert not batch_processor.is_batch_ready()  # Not enough screenshots
    
    # Wait for interval
    await asyncio.sleep(batch_processor.batch_interval + 1)
    assert batch_processor.is_batch_ready()  # Ready due to time

def test_error_handling(batch_processor):
    """Test error handling in batch processor"""
    with pytest.raises(BatchProcessingError):
        batch_processor.add_screenshot("/invalid/path")  # Should raise immediately 