from datetime import datetime
from typing import List, Dict, Optional
import logging
from pathlib import Path
import asyncio
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators, Context
from manager_mccode.config.settings import settings
import google.generativeai as genai
import json
import os

logger = logging.getLogger(__name__)

class BatchProcessingError(Exception):
    """Base exception for batch processing errors"""
    pass

class BatchProcessor:
    def __init__(
        self,
        batch_size: Optional[int] = None,
        batch_interval_seconds: Optional[int] = None
    ):
        self.batch_size = batch_size or settings.DEFAULT_BATCH_SIZE
        self.batch_interval = batch_interval_seconds or settings.DEFAULT_BATCH_INTERVAL_SECONDS
        self.pending_screenshots = {}
        self.last_batch_time = datetime.now()
        self.model = self._initialize_model()
        
        # Check for existing screenshots on startup
        self._process_existing_screenshots()
        
        logger.info(
            f"Initialized BatchProcessor with size={self.batch_size}, "
            f"interval={self.batch_interval}s"
        )

    def _initialize_model(self) -> genai.GenerativeModel:
        """Initialize the Gemini model with configuration"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            return genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL_NAME,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                    candidate_count=1
                )
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise BatchProcessingError(f"Model initialization failed: {e}")

    def add_screenshot(self, screenshot_path: str) -> None:
        """Add a screenshot to the pending batch"""
        if not os.path.exists(screenshot_path):
            raise BatchProcessingError(f"Screenshot file not found: {screenshot_path}")
            
        current_time = datetime.now()
        self.pending_screenshots[current_time] = screenshot_path

    def is_batch_ready(self) -> bool:
        """Check if we have enough screenshots to process a batch"""
        return (
            len(self.pending_screenshots) >= self.batch_size or
            (datetime.now() - self.last_batch_time).total_seconds() >= self.batch_interval
        )

    async def process_batch(self) -> List[ScreenSummary]:
        """Process a batch of screenshots"""
        if not self.pending_screenshots:
            return []

        try:
            # Get timestamps sorted by time
            timestamps = sorted(self.pending_screenshots.keys())
            batch_timestamps = timestamps[:self.batch_size]
            
            # Process each screenshot
            summaries = []
            for timestamp in batch_timestamps:
                screenshot_path = self.pending_screenshots[timestamp]
                try:
                    # Load image
                    try:
                        with open(screenshot_path, 'rb') as img_file:
                            image_part = {
                                "mime_type": "image/jpeg",
                                "data": img_file.read()
                            }
                    except Exception as e:
                        logger.error(f"Failed to read image {screenshot_path}: {e}")
                        continue

                    # Generate analysis with retry logic
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = await self._generate_analysis([image_part])
                            if response and response.text:
                                result = self._parse_response(response.text)
                                summary = self._create_summary(result, timestamp)
                                if summary:
                                    summaries.append(summary)
                                break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                logger.error(f"Failed to analyze after {max_retries} attempts: {e}")
                            else:
                                logger.warning(f"Attempt {attempt + 1} failed, retrying: {e}")
                                await asyncio.sleep(1)

                finally:
                    # Clean up the screenshot
                    try:
                        Path(screenshot_path).unlink(missing_ok=True)
                    except Exception as e:
                        logger.error(f"Failed to clean up screenshot {screenshot_path}: {e}")

            # Remove processed timestamps
            for timestamp in batch_timestamps:
                del self.pending_screenshots[timestamp]

            return summaries

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            raise BatchProcessingError(f"Failed to process batch: {e}")

    async def _generate_analysis(self, image_parts: List[Dict]) -> genai.types.GenerateContentResponse:
        """Generate analysis from images using Gemini
        
        Args:
            image_parts: List of image data dictionaries
            
        Returns:
            GenerateContentResponse: Gemini API response
            
        Raises:
            BatchProcessingError: If analysis generation fails
        """
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
        
        try:
            return await asyncio.to_thread(
                self.model.generate_content,
                contents=[prompt] + image_parts,
                stream=False
            )
        except Exception as e:
            raise BatchProcessingError(f"Failed to generate analysis: {e}")

    def _parse_response(self, response_text: str) -> dict:
        """Parse the response text into a structured format
        
        Args:
            response_text: Raw response from Gemini
            
        Returns:
            dict: Parsed response data
            
        Raises:
            BatchProcessingError: If parsing fails
        """
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
            
            # Validate required fields
            required_fields = ['summary', 'activities', 'context']
            missing_fields = [f for f in required_fields if f not in result]
            if missing_fields:
                raise BatchProcessingError(f"Missing required fields: {missing_fields}")
                
            return result
            
        except json.JSONDecodeError as e:
            raise BatchProcessingError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            raise BatchProcessingError(f"Error parsing response: {e}")

    def _create_summary(self, result: dict, timestamp: datetime) -> Optional[ScreenSummary]:
        """Create a ScreenSummary from parsed result
        
        Args:
            result: Parsed response data
            timestamp: Timestamp for the summary
            
        Returns:
            Optional[ScreenSummary]: Created summary or None if creation fails
        """
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
            
            return ScreenSummary(
                timestamp=timestamp,
                summary=result['summary'],
                activities=activities,
                context=context
            )
        except Exception as e:
            logger.error(f"Failed to create ScreenSummary: {e}")
            logger.error(f"Raw result: {result}")
            return None

    def _cleanup_screenshots(self, paths: List[str]) -> None:
        """Clean up screenshot files
        
        Args:
            paths: List of paths to clean up
        """
        for path in paths:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to clean up screenshot {path}: {e}") 

    def _process_existing_screenshots(self):
        """Process any screenshots that exist in the temp directory"""
        try:
            temp_dir = Path("temp_screenshots")
            if not temp_dir.exists():
                return
                
            existing_screenshots = list(temp_dir.glob("*.png"))
            if not existing_screenshots:
                return
                
            logger.info(f"Found {len(existing_screenshots)} existing screenshots to process")
            
            # Sort by creation time
            existing_screenshots.sort(key=lambda p: p.stat().st_ctime)
            
            # Add them to pending queue with their creation timestamps
            for screenshot in existing_screenshots:
                creation_time = datetime.fromtimestamp(screenshot.stat().st_ctime)
                self.pending_screenshots[creation_time] = str(screenshot)
            
            # Process immediately if we have enough for a batch
            if len(self.pending_screenshots) >= self.batch_size:
                logger.info("Processing existing screenshots batch")
                asyncio.create_task(self.process_batch())
                
        except Exception as e:
            logger.error(f"Error processing existing screenshots: {e}") 