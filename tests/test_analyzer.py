import pytest
from unittest.mock import patch, Mock
import json
from pathlib import Path
from datetime import datetime
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.models.screen_summary import ScreenSummary

@pytest.fixture
def mock_image_path(tmp_path):
    """Create a temporary test image"""
    image_path = tmp_path / "test_screenshot.png"
    # Create a small test PNG file
    image_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\x99c\xf8\x0f\x04\x00\x09\xfb\x03\xfd\x08\x99\x8f\xb6\x00\x00\x00\x00IEND\xaeB`\x82')
    return str(image_path)

@pytest.fixture
def mock_gemini_response():
    """Mock successful Gemini API response"""
    return {
        "summary": "Test summary of screen activity",
        "activities": ["coding", "browsing documentation"]
    }

@pytest.mark.asyncio
async def test_successful_analysis(mock_image_path, mock_gemini_response):
    """Test successful image analysis"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock response
        mock_response = Mock()
        mock_response.text = json.dumps(mock_gemini_response)
        mock_model.return_value.generate_content.return_value = mock_response

        # Run analysis
        result = await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify results
        assert isinstance(result, ScreenSummary)
        assert result.summary == mock_gemini_response["summary"]
        assert result.key_activities == mock_gemini_response["activities"]
        assert isinstance(result.timestamp, datetime)

@pytest.mark.asyncio
async def test_malformed_json_response(mock_image_path):
    """Test handling of malformed JSON response"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock response with invalid JSON
        mock_response = Mock()
        mock_response.text = "Invalid JSON response"
        mock_model.return_value.generate_content.return_value = mock_response

        # Run analysis
        result = await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Invalid JSON response..." in result.summary
        assert result.key_activities == ["Unknown"]

@pytest.mark.asyncio
async def test_empty_response(mock_image_path):
    """Test handling of empty API response"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock empty response
        mock_response = Mock()
        mock_response.text = ""
        mock_model.return_value.generate_content.return_value = mock_response

        # Run analysis
        result = await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Error analyzing screenshot" in result.summary
        assert result.key_activities == ["Error"]

@pytest.mark.asyncio
async def test_api_error(mock_image_path):
    """Test handling of API errors"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock API error
        mock_model.return_value.generate_content.side_effect = Exception("API Error")

        # Run analysis
        result = await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify error handling
        assert isinstance(result, ScreenSummary)
        assert "Error analyzing screenshot: API Error" in result.summary
        assert result.key_activities == ["Error"]

@pytest.mark.asyncio
async def test_markdown_cleanup(mock_image_path):
    """Test cleanup of markdown formatting in response"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup mock response with markdown
        mock_response = Mock()
        mock_response.text = """```json
        {
            "summary": "Test summary",
            "activities": ["coding"]
        }
        ```"""
        mock_model.return_value.generate_content.return_value = mock_response

        # Run analysis
        result = await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify cleanup
        assert isinstance(result, ScreenSummary)
        assert result.summary == "Test summary"
        assert result.key_activities == ["coding"]

@pytest.mark.asyncio
async def test_image_cleanup(mock_image_path):
    """Test that image file is cleaned up after analysis"""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        # Setup basic successful response
        mock_response = Mock()
        mock_response.text = json.dumps({
            "summary": "Test",
            "activities": ["test"]
        })
        mock_model.return_value.generate_content.return_value = mock_response

        # Run analysis
        await GeminiAnalyzer.analyze_image(mock_image_path)

        # Verify image cleanup
        assert not Path(mock_image_path).exists() 