import pytest
from datetime import datetime, timedelta
from manager_mccode.services.database import DatabaseManager, DatabaseError
from manager_mccode.models.screen_summary import ScreenSummary

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
    old_summary = sample_summary.copy()
    old_summary.timestamp = datetime.now() - timedelta(days=40)
    db.store_summary(old_summary)
    
    new_summary = sample_summary.copy()
    db.store_summary(new_summary)
    
    # Clean up old data
    deleted, space = db.cleanup_old_data(days=30)
    assert deleted >= 1
    
    # Check that only old data was removed
    summaries = db.get_recent_summaries()
    timestamps = [datetime.fromisoformat(s['timestamp']) for s in summaries]
    assert all(t > datetime.now() - timedelta(days=30) for t in timestamps)

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
        # Create an invalid summary
        invalid_summary = ScreenSummary(
            timestamp=datetime.now(),
            summary="Invalid",
            activities=[],
            context=None  # This will cause the error
        )
        db.store_summary(invalid_summary)

def test_focus_metrics(db, sample_summary):
    """Test focus metrics calculation"""
    # Store summaries with different focus states
    focused = sample_summary.model_copy()
    focused.context.attention_state = "focused"
    scattered = sample_summary.model_copy()
    scattered.context.attention_state = "scattered"
    
    db.store_summary(focused)
    db.store_summary(scattered)
    
    # Get recent activity
    activity = db.get_recent_activity(hours=1)
    assert len(activity) > 0
    assert any('focused' in str(a) for a in activity) 