from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class FocusIndicators(BaseModel):
    """Focus and attention indicators"""
    attention_level: int = Field(
        ge=0,  # Greater than or equal to 0
        le=100,  # Less than or equal to 100
        description="Attention level (0-100)"
    )
    context_switches: str = Field(
        description="Frequency of context switches (low/medium/high)"
    )
    workspace_organization: str = Field(
        description="State of workspace organization (organized/mixed/scattered)"
    )
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