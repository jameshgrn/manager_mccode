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
            if not summary.activities:  # First check for empty activities
                return Context(
                    primary_task="unknown",
                    attention_state="unknown",
                    confidence=0.0,
                    environment="unknown"
                )
            
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
        if not activity_names:  # First check if empty
            return "unknown"
        
        task_scores = {category: 0 for category in self.task_patterns}
        
        # Count matches for each category
        for activity in activity_names:
            matched = False
            for category, patterns in self.task_patterns.items():
                if any(pattern in activity for pattern in patterns):
                    task_scores[category] += 1
                    matched = True
            if not matched:  # If no patterns matched this activity
                task_scores["unknown"] = task_scores.get("unknown", 0) + 1
        
        if not task_scores or max(task_scores.values()) == 0:
            return "unknown"
        
        # Get category with highest score
        max_score = max(task_scores.values())
        max_categories = [cat for cat, score in task_scores.items() if score == max_score]
        
        return max_categories[0] if max_categories else "unknown"

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
        # Adjusted formula to give higher base confidence
        base_confidence = max(0.0, 1.0 - (attention_std / 50))  # Changed from 100 to 50
        
        # Adjust based on number of activities (more data = higher confidence)
        # Adjusted to give more weight to activity count
        activity_factor = min(1.0, len(activities) / 3)  # Changed from 5 to 3
        
        # Combine factors with higher weight on base_confidence
        return (base_confidence * 0.7 + activity_factor * 0.3)

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