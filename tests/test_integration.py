import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from manager_mccode.services.image import ImageManager
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.services.database import DatabaseManager
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators

@pytest.fixture
def test_env():
    """Set up a test environment with temporary directories"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "test.db"
        screenshots_dir = temp_path / "screenshots"
        screenshots_dir.mkdir()
        
        # Initialize services
        db = DatabaseManager(db_path)
        image_manager = ImageManager(screenshots_dir)
        
        yield {
            'db': db,
            'image_manager': image_manager,
            'temp_dir': temp_path,
            'screenshots_dir': screenshots_dir
        }

@pytest.mark.asyncio
async def test_capture_analyze_store_flow(test_env):
    """Test the full flow from screen capture to analysis to storage"""
    with patch('PIL.ImageGrab.grab') as mock_grab:
        # Mock screen capture
        mock_image = Mock()
        mock_image.save = Mock()
        mock_grab.return_value = mock_image
        
        # Capture screenshot
        screenshot_path = await test_env['image_manager'].save_screenshot()
        assert screenshot_path.exists()
        
        # Mock Gemini API response
        mock_response = {
            "summary": "Test activity",
            "activities": ["coding", "testing"]
        }
        
        with patch('google.generativeai.GenerativeModel') as mock_model:
            # Setup mock response
            mock_api_response = Mock()
            mock_api_response.text = json.dumps(mock_response)
            mock_model.return_value.generate_content.return_value = mock_api_response
            
            # Analyze screenshot
            summary = await GeminiAnalyzer.analyze_image(str(screenshot_path))
            assert isinstance(summary, ScreenSummary)
            
            # Store in database
            summary_id = test_env['db'].store_summary(summary)
            assert summary_id is not None
            
            # Verify storage
            stored = test_env['db'].get_recent_summaries(limit=1)[0]
            assert stored['summary'] == mock_response['summary']
            
            # Check cleanup
            assert not screenshot_path.exists()

@pytest.mark.asyncio
async def test_metrics_and_recommendations(test_env):
    """Test retrieving metrics and generating recommendations"""
    # Store some test data
    db = test_env['db']
    
    # Create test summaries with different focus states
    focused = ScreenSummary(
        timestamp=datetime.now(),
        summary="Focused coding session",
        activities=[
            Activity(
                name="coding",
                category="development",
                focus_indicators=FocusIndicators(
                    attention_level=90,
                    context_switches="low",
                    workspace_organization="organized"
                )
            )
        ]
    )
    
    scattered = ScreenSummary(
        timestamp=datetime.now() - timedelta(hours=1),
        summary="Scattered work session",
        activities=[
            Activity(
                name="browsing",
                category="research",
                focus_indicators=FocusIndicators(
                    attention_level=40,
                    context_switches="high",
                    workspace_organization="scattered"
                )
            )
        ]
    )
    
    # Store summaries
    db.store_summary(focused)
    db.store_summary(scattered)
    
    # Get metrics
    metrics = db.get_focus_metrics(hours=24)
    assert len(metrics) > 0
    assert 'focus_score' in metrics
    assert 'context_switches' in metrics
    
    # Test data retrieval for recommendations
    recent = db.get_recent_activity(hours=24)
    assert len(recent) >= 2
    assert any(a['focus_state'] == 'focused' for a in recent)
    assert any(a['focus_state'] == 'scattered' for a in recent)

@pytest.mark.asyncio
async def test_error_handling_flow(test_env):
    """Test error handling in the integration flow"""
    with patch('PIL.ImageGrab.grab') as mock_grab:
        # Mock screen capture failure
        mock_grab.side_effect = Exception("Screen capture failed")
        
        # Attempt capture
        with pytest.raises(Exception):
            await test_env['image_manager'].capture_screenshot()
    
    # Test database error handling
    with pytest.raises(Exception):
        test_env['db'].store_summary(None)
    
    # Test API error handling
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_model.return_value.generate_content.side_effect = Exception("API Error")
        
        # Create a test image
        test_image = test_env['screenshots_dir'] / "test.png"
        test_image.write_bytes(b'test')
        
        # Analysis should return error summary
        result = await GeminiAnalyzer.analyze_image(str(test_image))
        assert "Error" in result.summary
        assert result.activities[0].name == "Error" 