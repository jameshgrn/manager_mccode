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

    logger.info(f"Created focused summary with state: {focused.context.attention_state}")
    logger.info(f"Created scattered summary with state: {scattered.context.attention_state}")

    # Verify the states are different before storing
    assert focused.context.attention_state != scattered.context.attention_state, \
        f"Focus states should be different before storing. Found: focused={focused.context.attention_state}, scattered={scattered.context.attention_state}"

    # Store the summaries
    focused_id = db.store_summary(focused)
    scattered_id = db.store_summary(scattered)
    
    logger.info(f"Stored focused summary with ID: {focused_id}")
    logger.info(f"Stored scattered summary with ID: {scattered_id}")

    # Verify directly in the database that states were stored correctly
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, f.state_type 
        FROM activity_snapshots a
        JOIN focus_states f ON a.id = f.snapshot_id
        WHERE a.id IN (?, ?)
    """, (focused_id, scattered_id))
    
    stored_states = dict(cursor.fetchall())
    logger.info(f"Directly queried states from database: {stored_states}")
    
    assert stored_states[focused_id] == "focused", \
        f"Focused state not stored correctly. Expected 'focused', got '{stored_states.get(focused_id)}'"
    assert stored_states[scattered_id] == "scattered", \
        f"Scattered state not stored correctly. Expected 'scattered', got '{stored_states.get(scattered_id)}'"

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