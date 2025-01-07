"""Collect and analyze performance metrics"""
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional
from manager_mccode.services.database import DatabaseManager

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collects and formats activity metrics for analysis"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_daily_metrics(self, date: Optional[datetime] = None) -> Dict:
        """Get metrics for a specific date"""
        if date is None:
            date = datetime.now()
        try:
            # Convert date to datetime range
            start = datetime.combine(date.date(), time.min)  # Start of day
            end = datetime.combine(date.date(), time.max)    # End of day
            
            return {
                "summary": self._get_daily_summary(start, end),
                "activities": self._get_activity_breakdown(start, end),
                "focus_states": self._get_focus_distribution(start, end),
                "hourly_patterns": self._get_hourly_patterns(start, end)
            }
        except Exception as e:
            logger.error(f"Error getting daily metrics: {e}")
            return {}

    def export_timeframe(self, start: datetime, end: datetime) -> Dict:
        """Export all metrics for a given timeframe"""
        return {
            "timeframe": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "daily_metrics": self._get_daily_metrics_series(start, end),
            "aggregate_metrics": self._get_aggregate_metrics(start, end)
        }

    def _get_daily_summary(self, start: datetime, end: datetime) -> Dict:
        """Get summary metrics for a day"""
        try:
            snapshots = self.db.get_snapshots_between(start, end) or []
            if not snapshots:
                return {
                    "active_hours": 0.0,
                    "context_switches": 0,
                    "focus_score": 0.0,
                    "total_snapshots": 0,
                    "date": start.strftime("%Y-%m-%d")
                }
            
            focus_scores = [s.get("focus_score", 0) for s in snapshots]
            return {
                "active_hours": self._calculate_active_hours(snapshots),
                "context_switches": len([s for s in snapshots if s.get("context_switches") == "high"]),
                "focus_score": sum(focus_scores) / len(focus_scores) if focus_scores else 0.0,
                "total_snapshots": len(snapshots),
                "date": start.strftime("%Y-%m-%d")
            }
        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {
                "active_hours": 0.0,
                "context_switches": 0,
                "focus_score": 0.0,
                "total_snapshots": 0,
                "date": start.strftime("%Y-%m-%d")
            }

    def _get_activity_breakdown(self, start: datetime, end: datetime) -> Dict:
        """Get detailed activity metrics"""
        try:
            activities = self.db.get_activities_between(start, end)
            
            # Group by category
            categories = {}
            for activity in activities:
                category = activity.get("category", "unknown")
                categories[category] = categories.get(category, 0) + 1
                
            return {
                "categories": categories,
                "total_activities": len(activities)
            }
        except Exception as e:
            logger.error(f"Error getting activity breakdown: {e}")
            return {}

    def _get_focus_distribution(self, start: datetime, end: datetime) -> Dict:
        """Get focus state distribution"""
        try:
            states = self.db.get_focus_states_between(start, end)
            
            distribution = {
                "focused": 0,
                "neutral": 0,
                "scattered": 0,
                "unknown": 0
            }
            
            for state in states:
                state_type = state.get("state_type", "unknown")
                distribution[state_type] = distribution.get(state_type, 0) + 1
                
            return distribution
        except Exception as e:
            logger.error(f"Error getting focus distribution: {e}")
            return {}

    def _get_hourly_patterns(self, start: datetime, end: datetime) -> Dict[int, Dict]:
        """Get activity patterns by hour"""
        try:
            snapshots = self.db.get_snapshots_between(start, end) or []
            patterns = {hour: {"snapshots": 0, "focus_score": 0.0, "activities": 0} 
                        for hour in range(24)}
            
            for snapshot in snapshots:
                timestamp = snapshot.get("timestamp")
                if not timestamp:
                    continue
                hour = timestamp.hour
                patterns[hour]["snapshots"] += 1
                patterns[hour]["focus_score"] += snapshot.get("focus_score", 0)
                patterns[hour]["activities"] += len(snapshot.get("activities") or [])
            
            # Safe average calculation
            for hour in patterns:
                if patterns[hour]["snapshots"] > 0:
                    patterns[hour]["focus_score"] /= patterns[hour]["snapshots"]
            
            return patterns
        except Exception as e:
            logger.error(f"Error getting hourly patterns: {e}")
            return {hour: {"snapshots": 0, "focus_score": 0.0, "activities": 0} 
                    for hour in range(24)}

    def _calculate_active_hours(self, snapshots: List[Dict]) -> float:
        """Calculate approximate active hours"""
        if not snapshots:
            return 0.0
        
        # Sort by timestamp and filter out None timestamps
        valid_snapshots = [s for s in snapshots if s.get("timestamp")]
        if not valid_snapshots:
            return 0.0
        
        sorted_snapshots = sorted(valid_snapshots, key=lambda x: x["timestamp"])
        
        # Calculate time differences
        total_minutes = 0
        for i in range(len(sorted_snapshots) - 1):
            try:
                diff = sorted_snapshots[i + 1]["timestamp"] - sorted_snapshots[i]["timestamp"]
                # Only count gaps less than 30 minutes
                if diff.total_seconds() < 1800:  # 30 minutes
                    total_minutes += diff.total_seconds() / 60
            except (TypeError, AttributeError):
                continue
            
        return round(total_minutes / 60, 2)  # Convert to hours

    def _get_primary_tasks(self, snapshots: List[Dict]) -> Dict:
        """Get distribution of primary tasks"""
        tasks = {}
        for snapshot in snapshots:
            task = snapshot.get("primary_task", "unknown")
            tasks[task] = tasks.get(task, 0) + 1
        return tasks 

    def _get_daily_metrics_series(self, start: datetime, end: datetime) -> List[Dict]:
        """Get metrics for each day in the timeframe"""
        daily_metrics = []
        current = start
        
        while current <= end:
            next_day = current + timedelta(days=1)
            metrics = {
                "date": current.date().isoformat(),
                "summary": self._get_daily_summary(current, next_day),
                "activities": self._get_activity_breakdown(current, next_day),
                "focus_states": self._get_focus_distribution(current, next_day),
                "hourly_patterns": self._get_hourly_patterns(current, next_day)
            }
            daily_metrics.append(metrics)
            current = next_day
            
        return daily_metrics

    def _get_aggregate_metrics(self, start: datetime, end: datetime) -> Dict:
        """Get aggregated metrics for the entire timeframe"""
        try:
            # Get all data for the period
            snapshots = self.db.get_snapshots_between(start, end) or []
            activities = self.db.get_activities_between(start, end) or []
            focus_states = self.db.get_focus_states_between(start, end) or []
            
            # Calculate aggregates
            total_snapshots = len(snapshots)
            if not total_snapshots:
                return {
                    "total_snapshots": 0,
                    "timeframe_hours": (end - start).total_seconds() / 3600,
                    "active_hours": 0.0,
                    "category_distribution": {},
                    "focus_distribution": {
                        "focused": 0,
                        "neutral": 0,
                        "scattered": 0,
                        "unknown": 0
                    },
                    "average_focus_score": 0.0
                }
            
            # Activity category distribution
            category_counts = {}
            for activity in activities:
                category = activity.get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Focus state distribution
            focus_distribution = {
                "focused": 0,
                "neutral": 0,
                "scattered": 0,
                "unknown": 0
            }
            for state in focus_states:
                state_type = state.get("state_type", "unknown")
                focus_distribution[state_type] = focus_distribution.get(state_type, 0) + 1
            
            # Calculate average focus score
            focus_scores = [s.get("focus_score", 0) for s in snapshots if s.get("focus_score") is not None]
            avg_focus_score = sum(focus_scores) / len(focus_scores) if focus_scores else 0
            
            return {
                "total_snapshots": total_snapshots,
                "timeframe_hours": (end - start).total_seconds() / 3600,
                "active_hours": self._calculate_active_hours(snapshots),
                "category_distribution": category_counts,
                "focus_distribution": focus_distribution,
                "average_focus_score": round(avg_focus_score, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting aggregate metrics: {e}")
            return {
                "total_snapshots": 0,
                "timeframe_hours": 0,
                "active_hours": 0.0,
                "category_distribution": {},
                "focus_distribution": {"focused": 0, "neutral": 0, "scattered": 0, "unknown": 0},
                "average_focus_score": 0.0
            }

    def _calculate_focus_score(self, focus_states: Dict[str, int]) -> float:
        """Calculate overall focus score from state distribution"""
        total = sum(focus_states.values())
        if total == 0:
            return 0.0
        
        # Weight: focused = 100, neutral = 50, scattered = 0
        weighted_sum = (
            focus_states.get("focused", 0) * 100 +
            focus_states.get("neutral", 0) * 50 +
            focus_states.get("scattered", 0) * 0
        )
        
        return round(weighted_sum / total, 1) 