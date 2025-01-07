import json
import google.generativeai as genai
from datetime import datetime
from manager_mccode.models.screen_summary import ScreenSummary
from manager_mccode.config.settings import settings
import os

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class GeminiAnalyzer:
    def __init__(self, model_name=settings.GEMINI_MODEL_NAME):
        self.model = genai.GenerativeModel(model_name)

    @staticmethod
    async def analyze_image(image_path: str) -> ScreenSummary:
        """Analyze screenshot using Gemini Vision API"""
        try:
            # Read image as bytes
            with open(image_path, 'rb') as img_file:
                image_bytes = img_file.read()
            
            # Create generation config for Gemini 1.5
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
                candidate_count=1
            )
            
            # Create proper image part with mime type
            image_part = {
                "mime_type": "image/png",
                "data": image_bytes
            }
            
            prompt = """
            Please analyze this screenshot and provide a structured response.
            Focus on visible applications, content, and activities.
            
            Respond with ONLY valid JSON in this exact format (no markdown, no backticks):
            {
                "summary": "<1-2 sentence summary>",
                "activities": ["activity1", "activity2", ...]
            }
            """
            
            # Create the model with configuration
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL_NAME,
                generation_config=generation_config
            )
            
            response = model.generate_content(
                contents=[prompt, image_part],
                stream=False
            )
            
            if not response.text:
                raise ValueError("Empty response from Gemini")
            
            # Clean up response text - remove any markdown formatting
            response_text = response.text.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
            
            # Parse the JSON response
            try:
                result = json.loads(response_text)
                summary_part = result.get('summary', '')
                activities = result.get('activities', [])
                
                if not summary_part or not activities:
                    raise ValueError("Missing summary or activities in JSON response")
                
                return ScreenSummary(
                    timestamp=datetime.now(),
                    summary=summary_part,
                    activities=activities
                )
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {str(e)}")
                print(f"Raw response: {response_text}")
                summary_part = response_text[:200] + "..."
                return ScreenSummary(
                    timestamp=datetime.now(),
                    summary=summary_part,
                    activities=["Unknown"]
                )
            
        except Exception as e:
            print(f"Error analyzing image: {str(e)}")
            print("Full error:")
            import traceback
            print(traceback.format_exc())
            return ScreenSummary(
                timestamp=datetime.now(),
                summary=f"Error analyzing screenshot: {str(e)}",
                activities=["Error"]
            )
        finally:
            # Always clean up the image file
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                print(f"Error cleaning up image: {str(e)}") 