import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from manager_mccode.web.app import app
from manager_mccode.services.metrics import MetricsCollector

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)

@pytest.fixture
def mock_metrics():
    """Create mock metrics data"""
    return {
        "summary": {
            "focus_score": 75.5,
            "active_hours": 6.2,
            "context_switches": 12
        },
        "hourly_patterns": {
            str(i): {
                "focus_score": 80 if 9 <= i <= 17 else 40,
                "activities": 5 if 9 <= i <= 17 else 1,
                "snapshots": 2 if 9 <= i <= 17 else 0
            } for i in range(24)
        },
        "focus_states": {
            "focused": 15,
            "neutral": 8,
            "scattered": 4
        },
        "activities": {
            "categories": {
                "development": 12,
                "communication": 8,
                "research": 5
            },
            "total_activities": 25
        }
    }

def test_dashboard_view(test_client, mock_metrics):
    """Test the main dashboard view"""
    with patch.object(MetricsCollector, 'get_daily_metrics', return_value=mock_metrics):
        response = test_client.get("/")
        assert response.status_code == 200
        assert "Activity Dashboard" in response.text
        assert "Focus Score" in response.text

def test_daily_metrics_api(test_client, mock_metrics):
    """Test the daily metrics API endpoint"""
    with patch.object(MetricsCollector, 'get_daily_metrics', return_value=mock_metrics):
        response = test_client.get("/api/metrics/daily/2024-01-01")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["focus_score"] == 75.5
        assert data["summary"]["active_hours"] == 6.2

def test_metrics_range_api(test_client, mock_metrics):
    """Test the metrics range API endpoint"""
    mock_range_data = {
        "timeframe": {
            "start": "2024-01-01T00:00:00",
            "end": "2024-01-07T00:00:00"
        },
        "daily_metrics": [mock_metrics for _ in range(7)],
        "aggregate_metrics": {
            "total_snapshots": 175,
            "active_hours": 43.4,
            "average_focus_score": 75.5
        }
    }
    
    with patch.object(MetricsCollector, 'export_timeframe', return_value=mock_range_data):
        response = test_client.get("/api/metrics/range?start=2024-01-01&end=2024-01-07")
        assert response.status_code == 200
        data = response.json()
        assert "timeframe" in data
        assert len(data["daily_metrics"]) == 7

def test_invalid_date_format(test_client):
    """Test error handling for invalid date format"""
    response = test_client.get("/api/metrics/daily/invalid-date")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]

def test_error_handling(test_client):
    """Test general error handling"""
    with patch.object(MetricsCollector, 'get_daily_metrics', side_effect=Exception("Test error")):
        response = test_client.get("/api/metrics/daily/2024-01-01")
        assert response.status_code == 500
        assert "Test error" in response.json()["detail"]

@pytest.mark.parametrize("endpoint", [
    "/api/metrics/daily/2024-01-01",
    "/api/metrics/range?start=2024-01-01&end=2024-01-07"
])
def test_metrics_endpoints_content_type(test_client, endpoint, mock_metrics):
    """Test that API endpoints return JSON"""
    with patch.object(MetricsCollector, 'get_daily_metrics', return_value=mock_metrics):
        with patch.object(MetricsCollector, 'export_timeframe', return_value={"data": mock_metrics}):
            response = test_client.get(endpoint)
            assert response.headers["content-type"] == "application/json" 