import pytest
from datetime import datetime, timedelta
from manager_mccode.services.database import DatabaseManager, DatabaseError
from manager_mccode.models.screen_summary import ScreenSummary
import logging

logger = logging.getLogger(__name__)

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
        # Pass None to trigger validation error
        db.store_summary(None)

def test_focus_metrics(db, sample_summary):
    """Test focus metrics calculation"""
    # Store summaries with different focus states
    focused = sample_summary.model_copy()
    focused.context.attention_state = "focused"
    scattered = sample_summary.model_copy()
    scattered.context.attention_state = "scattered"

    # Store the summaries
    focused_id = db.store_summary(focused)
    scattered_id = db.store_summary(scattered)
    
    logger.info(f"Stored focused summary with ID: {focused_id}")
    logger.info(f"Stored scattered summary with ID: {scattered_id}")

    # Get recent activity
    activity = db.get_recent_activity(hours=24)
    
    # Debug output
    logger.info(f"Retrieved {len(activity)} activities")
    for a in activity:
        logger.info(f"Activity: {a}")

    # Assertions with better error messages
    assert len(activity) > 0, f"No activity records found. Expected at least 2 records (IDs: {focused_id}, {scattered_id})"
    
    focus_states = [a['focus_state'] for a in activity]
    logger.info(f"Found focus states: {focus_states}")
    
    assert any(a['focus_state'] == 'focused' for a in activity), \
        f"No focused state found. Found states: {focus_states}"
    assert any(a['focus_state'] == 'scattered' for a in activity), \
        f"No scattered state found. Found states: {focus_states}" 