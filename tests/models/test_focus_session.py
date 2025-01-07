import pytest
from datetime import datetime, timedelta
from manager_mccode.models.focus_session import FocusSession, FocusTrigger
from manager_mccode.models.screen_summary import Activity, FocusIndicators

def test_focus_session_initialization():
    """Test basic FocusSession initialization"""
    start_time = datetime.now()
    session = FocusSession(
        start_time=start_time,
        activity_type="coding"
    )
    
    assert session.start_time == start_time
    assert session.activity_type == "coding"
    assert session.duration_minutes == 0
    assert session.context_switches == 0
    assert session.attention_score == 0.0
    assert session.triggers == []

def test_add_activity():
    """Test adding activities to a session"""
    start_time = datetime.now()
    session = FocusSession(
        start_time=start_time,
        activity_type="coding"
    )
    
    # Create test activity
    activity = Activity(
        name="coding",
        category="development",
        purpose="testing",
        focus_indicators=FocusIndicators(
            attention_level=75.0,
            context_switches="low",
            workspace_organization="organized"
        )
    )
    activity.timestamp = start_time + timedelta(minutes=30)
    
    # Add activity
    session.add_activity(activity)
    
    assert session.end_time == activity.timestamp
    assert session.duration_minutes == 30
    assert session.attention_score == 37.5  # (0 + 75) / 2
    assert session.context_switches == 0  # low switches

def test_high_context_switches():
    """Test handling of high context switch activities"""
    start_time = datetime.now()
    session = FocusSession(
        start_time=start_time,
        activity_type="coding"
    )
    
    activity = Activity(
        name="coding",
        category="development",
        purpose="testing",
        focus_indicators=FocusIndicators(
            attention_level=50.0,
            context_switches="high",
            workspace_organization="scattered"
        )
    )
    activity.timestamp = start_time + timedelta(minutes=15)
    
    session.add_activity(activity)
    assert session.context_switches == 1 

def test_focus_triggers():
    """Test adding and retrieving focus triggers"""
    start_time = datetime.now()
    session = FocusSession(
        start_time=start_time,
        activity_type="coding"
    )
    
    # Add a trigger
    trigger = FocusTrigger(
        type="notification",
        source="slack",
        timestamp=start_time + timedelta(minutes=5),
        recovery_time=30  # 30 seconds to recover
    )
    session.triggers.append(trigger)
    
    assert len(session.triggers) == 1
    assert session.triggers[0].type == "notification"
    assert session.triggers[0].source == "slack"
    assert session.triggers[0].recovery_time == 30 