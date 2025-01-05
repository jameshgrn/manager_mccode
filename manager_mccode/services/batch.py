from datetime import datetime
from typing import List
from manager_mccode.models.screen_summary import ScreenSummary
from manager_mccode.config.settings import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_INTERVAL_SECONDS,
    GEMINI_MODEL_NAME
)
import google.generativeai as genai
import os
import json

class BatchProcessor:
    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_interval_seconds: int = DEFAULT_BATCH_INTERVAL_SECONDS
    ):
        self.batch_size = batch_size
        self.batch_interval = batch_interval_seconds
        self.pending_screenshots = []
        self.last_batch_time = datetime.now()

    async def process_batch(self) -> List[ScreenSummary]:
        """Process a batch of screenshots"""
        if not self.pending_screenshots:
            return []

        try:
            # Limit batch size
            batch = self.pending_screenshots[:self.batch_size]
            self.pending_screenshots = self.pending_screenshots[self.batch_size:]
            
            # Process each screenshot individually to avoid payload size issues
            summaries = []
            for screenshot in batch:
                try:
                    # Create model with configuration
                    model = genai.GenerativeModel(
                        model_name=GEMINI_MODEL_NAME,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=2048,
                            candidate_count=1
                        )
                    )

                    with open(screenshot['path'], 'rb') as img_file:
                        image_part = {
                            "mime_type": "image/jpeg",
                            "data": img_file.read()
                        }

                    prompt = """
                    You are an observant academic productivity analyst. Analyze this screenshot of academic work.
                    Focus on visible applications, content, and activities, particularly noting:

                    1. What applications and windows are open
                    2. The nature of the work being done (subject area, specific task)
                    3. Signs of focus or distraction (window arrangement, tab count)
                    4. Context switching patterns
                    5. Work environment (time of day, screen layout)

                    Think like an academic productivity coach who understands ADHD work patterns.
                    
                    Respond with ONLY valid JSON in this exact format (no markdown, no backticks):
                    {
                        "summary": "<detailed 1-2 sentence summary including work context and attention patterns>",
                        "activities": [
                            {
                                "name": "<specific_app_or_activity>",
                                "category": "<inferred_category>",
                                "purpose": "<brief_purpose_description>",
                                "focus_indicators": {
                                    "window_state": "foreground|background|minimized",
                                    "tab_count": "<number_if_browser>",
                                    "content_type": "<document|code|communication|etc>"
                                }
                            }
                        ],
                        "context": {
                            "primary_task": "<main task being worked on>",
                            "attention_state": "focused|scattered|transitioning",
                            "environment": "<relevant environmental factors>"
                        }
                    }
                    """

                    response = model.generate_content(
                        contents=[prompt, image_part],
                        stream=False
                    )

                    if response.text:
                        result = self._parse_response(response.text)
                        try:
                            activities = [
                                Activity(
                                    name=act['name'],
                                    category=act['category'],
                                    purpose=act['purpose'],
                                    focus_indicators=FocusIndicators(**act['focus_indicators'])
                                ) for act in result['activities']
                            ]
                            context = Context(**result['context'])
                            
                            summaries.append(ScreenSummary(
                                timestamp=screenshot['timestamp'],
                                summary=result['summary'],
                                activities=activities,
                                context=context
                            ))
                        except Exception as e:
                            logger.error(f"Error creating ScreenSummary: {e}")
                            logger.error(f"Raw result: {result}")

                except Exception as e:
                    print(f"Error processing individual screenshot: {e}")
                finally:
                    # Clean up the screenshot
                    if os.path.exists(screenshot['path']):
                        os.remove(screenshot['path'])

            return summaries

        except Exception as e:
            print(f"Batch processing error: {e}")
            return []
        finally:
            # Ensure any remaining screenshots are cleaned up
            for screenshot in batch:
                try:
                    if os.path.exists(screenshot['path']):
                        os.remove(screenshot['path'])
                except Exception as e:
                    print(f"Error cleaning up screenshot: {e}")

    def _parse_response(self, response_text: str) -> dict:
        """Parse the response text into a structured format"""
        try:
            # Clean up response text
            text = response_text.strip()
            if text.startswith('```'):
                text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
            
            # Parse JSON
            result = json.loads(text)
            
            # Ensure required fields exist
            if not result.get('summary'):
                result['summary'] = "No summary provided"
            if not result.get('activities'):
                result['activities'] = ["Unknown"]
                
            return result
            
        except Exception as e:
            print(f"Error parsing response: {e}")
            return {
                'summary': f"Error parsing response: {str(e)}",
                'activities': ["Error"]
            } 