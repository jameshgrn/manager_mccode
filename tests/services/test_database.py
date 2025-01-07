from datetime import datetime, timedelta
import pytest
from manager_mccode.models.focus_session import FocusSession, FocusTrigger

@pytest.fixture
def db():
    """Create a test database"""
    from manager_mccode.services.database import DatabaseManager
    db = DatabaseManager(":memory:")  # Use in-memory database for tests
    db.initialize()
    return db

def test_focus_session_storage(db):
    """Test storing and retrieving focus sessions"""
    # Create a test focus session with no microseconds
    start_time = datetime.now().replace(microsecond=0)  # Strip microseconds
    session = FocusSession(
        start_time=start_time,
        activity_type="coding",
        duration_minutes=30,
        context_switches=2,
        attention_score=75.0
    )
    
    # Store session
    db.store_focus_session(session)
    
    # Debug: Check what's in the database
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM focus_sessions")
    rows = cursor.fetchall()
    print("\nDebug - focus_sessions table contents:")
    print(rows)
    
    # Debug: Check the query
    cursor.execute("""
        SELECT COUNT(*) FROM focus_sessions 
        WHERE strftime('%s', start_time) >= strftime('%s', 'now', '-1 hours')
    """)
    count = cursor.fetchone()[0]
    print(f"\nDebug - Query count: {count}")
    print(f"Debug - Current time: {datetime.now()}")
    print(f"Debug - Session start time: {start_time}")
    
    # Retrieve and verify
    stored_sessions = db.get_focus_sessions(hours=1)
    assert len(stored_sessions) == 1
    stored = stored_sessions[0]
    
    # Compare without microseconds
    assert stored.start_time.replace(microsecond=0) == session.start_time
    assert stored.activity_type == session.activity_type
    assert stored.duration_minutes == session.duration_minutes
    assert stored.context_switches == session.context_switches
    assert stored.attention_score == session.attention_score 