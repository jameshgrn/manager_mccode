from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class FocusIndicators:
    attention_level: float
    context_switches: str  # low, medium, high
    workspace_organization: str  # organized, mixed, scattered
    window_state: Optional[str] = None
    tab_count: Optional[int] = None
    content_type: Optional[str] = None

@dataclass
class Activity:
    name: str
    category: str
    focus_indicators: FocusIndicators
    purpose: str = "Unknown"
    timestamp: Optional[datetime] = None

@dataclass
class Context:
    """Context information for the screen summary"""
    primary_task: str
    attention_state: str  # focused, scattered, transitioning
    environment: str
    confidence: float = 0.5

@dataclass
class ScreenSummary:
    """Summary of screen activity and context"""
    timestamp: datetime
    summary: str
    activities: List[Activity]
    context: Optional[Context] = None 