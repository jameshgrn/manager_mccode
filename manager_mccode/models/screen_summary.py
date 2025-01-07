from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel

class FocusIndicators(BaseModel):
    attention_level: int
    context_switches: str
    workspace_organization: str
    window_state: Optional[str] = None
    tab_count: Optional[str] = None
    content_type: Optional[str] = None

class Activity(BaseModel):
    name: str
    category: str
    purpose: str
    focus_indicators: FocusIndicators

class Context(BaseModel):
    primary_task: str
    attention_state: str
    environment: str
    confidence: float = 0.5  # Default confidence value

class ScreenSummary(BaseModel):
    timestamp: datetime
    summary: str
    activities: List[Activity]
    context: Optional[Context] = None 