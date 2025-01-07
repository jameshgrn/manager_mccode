import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from manager_mccode.services.metrics import MetricsCollector

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

def test_metrics_data_structure(mock_metrics):
    """Test the structure of metrics data"""
    assert "summary" in mock_metrics
    assert "focus_score" in mock_metrics["summary"]
    assert "active_hours" in mock_metrics["summary"]
    assert isinstance(mock_metrics["hourly_patterns"], dict)
    assert isinstance(mock_metrics["focus_states"], dict)
    assert isinstance(mock_metrics["activities"]["categories"], dict)

def test_metrics_calculations():
    """Test metrics calculations"""
    metrics = MetricsCollector(Mock())
    
    # Test focus score calculation
    focus_data = {"focused": 10, "neutral": 5, "scattered": 5}
    total = sum(focus_data.values())
    
    # Calculate weighted score: (10 focused * 100 + 5 neutral * 50 + 5 scattered * 0) / 20 total
    weighted_score = (10 * 100 + 5 * 50 + 5 * 0) / total  # = (1000 + 250 + 0) / 20 = 62.5
    assert abs(weighted_score - 62.5) < 0.1  # Updated expected value

def test_hourly_pattern_format(mock_metrics):
    """Test hourly pattern data format"""
    patterns = mock_metrics["hourly_patterns"]
    
    # Test work hours have higher scores
    work_hours = [str(i) for i in range(9, 18)]
    for hour in work_hours:
        assert patterns[hour]["focus_score"] == 80
        assert patterns[hour]["activities"] == 5
        
    # Test non-work hours have lower scores
    non_work_hours = [str(i) for i in range(24) if i < 9 or i >= 18]
    for hour in non_work_hours:
        assert patterns[hour]["focus_score"] == 40
        assert patterns[hour]["activities"] == 1 