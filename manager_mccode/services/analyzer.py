import logging
import json
import google.generativeai as genai
from datetime import datetime
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context
from manager_mccode.models.focus_session import FocusSession, FocusTrigger
from manager_mccode.config.settings import settings
import os
import asyncio
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class GeminiAnalyzer:
    def __init__(self, model_name=settings.GEMINI_MODEL_NAME):
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
                candidate_count=1
            )
        )

    async def analyze_image(self, image_path: str) -> ScreenSummary:
        """Analyze screenshot using Gemini Vision API"""
        try:
            with open(image_path, 'rb') as img_file:
                image_part = {
                    "mime_type": "image/png",
                    "data": img_file.read()
                }
            
            prompt = """
            You are an observant academic productivity analyst. Analyze these screenshots of academic work across multiple monitors.
            Consider the entire workspace setup and how multiple screens are being utilized.
            Focus on visible applications, content, and activities, particularly noting:

            1. What applications and windows are open across all screens
            2. The nature of the work being done (subject area, specific task)
            3. Signs of focus or distraction (window arrangement, tab count)
            4. Context switching patterns
            5. Work environment (time of day, screen layout, monitor usage)
            6. How the multiple monitors are being utilized

            Provide your analysis in the following JSON format:
            {
                "summary": "<overall analysis of work patterns and focus>",
                "activities": [
                    {
                        "name": "<activity name>",
                        "category": "coding|writing|research|communication|other",
                        "purpose": "<activity purpose>",
                        "focus_indicators": {
                            "attention_level": 0-100,
                            "context_switches": "low|medium|high",
                            "workspace_organization": "organized|scattered|mixed"
                        }
                    }
                ],
                "context": {
                    "primary_task": "<main task being worked on>",
                    "attention_state": "focused|scattered|transitioning",
                    "environment": "<relevant environmental factors including monitor usage>"
                }
            }
            """
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                contents=[prompt, image_part],
                stream=False
            )
            
            if not response.text:
                raise ValueError("Empty response from Gemini")
            
            # Parse response
            result = self._parse_response(response.text)
            
            return self._create_summary(result)
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return self._create_error_summary(str(e))
        finally:
            # Always try to clean up the image file
            try:
                Path(image_path).unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up image file: {e}")

    def _parse_response(self, response_text: str) -> dict:
        """Parse the response text into a structured format"""
        text = response_text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()
        
        try:
            result = json.loads(text)
            required_fields = ['summary', 'activities', 'context']
            missing_fields = [f for f in required_fields if f not in result]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            return result
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")

    def _create_summary(self, result: dict) -> ScreenSummary:
        """Create a ScreenSummary from parsed result"""
        activities = [
            Activity(
                name=act['name'],
                category=act['category'],
                purpose=act.get('purpose', ''),
                focus_indicators=FocusIndicators(**act['focus_indicators'])
            ) for act in result['activities']
        ]
        
        return ScreenSummary(
            timestamp=datetime.now(),
            summary=result['summary'],
            activities=activities,
            context=result['context']
        )

    def _create_error_summary(self, error_message: str) -> ScreenSummary:
        """Create an error summary"""
        return ScreenSummary(
            timestamp=datetime.now(),
            summary=f"Error analyzing screenshot: {error_message}",
            activities=[
                Activity(
                    name="Error",
                    category="error",
                    purpose="error",
                    focus_indicators=FocusIndicators(
                        attention_level=0,
                        context_switches="unknown",
                        workspace_organization="unknown"
                    )
                )
            ],
            context=Context(
                primary_task="error",
                attention_state="unknown",
                environment="unknown"
            )
        )

    def analyze_focus_patterns(self, activities: List[Activity]) -> Dict:
        """Analyze focus patterns from activities"""
        return {
            'context_switches': self._detect_context_switches(activities),
            'focus_quality': self._assess_focus_quality(activities),
            'task_completion': self._analyze_task_completion(activities),
            'environment_impact': self._assess_environment(activities),
            'recommendations': self._generate_recommendations(activities)
        } 

    def _detect_context_switches(self, activities: List[Activity]) -> Dict:
        """Analyze context switching patterns"""
        # Group activities into focus sessions
        sessions = self._group_into_sessions(activities)
        
        # Calculate actual metrics
        switches_per_hour = sum(s.context_switches for s in sessions) / (len(sessions) * 0.25)  # 15min periods
        max_duration = max(s.duration_minutes for s in sessions) if sessions else 0
        
        # Analyze actual triggers
        triggers = self._analyze_session_triggers(sessions)
        
        return {
            'switches_per_hour': switches_per_hour,
            'max_focus_duration': max_duration,
            'common_triggers': triggers[:3],  # Top 3 most common triggers
            'session_count': len(sessions),
            'avg_session_length': sum(s.duration_minutes for s in sessions) / len(sessions) if sessions else 0
        }

    def _group_into_sessions(self, activities: List[Activity]) -> List[FocusSession]:
        """Group sequential activities into focus sessions"""
        sessions = []
        current_session = None
        
        for activity in activities:
            # Start new session if:
            # 1. No current session
            # 2. Different activity type
            # 3. High context switch score
            if (not current_session or 
                activity.name != current_session.activity_type or
                activity.focus_indicators.context_switches == 'high'):
                
                if current_session:
                    sessions.append(current_session)
                
                current_session = FocusSession(
                    start_time=activity.timestamp,
                    activity_type=activity.name
                )
            
            # Update current session
            current_session.add_activity(activity)
        
        if current_session:
            sessions.append(current_session)
        
        return sessions

    def _analyze_session_triggers(self, sessions: List[FocusSession]) -> List[str]:
        """Analyze what commonly triggers context switches"""
        trigger_counts = {}
        
        for session in sessions:
            if session.start_time and session.end_time:  # Add null check
                try:
                    duration = (session.end_time - session.start_time).total_seconds() / 60
                    if duration > 0:  # Add duration check
                        for trigger in session.triggers:
                            trigger_type = f"{trigger.source}: {trigger.type}"
                            trigger_counts[trigger_type] = trigger_counts.get(trigger_type, 0) + 1
                except (TypeError, AttributeError):
                    continue  # Skip if we can't calculate duration
        
        # Sort by frequency
        sorted_triggers = sorted(trigger_counts.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_triggers]

    def _assess_focus_quality(self, activities: List[Activity]) -> Dict:
        """Assess quality of focus periods"""
        attention_levels = [act.focus_indicators.attention_level for act in activities]
        avg_attention = sum(attention_levels) / len(attention_levels) if attention_levels else 0
        
        return {
            'avg_focus_score': avg_attention,
            'focus_quality': 'high' if avg_attention > 75 else 'medium' if avg_attention > 50 else 'low',
            'recovery_activities': ['Documentation review', 'Code organization'] if avg_attention > 50 else ['Short break', 'Task switching']
        }

    def _analyze_task_completion(self, activities: List[Activity]) -> Dict:
        """Analyze task completion patterns"""
        organized_count = sum(1 for act in activities if act.focus_indicators.workspace_organization == 'organized')
        completion_rate = organized_count / len(activities) if activities else 0
        
        return {
            'completion_rate': completion_rate,
            'avg_recovery_time': 5 if completion_rate > 0.7 else 15,
            'task_types': {
                'coding': 0.8,
                'research': 0.6,
                'communication': 0.9
            }
        }

    def _assess_environment(self, activities: List[Activity]) -> Dict:
        """Assess environmental impact on focus"""
        workspace_states = [act.focus_indicators.workspace_organization for act in activities]
        organized_ratio = workspace_states.count('organized') / len(workspace_states) if workspace_states else 0
        
        return {
            'workspace_score': organized_ratio * 100,
            'environmental_impacts': [
                'Multi-monitor setup',
                'Application organization',
                'Window management'
            ]
        }

    def _generate_recommendations(self, activities: List[Activity]) -> List[str]:
        """Generate focus improvement recommendations"""
        attention_levels = [act.focus_indicators.attention_level for act in activities]
        avg_attention = sum(attention_levels) / len(attention_levels) if attention_levels else 0
        
        recommendations = []
        
        if avg_attention < 75:
            recommendations.extend([
                "Consider using time-blocking for focused work sessions",
                "Minimize open applications during deep work",
                "Set up dedicated workspaces for different tasks"
            ])
        
        if any(act.focus_indicators.context_switches == 'high' for act in activities):
            recommendations.extend([
                "Reduce context switching by batching similar tasks",
                "Use workspace snapshots to maintain task context",
                "Schedule communication checks at specific times"
            ])
            
        return recommendations 