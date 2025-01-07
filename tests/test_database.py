import pytest
from datetime import datetime, timedelta
from manager_mccode.services.database import DatabaseManager

@pytest.fixture
def db():
    """Provide a test database instance"""
    db = DatabaseManager(":memory:")  # Use in-memory database for testing
    yield db
    db.close()

def test_database_initialization(db):
    """Test database initialization and migrations"""
    # Check if tables exist
    tables = db.conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table'
    """).fetchall()
    table_names = {t[0] for t in tables}
    
    assert "activity_snapshots" in table_names
    assert "focus_states" in table_names
    assert "task_segments" in table_names

def test_store_snapshot(db):
    """Test storing and retrieving snapshots"""
    test_data = {
        "timestamp": datetime.now(),
        "summary": "Test activity",
        "window_title": "Test Window",
        "active_app": "TestApp",
        "focus_score": 0.8
    }
    
    db.store_snapshot(test_data)
    
    result = db.conn.execute("""
        SELECT * FROM activity_snapshots
        ORDER BY timestamp DESC LIMIT 1
    """).fetchone()
    
    assert result is not None
    assert result[2] == "Test activity"  # summary field
    assert result[4] == "TestApp"  # active_app field 