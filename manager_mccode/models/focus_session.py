from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class FocusTrigger:
    type: str  # notification, app_switch, new_window, etc.
    source: str  # The app/window that caused the switch
    timestamp: datetime
    recovery_time: Optional[int] = None  # seconds until focus resumed

@dataclass
class FocusSession:
    start_time: datetime
    activity_type: str
    end_time: Optional[datetime] = None
    duration_minutes: int = 0
    context_switches: int = 0
    attention_score: float = 0.0
    triggers: List[FocusTrigger] = field(default_factory=list)
    
    def add_activity(self, activity: 'Activity'):
        """Add an activity to this session"""
        self.end_time = activity.timestamp
        self.duration_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        self.attention_score = (self.attention_score + activity.focus_indicators.attention_level) / 2
        
        if activity.focus_indicators.context_switches == 'high':
            self.context_switches += 1
            # TODO: Analyze activity to determine trigger type and source 