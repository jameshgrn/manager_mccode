import pytest
from datetime import datetime, timedelta
from manager_mccode.services.database import DatabaseManager, DatabaseError
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context
import logging
from dataclasses import replace
import copy

logger = logging.getLogger(__name__)

@pytest.fixture
def db():
    """Create a fresh in-memory database for each test"""
    db = DatabaseManager(":memory:")
    db.initialize()  # Explicitly initialize
    db.conn.commit()  # Ensure changes are committed
    return db

@pytest.fixture
def sample_summary():
    """Create a sample screen summary for testing"""
    return ScreenSummary(
        timestamp=datetime(2026, 1, 7, 15, 16, 19, 987874),
        summary="Test activity summary",
        activities=[
            Activity(
                name="Writing tests",
                category="Development",
                focus_indicators=FocusIndicators(
                    attention_level=75,
                    context_switches="low",
                    workspace_organization="organized"
                )
            )
        ],
        context=Context(
            primary_task="Writing unit tests",
            attention_state="scattered",
            environment="Single monitor setup",
            confidence=0.9
        )
    )

def test_store_and_retrieve_summary(db, sample_summary):
    """Test storing and retrieving a complete summary"""
    # Store the summary
    summary_id = db.store_summary(sample_summary)
    assert summary_id is not None
    
    # Retrieve recent summaries
    summaries = db.get_recent_summaries(limit=1)
    assert len(summaries) == 1
    
    retrieved = summaries[0]
    assert retrieved['summary'] == sample_summary.summary
    assert retrieved['focus_state'] == sample_summary.context.attention_state
    assert retrieved['focus_confidence'] == sample_summary.context.confidence

def test_cleanup_old_data(db, sample_summary):
    """Test cleaning up old data"""
    # Store some old and new summaries
    old_summary = copy.deepcopy(sample_summary)
    old_summary.timestamp = datetime.now() - timedelta(days=40)
    db.store_summary(old_summary)
    
    new_summary = copy.deepcopy(sample_summary)
    new_summary.timestamp = datetime.now()
    db.store_summary(new_summary)
    
    # Run cleanup
    db.cleanup_old_data(days=30)
    
    # Verify
    summaries = db.get_recent_summaries()
    assert len(summaries) == 1
    assert summaries[0]['timestamp'] > (datetime.now() - timedelta(days=30))

def test_database_stats(db, sample_summary):
    """Test getting database statistics"""
    # Store some test data
    for _ in range(3):
        db.store_summary(sample_summary)
    
    stats = db.get_database_stats()
    assert 'tables' in stats
    assert 'database_size_mb' in stats
    assert 'time_range' in stats
    assert stats['time_range']['total_records'] == 3

def test_database_integrity(db):
    """Test database integrity check"""
    assert db.verify_database_integrity() is True

def test_error_handling(db):
    """Test database error handling"""
    with pytest.raises(DatabaseError):
        # Pass None to trigger validation error
        db.store_summary(None)

def test_focus_metrics(db, sample_summary):
    """Test focus metrics calculation"""
    # Create two completely separate summaries
    focused = ScreenSummary(
        timestamp=sample_summary.timestamp,
        summary=sample_summary.summary,
        activities=sample_summary.activities,
        context=Context(
            primary_task=sample_summary.context.primary_task,
            attention_state="focused",  # Set this directly
            environment=sample_summary.context.environment,
            confidence=sample_summary.context.confidence
        )
    )
    
    scattered = ScreenSummary(
        timestamp=sample_summary.timestamp,
        summary=sample_summary.summary,
        activities=sample_summary.activities,
        context=Context(
            primary_task=sample_summary.context.primary_task,
            attention_state="scattered",  # Set this directly
            environment=sample_summary.context.environment,
            confidence=sample_summary.context.confidence
        )
    )
    
    # Store the summaries
    focused_id = db.store_summary(focused)
    scattered_id = db.store_summary(scattered)
    
    # Verify directly in the database that states were stored correctly
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT a.id, f.state_type
        FROM activity_snapshots a
        JOIN focus_states f ON a.id = f.snapshot_id
        WHERE a.id IN (?, ?)
    """, (focused_id, scattered_id))
    
    results = cursor.fetchall()
    assert len(results) == 2
    states = {row[0]: row[1] for row in results}
    assert states[focused_id] == "focused"
    assert states[scattered_id] == "scattered"
    
    # Get recent activity
    activity = db.get_recent_activity(hours=24)
    assert len(activity) == 2  # Should have both summaries
    
    # Verify activity data
    focus_states = [a['focus_state'] for a in activity]
    assert "focused" in focus_states
    assert "scattered" in focus_states 