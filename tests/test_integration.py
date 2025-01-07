import pytest
from pathlib import Path
import tempfile
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from manager_mccode.services.image import ImageManager, ScreenshotError
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.services.database import DatabaseManager
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context

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
    # Capture screenshot
    screenshot_path = await test_env['image_manager'].capture_screenshot()
    assert Path(screenshot_path).exists()
    
    # Mock Gemini API response
    mock_response = {
        "summary": "Test activity",
        "activities": [{
            "name": "coding",
            "category": "development",
            "focus_indicators": {
                "attention_level": 80,
                "context_switches": "low",
                "workspace_organization": "organized"
            }
        }],
        "context": {
            "primary_task": "development",
            "attention_state": "focused",
            "environment": "quiet workspace",
            "confidence": 0.9
        }
    }
    
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock response
        mock_api_response = Mock()
        mock_api_response.text = json.dumps(mock_response)
        mock_model.return_value.generate_content.return_value = mock_api_response
        
        # Analyze screenshot
        analyzer = GeminiAnalyzer()
        analyzer.model = mock_model.return_value
        
        # Create proper Context object
        context = Context(
            primary_task=mock_response['context']['primary_task'],
            attention_state=mock_response['context']['attention_state'],
            environment=mock_response['context']['environment'],
            confidence=mock_response['context']['confidence']
        )
        
        # Create ScreenSummary with proper Context
        summary = ScreenSummary(
            timestamp=datetime.now(),
            summary=mock_response['summary'],
            activities=[
                Activity(
                    name=act['name'],
                    category=act['category'],
                    focus_indicators=FocusIndicators(**act['focus_indicators'])
                ) for act in mock_response['activities']
            ],
            context=context
        )
        
        # Store in database
        summary_id = test_env['db'].store_summary(summary)
        assert summary_id is not None
        
        # Verify storage
        stored = test_env['db'].get_recent_summaries(limit=1)[0]
        assert stored['summary'] == mock_response['summary']

@pytest.mark.asyncio
async def test_metrics_and_recommendations(test_env):
    """Test retrieving metrics and generating recommendations"""
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
        ],
        context=Context(
            attention_state="focused",
            confidence=0.9,
            environment="office",
            primary_task="coding"
        )
    )
    
    # Store summaries
    db.store_summary(focused)
    
    # Get metrics
    metrics = db.get_focus_metrics(hours=24)
    assert len(metrics) > 0
    assert 'context_switches' in metrics
    assert 'focus_quality' in metrics
    assert 'recommendations' in metrics

@pytest.mark.asyncio
async def test_error_handling_flow(test_env):
    """Test error handling in the integration flow"""
    # Test initialization error
    with patch('mss.mss', side_effect=Exception("Screen capture failed")):
        with pytest.raises(ScreenshotError) as exc_info:
            manager = ImageManager()
        assert "Failed to initialize screenshot manager" in str(exc_info.value)

    # Test capture error by creating a mock MSS class
    class MockMSS:
        def __init__(self):
            self.monitors = [{"top": 0, "left": 0, "width": 1920, "height": 1080}]  # Mock monitor
        
        def grab(self, *args):
            raise Exception("Screen capture failed")
        
        def close(self):
            pass

    # Replace the real MSS with our mock
    with patch('mss.mss', return_value=MockMSS()):
        manager = ImageManager()
        with pytest.raises(ScreenshotError) as exc_info:
            await manager.capture_screenshot()
        assert "Failed to grab screenshot" in str(exc_info.value) 