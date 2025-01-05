"""
Manager McCode - An ADHD-friendly productivity tracker
"""

__version__ = "0.1.0"

from .services.database import DatabaseManager
from .services.image import ImageManager
from .services.analyzer import GeminiAnalyzer
from .services.batch import BatchProcessor
from .models.screen_summary import ScreenSummary

__all__ = [
    'DatabaseManager',
    'ImageManager',
    'GeminiAnalyzer',
    'BatchProcessor',
    'ScreenSummary',
]
