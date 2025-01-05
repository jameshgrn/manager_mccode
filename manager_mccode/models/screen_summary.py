from datetime import datetime
from typing import List, Dict
from pydantic import BaseModel

class FocusIndicators(BaseModel):
    window_state: str
    tab_count: int | None = None
    content_type: str

class Activity(BaseModel):
    name: str
    category: str
    purpose: str
    focus_indicators: FocusIndicators

class Context(BaseModel):
    primary_task: str
    attention_state: str
    environment: str

class ScreenSummary(BaseModel):
    timestamp: datetime
    summary: str
    activities: List[Activity]
    context: Context 