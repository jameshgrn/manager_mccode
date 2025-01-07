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
    """Activity details"""
    name: str = Field(description="Name of the activity")
    category: str = Field(description="Category of the activity")
    purpose: Optional[str] = Field(
        default="Unknown",
        description="Purpose or goal of the activity"
    )
    focus_indicators: FocusIndicators = Field(
        description="Focus and attention indicators for this activity"
    )

class Context(BaseModel):
    """Context information for the screen summary"""
    primary_task: str = Field(description="Primary task being performed")
    attention_state: str = Field(description="Current attention state (focused/scattered)")
    environment: str = Field(description="Description of work environment")
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for the context assessment"
    )

class ScreenSummary(BaseModel):
    """Summary of screen activity and context"""
    timestamp: datetime = Field(description="When this summary was captured")
    summary: str = Field(description="Text summary of the screen activity")
    activities: List[Activity] = Field(description="List of detected activities")
    context: Optional[Context] = Field(
        default=None,
        description="Contextual information about the activities"
    ) 