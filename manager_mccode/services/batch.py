from datetime import datetime
from typing import List, Dict
import logging
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context
from manager_mccode.config.settings import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_INTERVAL_SECONDS,
    GEMINI_MODEL_NAME
)
import google.generativeai as genai
import os
import json

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_interval_seconds: int = DEFAULT_BATCH_INTERVAL_SECONDS
    ):
        self.batch_size = batch_size
        self.batch_interval = batch_interval_seconds
        self.pending_screenshots: Dict[datetime, List[str]] = {}  # timestamp -> list of screenshot paths
        self.last_batch_time = datetime.now()

    def add_screenshot(self, screenshot_path: str):
        """Add a screenshot to the pending batch"""
        current_time = datetime.now()
        
        # Group screenshots taken at the same time (within 1 second)
        matching_time = None
        for timestamp in self.pending_screenshots.keys():
            if abs((current_time - timestamp).total_seconds()) < 1:
                matching_time = timestamp
                break
        
        if matching_time:
            self.pending_screenshots[matching_time].append(screenshot_path)
        else:
            self.pending_screenshots[current_time] = [screenshot_path]
            
        logger.debug(f"Added screenshot to batch. Current size: {len(self.pending_screenshots)}")

    def is_batch_ready(self) -> bool:
        """Check if we have enough screenshots to process a batch"""
        return len(self.pending_screenshots) >= DEFAULT_BATCH_SIZE or \
            (datetime.now() - self.last_batch_time).total_seconds() >= self.batch_interval

    async def process_batch(self) -> List[ScreenSummary]:
        """Process a batch of screenshots"""
        if not self.pending_screenshots:
            return []

        try:
            # Get timestamps sorted by time
            timestamps = sorted(self.pending_screenshots.keys())
            batch_timestamps = timestamps[:self.batch_size]
            
            # Process each set of screenshots
            summaries = []
            for timestamp in batch_timestamps:
                screenshot_paths = self.pending_screenshots[timestamp]
                try:
                    model = genai.GenerativeModel(
                        model_name=GEMINI_MODEL_NAME,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=2048,
                            candidate_count=1
                        )
                    )

                    # Load all images for this timestamp
                    image_parts = []
                    for path in screenshot_paths:
                        with open(path, 'rb') as img_file:
                            image_parts.append({
                                "mime_type": "image/jpeg",
                                "data": img_file.read()
                            })

                    prompt = """
                    You are an observant academic productivity analyst. Analyze these screenshots of academic work across multiple monitors.
                    Consider the entire workspace setup and how multiple screens are being utilized.
                    Focus on visible applications, content, and activities, particularly noting:

                    1. What applications and windows are open across all screens
                    2. The nature of the work being done (subject area, specific task)
                    3. Signs of focus or distraction (window arrangement, tab count)
                    4. Context switching patterns
                    5. Work environment (time of day, screen layout, monitor usage)
                    6. How the multiple monitors are being utilized (e.g., reference material on one screen, main work on another)

                    Think like an academic productivity coach who understands ADHD work patterns and multi-monitor setups.
                    
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

                    # Pass all images to the model at once
                    response = model.generate_content(
                        contents=[prompt] + image_parts,
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
                                timestamp=timestamp,
                                summary=result['summary'],
                                activities=activities,
                                context=context
                            ))
                        except Exception as e:
                            logger.error(f"Error creating ScreenSummary: {e}")
                            logger.error(f"Raw result: {result}")

                except Exception as e:
                    logger.error(f"Error processing screenshots for timestamp {timestamp}: {e}")
                finally:
                    # Clean up the screenshots
                    for path in screenshot_paths:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception as e:
                            logger.error(f"Error cleaning up screenshot {path}: {e}")

            # Remove processed timestamps
            for timestamp in batch_timestamps:
                del self.pending_screenshots[timestamp]

            return summaries

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return []

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
            logger.error(f"Error parsing response: {e}")
            return {
                'summary': f"Error parsing response: {str(e)}",
                'activities': ["Error"]
            } 