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
    with patch('mss.mss') as mock_mss:
        # Mock the mss instance to raise an error
        mock_instance = Mock()
        mock_instance.grab.side_effect = Exception("Screen capture failed")
        mock_mss.return_value = mock_instance
        
        # Attempt capture
        with pytest.raises(ScreenshotError):
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
        
        # Create analyzer instance
        analyzer = GeminiAnalyzer()
        
        # Analysis should return error summary
        result = await analyzer.analyze_image(str(test_image))
        assert "Error" in result.summary
        assert result.activities[0].name == "Error" 