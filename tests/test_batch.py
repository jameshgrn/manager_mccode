import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from manager_mccode.services.batch import BatchProcessor, BatchProcessingError
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_batch_processing(batch_processor, temp_dir):
    """Test processing a batch of screenshots"""
    # Mock Gemini API response
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Test", "activities": [], "context": {"primary_task": "Unknown", "attention_state": "Unknown", "environment": "Unknown"}}'
    
    with patch.object(batch_processor.model, 'generate_content', return_value=mock_response):
        # Create test screenshots
        screenshots = []
        for i in range(batch_processor.batch_size):
            path = temp_dir / f"test_{i}.jpg"
            Image.new('RGB', (800, 600), color='white').save(path)
            screenshots.append(str(path))
            batch_processor.add_screenshot(str(path))
        
        # Process batch
        assert batch_processor.is_batch_ready()
        summaries = await batch_processor.process_batch()
        
        # We should get summaries since we mocked the API
        assert len(summaries) == batch_processor.batch_size
        for summary in summaries:
            assert summary.summary == "Test"
            assert len(summary.activities) == 0
            assert summary.context.attention_state == "Unknown"

@pytest.mark.asyncio
async def test_batch_timing(batch_processor, temp_dir):
    """Test batch timing logic"""
    # Create a test file first
    test_path = temp_dir / "test.jpg"
    Image.new('RGB', (800, 600), color='white').save(test_path)
    
    # Add screenshot
    batch_processor.add_screenshot(str(test_path))
    assert not batch_processor.is_batch_ready()  # Not enough screenshots
    
    # Wait for interval
    await asyncio.sleep(batch_processor.batch_interval + 1)
    assert batch_processor.is_batch_ready()  # Ready due to time

def test_error_handling(batch_processor):
    """Test error handling in batch processor"""
    with pytest.raises(BatchProcessingError):
        batch_processor.add_screenshot("/invalid/path")  # Should raise immediately 