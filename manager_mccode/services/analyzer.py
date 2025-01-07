import json
import google.generativeai as genai
from datetime import datetime
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators
from manager_mccode.config.settings import settings
import os
import asyncio

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
            
            # Create ScreenSummary
            return self._create_summary(result)
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return self._create_error_summary(str(e))

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

    def _create_error_summary(self, error_msg: str) -> ScreenSummary:
        """Create an error summary"""
        return ScreenSummary(
            timestamp=datetime.now(),
            summary=f"Error analyzing screenshot: {error_msg}",
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
            context={
                "primary_task": "error",
                "attention_state": "unknown",
                "environment": "unknown"
            }
        ) 