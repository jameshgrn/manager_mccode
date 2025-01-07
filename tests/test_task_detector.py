import pytest
from datetime import datetime
from manager_mccode.services.task_detector import TaskDetector
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context

@pytest.fixture
def task_detector():
    """Create a TaskDetector instance"""
    return TaskDetector()

@pytest.fixture
def development_summary():
    """Create a test summary for development activities"""
    return ScreenSummary(
        timestamp=datetime.now(),
        summary="Coding in VSCode with documentation",
        activities=[
            Activity(
                name="vscode",
                category="development",
                focus_indicators=FocusIndicators(
                    attention_level=90,
                    context_switches="low",
                    workspace_organization="organized"
                )
            ),
            Activity(
                name="stackoverflow",
                category="research",
                focus_indicators=FocusIndicators(
                    attention_level=85,
                    context_switches="low",
                    workspace_organization="organized"
                )
            )
        ]
    )

@pytest.fixture
def scattered_summary():
    """Create a test summary for scattered activities"""
    return ScreenSummary(
        timestamp=datetime.now(),
        summary="Multiple context switches",
        activities=[
            Activity(
                name="slack",
                category="communication",
                focus_indicators=FocusIndicators(
                    attention_level=30,
                    context_switches="high",
                    workspace_organization="scattered"
                )
            ),
            Activity(
                name="chrome",
                category="research",
                focus_indicators=FocusIndicators(
                    attention_level=40,
                    context_switches="high",
                    workspace_organization="scattered"
                )
            )
        ]
    )

def test_detect_primary_task(task_detector, development_summary):
    """Test primary task detection"""
    activity_names = [a.name.lower() for a in development_summary.activities]
    task = task_detector._detect_primary_task(activity_names)
    assert task == "development"

def test_detect_primary_task_unknown(task_detector):
    """Test unknown task detection"""
    task = task_detector._detect_primary_task(["unknown_app"])
    assert task == "unknown"

def test_analyze_focus_state_focused(task_detector, development_summary):
    """Test focus state analysis for focused work"""
    state = task_detector._analyze_focus_state(development_summary.activities)
    assert state == "focused"

def test_analyze_focus_state_scattered(task_detector, scattered_summary):
    """Test focus state analysis for scattered work"""
    state = task_detector._analyze_focus_state(scattered_summary.activities)
    assert state == "scattered"

def test_analyze_focus_state_empty(task_detector):
    """Test focus state analysis with no activities"""
    state = task_detector._analyze_focus_state([])
    assert state == "unknown"

def test_calculate_confidence(task_detector, development_summary):
    """Test confidence calculation"""
    confidence = task_detector._calculate_confidence(development_summary.activities)
    assert 0 <= confidence <= 1.0
    assert confidence > 0.5  # Should be high confidence for consistent activities

def test_calculate_confidence_scattered(task_detector, scattered_summary):
    """Test confidence calculation for scattered activities"""
    confidence = task_detector._calculate_confidence(scattered_summary.activities)
    assert 0 <= confidence <= 1.0
    assert confidence < 0.8  # Should be lower confidence for scattered activities

def test_detect_environment_office(task_detector):
    """Test office environment detection"""
    activities = ["teams meeting", "outlook email", "corporate vpn"]
    env = task_detector._detect_environment(activities)
    assert env == "office"

def test_detect_environment_home(task_detector):
    """Test home environment detection"""
    activities = ["personal browser", "home network", "spotify"]
    env = task_detector._detect_environment(activities)
    assert env == "home"

def test_detect_environment_unknown(task_detector):
    """Test unknown environment detection"""
    activities = ["chrome", "vscode"]
    env = task_detector._detect_environment(activities)
    assert env == "unknown"

def test_calculate_std(task_detector):
    """Test standard deviation calculation"""
    values = [80, 85, 90, 75]
    std = task_detector._calculate_std(values)
    assert std > 0
    assert isinstance(std, float)

def test_calculate_std_empty(task_detector):
    """Test standard deviation with empty list"""
    std = task_detector._calculate_std([])
    assert std == 0.0

def test_detect_task_context_success(task_detector, development_summary):
    """Test successful task context detection"""
    context = task_detector.detect_task_context(development_summary)
    assert isinstance(context, Context)
    assert context.primary_task == "development"
    assert context.attention_state == "focused"
    assert context.confidence > 0.5

def test_detect_task_context_error_handling(task_detector):
    """Test error handling in task context detection"""
    # Create an invalid summary to trigger error
    invalid_summary = ScreenSummary(
        timestamp=datetime.now(),
        summary="Invalid",
        activities=[]  # Empty activities should trigger error handling
    )
    
    context = task_detector.detect_task_context(invalid_summary)
    assert isinstance(context, Context)
    assert context.primary_task == "unknown"
    assert context.attention_state == "unknown"
    assert context.confidence == 0.0
    assert context.environment == "unknown" 