import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from manager_mccode.services.metrics import MetricsCollector
from manager_mccode.services.database import DatabaseManager

@pytest.fixture
def mock_db():
    """Create a mock database manager"""
    db = Mock(spec=DatabaseManager)
    
    # Add methods to spec
    db.__class__.get_snapshots_between = DatabaseManager.get_snapshots_between
    db.__class__.get_activities_between = DatabaseManager.get_activities_between
    db.__class__.get_focus_states_between = DatabaseManager.get_focus_states_between
    
    # Mock snapshot data
    db.get_snapshots_between.return_value = [
        {
            "id": 1,
            "timestamp": datetime(2024, 1, 1, 10, 0),
            "focus_score": 80,
            "primary_task": "development",
            "activities": ["vscode", "chrome"]
        },
        {
            "id": 2,
            "timestamp": datetime(2024, 1, 1, 10, 15),
            "focus_score": 75,
            "primary_task": "development",
            "activities": ["vscode", "terminal"]
        },
        {
            "id": 3,
            "timestamp": datetime(2024, 1, 1, 14, 0),
            "focus_score": 40,
            "primary_task": "communication",
            "activities": ["slack", "chrome"]
        }
    ]
    
    # Mock activity data
    db.get_activities_between.return_value = [
        {"category": "development", "name": "vscode"},
        {"category": "development", "name": "terminal"},
        {"category": "communication", "name": "slack"},
        {"category": "research", "name": "chrome"}
    ]
    
    # Mock focus state data
    db.get_focus_states_between.return_value = [
        {"state_type": "focused", "confidence": 0.8},
        {"state_type": "focused", "confidence": 0.9},
        {"state_type": "scattered", "confidence": 0.7}
    ]
    
    return db

@pytest.fixture
def metrics_collector(mock_db):
    """Create a MetricsCollector instance with mock db"""
    return MetricsCollector(mock_db)

def test_get_daily_metrics(metrics_collector):
    """Test getting daily metrics"""
    date = datetime(2024, 1, 1)
    metrics = metrics_collector.get_daily_metrics(date)
    
    assert "summary" in metrics
    assert "activities" in metrics
    assert "focus_states" in metrics
    assert "hourly_patterns" in metrics
    
    # Check summary
    assert metrics["summary"]["total_snapshots"] == 3
    assert metrics["summary"]["date"] == "2024-01-01"
    assert isinstance(metrics["summary"]["active_hours"], float)
    
    # Check activities
    assert metrics["activities"]["total_activities"] == 4
    assert "development" in metrics["activities"]["categories"]
    
    # Check focus states
    assert metrics["focus_states"]["focused"] == 2
    assert metrics["focus_states"]["scattered"] == 1

def test_get_daily_metrics_empty(metrics_collector, mock_db):
    """Test getting daily metrics with no data"""
    mock_db.get_snapshots_between.return_value = []
    mock_db.get_activities_between.return_value = []
    mock_db.get_focus_states_between.return_value = []
    
    metrics = metrics_collector.get_daily_metrics()
    
    assert metrics["summary"] == {}
    assert metrics["activities"]["total_activities"] == 0
    assert all(v == 0 for v in metrics["focus_states"].values())

def test_calculate_active_hours(metrics_collector):
    """Test active hours calculation"""
    snapshots = [
        {"timestamp": datetime(2024, 1, 1, 10, 0)},
        {"timestamp": datetime(2024, 1, 1, 10, 15)},  # 15 min gap
        {"timestamp": datetime(2024, 1, 1, 14, 0)}    # Long gap (ignored)
    ]
    
    hours = metrics_collector._calculate_active_hours(snapshots)
    assert hours == 0.25  # Only the 15-minute gap should count

def test_get_activity_breakdown(metrics_collector):
    """Test activity breakdown calculation"""
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)
    
    breakdown = metrics_collector._get_activity_breakdown(start, end)
    
    assert breakdown["total_activities"] == 4
    assert breakdown["categories"]["development"] == 2
    assert breakdown["categories"]["communication"] == 1
    assert breakdown["categories"]["research"] == 1

def test_get_focus_distribution(metrics_collector):
    """Test focus state distribution"""
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)
    
    distribution = metrics_collector._get_focus_distribution(start, end)
    
    assert distribution["focused"] == 2
    assert distribution["scattered"] == 1
    assert distribution["neutral"] == 0
    assert distribution["unknown"] == 0

def test_get_hourly_patterns(metrics_collector):
    """Test hourly pattern calculation"""
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)
    
    patterns = metrics_collector._get_hourly_patterns(start, end)
    
    # Check 10am data (2 snapshots)
    assert patterns[10]["snapshots"] == 2
    assert patterns[10]["focus_score"] == 77.5  # Average of 80 and 75
    assert patterns[10]["activities"] == 4  # Total activities in that hour
    
    # Check 14pm data (1 snapshot)
    assert patterns[14]["snapshots"] == 1
    assert patterns[14]["focus_score"] == 40
    assert patterns[14]["activities"] == 2

def test_get_primary_tasks(metrics_collector):
    """Test primary task distribution"""
    snapshots = [
        {"primary_task": "development"},
        {"primary_task": "development"},
        {"primary_task": "communication"}
    ]
    
    tasks = metrics_collector._get_primary_tasks(snapshots)
    
    assert tasks["development"] == 2
    assert tasks["communication"] == 1

def test_error_handling(metrics_collector, mock_db):
    """Test error handling in metrics collection"""
    mock_db.get_snapshots_between.side_effect = Exception("Database error")
    
    metrics = metrics_collector.get_daily_metrics()
    
    assert metrics["summary"] == {}
    assert "activities" in metrics
    assert "focus_states" in metrics
    assert "hourly_patterns" in metrics

def test_export_timeframe(metrics_collector):
    """Test timeframe export"""
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 7)
    
    export = metrics_collector.export_timeframe(start, end)
    
    assert "timeframe" in export
    assert export["timeframe"]["start"] == start.isoformat()
    assert export["timeframe"]["end"] == end.isoformat()
    assert "daily_metrics" in export
    assert "aggregate_metrics" in export 