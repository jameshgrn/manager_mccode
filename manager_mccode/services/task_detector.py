"""Detect higher-level tasks from activity patterns"""
from typing import List, Dict, Optional
import re
import logging
from datetime import datetime
from manager_mccode.models.screen_summary import ScreenSummary, Activity, Context

logger = logging.getLogger(__name__)

class TaskDetector:
    """Detects and classifies tasks from screen activity"""
    
    def __init__(self):
        self.task_patterns = {
            "development": [
                "vscode", "pycharm", "terminal", "git", "github",
                "stackoverflow", "documentation"
            ],
            "communication": [
                "slack", "teams", "outlook", "gmail", "zoom",
                "meet", "chat"
            ],
            "research": [
                "chrome", "firefox", "safari", "papers", "scholar",
                "documentation", "research"
            ],
            "writing": [
                "word", "docs", "notion", "markdown", "latex",
                "overleaf", "writing"
            ]
        }

    def detect_task_context(self, summary: ScreenSummary) -> Context:
        """Analyze screen summary to detect task context"""
        try:
            # Extract activity names
            activity_names = [a.name.lower() for a in summary.activities]
            
            # Detect primary task category
            primary_task = self._detect_primary_task(activity_names)
            
            # Analyze focus state
            attention_state = self._analyze_focus_state(summary.activities)
            
            # Calculate confidence
            confidence = self._calculate_confidence(summary.activities)
            
            # Detect environment
            environment = self._detect_environment(activity_names)
            
            return Context(
                primary_task=primary_task,
                attention_state=attention_state,
                confidence=confidence,
                environment=environment
            )
            
        except Exception as e:
            logger.error(f"Error detecting task context: {e}")
            return Context(
                primary_task="unknown",
                attention_state="unknown",
                confidence=0.0,
                environment="unknown"
            )

    def _detect_primary_task(self, activity_names: List[str]) -> str:
        """Detect primary task category from activities"""
        task_scores = {category: 0 for category in self.task_patterns}
        
        for activity in activity_names:
            for category, patterns in self.task_patterns.items():
                if any(pattern in activity for pattern in patterns):
                    task_scores[category] += 1
        
        if not task_scores:
            return "unknown"
            
        return max(task_scores.items(), key=lambda x: x[1])[0]

    def _analyze_focus_state(self, activities: List[Activity]) -> str:
        """Analyze focus state from activities"""
        if not activities:
            return "unknown"
            
        # Calculate average attention level
        avg_attention = sum(a.focus_indicators.attention_level for a in activities) / len(activities)
        
        # Count context switches
        high_switches = sum(1 for a in activities if a.focus_indicators.context_switches == "high")
        
        if avg_attention >= 75 and high_switches == 0:
            return "focused"
        elif avg_attention <= 40 or high_switches >= 2:
            return "scattered"
        else:
            return "neutral"

    def _calculate_confidence(self, activities: List[Activity]) -> float:
        """Calculate confidence score for the detection"""
        if not activities:
            return 0.0
            
        # Base confidence on consistency of indicators
        attention_levels = [a.focus_indicators.attention_level for a in activities]
        attention_std = self._calculate_std(attention_levels)
        
        # Higher standard deviation = lower confidence
        base_confidence = max(0.0, 1.0 - (attention_std / 100))
        
        # Adjust based on number of activities (more data = higher confidence)
        activity_factor = min(1.0, len(activities) / 5)
        
        return base_confidence * activity_factor

    def _detect_environment(self, activity_names: List[str]) -> str:
        """Detect working environment from activities"""
        office_indicators = ["teams", "outlook", "corporate", "vpn"]
        home_indicators = ["personal", "home"]
        
        office_matches = sum(1 for a in activity_names if any(i in a for i in office_indicators))
        home_matches = sum(1 for a in activity_names if any(i in a for i in home_indicators))
        
        if office_matches > home_matches:
            return "office"
        elif home_matches > office_matches:
            return "home"
        else:
            return "unknown"

    @staticmethod
    def _calculate_std(values: List[float]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        squared_diff_sum = sum((x - mean) ** 2 for x in values)
        return (squared_diff_sum / len(values)) ** 0.5 