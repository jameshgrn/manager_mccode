import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def db():
    """Provide a test database instance"""
    db = DatabaseManager(":memory:")  # Use in-memory database for testing
    yield db
    db.close()

@pytest.fixture
def image_manager(temp_dir):
    """Provide a test image manager instance"""
    manager = ImageManager(temp_dir=temp_dir)
    yield manager
    manager.cleanup_old_images(max_age_minutes=0)

@pytest.fixture
def batch_processor():
    """Provide a test batch processor instance"""
    processor = BatchProcessor(batch_size=2, batch_interval_seconds=5)
    yield processor

@pytest.fixture
def sample_summary():
    """Provide a sample ScreenSummary for testing"""
    return ScreenSummary(
        timestamp=datetime.now(),
        summary="Test activity summary",
        activities=[
            Activity(
                name="Coding",
                category="development",
                purpose="Writing tests",
                focus_indicators=FocusIndicators(
                    attention_level=85,
                    context_switches="low",
                    workspace_organization="organized"
                )
            )
        ],
        context=Context(
            primary_task="Writing unit tests",
            attention_state="focused",
            environment="Single monitor setup",
            confidence=0.9
        )
    ) 