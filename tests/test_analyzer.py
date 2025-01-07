import pytest
from unittest.mock import patch, Mock
import json
from pathlib import Path
from datetime import datetime
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.models.screen_summary import ScreenSummary
import asyncio

@pytest.fixture
def mock_image_path(tmp_path):
    """Create a temporary test image"""
    image_path = tmp_path / "test_screenshot.png"
    # Create a small test PNG file
    image_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\x99c\xf8\x0f\x04\x00\x09\xfb\x03\xfd\x08\x99\x8f\xb6\x00\x00\x00\x00IEND\xaeB`\x82')
    return str(image_path)

@pytest.fixture
def mock_successful_response():
    """Mock successful API response with all required fields"""
    return {
        "summary": "Test summary of screen activity",
        "activities": [{
            "name": "coding",
            "category": "coding",
            "purpose": "development",
            "focus_indicators": {
                "attention_level": 80,
                "context_switches": "low",
                "workspace_organization": "organized"
            }
        }],
        "context": {
            "primary_task": "development",
            "attention_state": "focused",
            "environment": "quiet workspace"
        }
    }

@pytest.mark.asyncio
async def test_successful_analysis(mock_image_path, mock_successful_response):
    """Test successful image analysis"""
    analyzer = GeminiAnalyzer()
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_response = Mock()
        mock_response.text = json.dumps(mock_successful_response)
        mock_model.return_value.generate_content.return_value = mock_response
        analyzer.model = mock_model.return_value

        result = await analyzer.analyze_image(mock_image_path)

        assert isinstance(result, ScreenSummary)
        assert result.summary == mock_successful_response["summary"]
        assert len(result.activities) == len(mock_successful_response["activities"])

@pytest.mark.asyncio
async def test_malformed_json_response(mock_image_path):
    """Test handling of malformed JSON response"""
    analyzer = GeminiAnalyzer()
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock response with invalid JSON
        mock_response = Mock()
        mock_response.text = "Invalid JSON response"
        mock_model.return_value.generate_content.return_value = mock_response
        analyzer.model = mock_model.return_value

        # Run analysis
        result = await analyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Error analyzing screenshot: Failed to parse JSON response" in result.summary
        assert [activity.name for activity in result.activities] == ["Error"]

@pytest.mark.asyncio
async def test_empty_response(mock_image_path):
    """Test handling of empty API response"""
    analyzer = GeminiAnalyzer()  # Create instance
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock empty response
        mock_response = Mock()
        mock_response.text = ""
        mock_model.return_value.generate_content.return_value = mock_response
        analyzer.model = mock_model.return_value  # Set the mock model

        # Run analysis
        result = await analyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Error analyzing screenshot" in result.summary
        assert [activity.name for activity in result.activities] == ["Error"]

@pytest.mark.asyncio
async def test_api_error(mock_image_path):
    """Test handling of API errors"""
    analyzer = GeminiAnalyzer()  # Create instance
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock API error
        mock_model.return_value.generate_content.side_effect = Exception("API Error")
        analyzer.model = mock_model.return_value  # Set the mock model

        # Run analysis
        result = await analyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Error analyzing screenshot: API Error" in result.summary
        assert [activity.name for activity in result.activities] == ["Error"]

@pytest.mark.asyncio
async def test_markdown_cleanup(mock_image_path, mock_successful_response):
    """Test cleanup of markdown formatting in response"""
    analyzer = GeminiAnalyzer()
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_response = Mock()
        mock_response.text = f"```json\n{json.dumps(mock_successful_response)}\n```"
        mock_model.return_value.generate_content.return_value = mock_response
        analyzer.model = mock_model.return_value

        result = await analyzer.analyze_image(mock_image_path)

        assert isinstance(result, ScreenSummary)
        assert result.summary == mock_successful_response["summary"]

@pytest.mark.asyncio
async def test_image_cleanup(mock_image_path, mock_successful_response):
    """Test that image file is cleaned up after analysis"""
    analyzer = GeminiAnalyzer()
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Use the mock_successful_response fixture that has all required fields
        mock_response = Mock()
        mock_response.text = json.dumps(mock_successful_response)
        mock_model.return_value.generate_content.return_value = mock_response
        analyzer.model = mock_model.return_value

        # Run analysis
        await analyzer.analyze_image(mock_image_path)

        # Give a small delay for file cleanup
        await asyncio.sleep(0.1)

        # Verify image cleanup
        assert not Path(mock_image_path).exists() 