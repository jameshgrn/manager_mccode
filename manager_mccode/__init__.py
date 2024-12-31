from dotenv import load_dotenv
import os
import time
import pyautogui
import google.generativeai as genai
from datetime import datetime
from typing import List, Dict
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro-vision')

class ScreenSummary(BaseModel):
    timestamp: datetime
    summary: str
    key_activities: List[str]

class ScreenCapture:
    @staticmethod
    def capture() -> str:
        """Take a screenshot and save it temporarily"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"temp_screenshot_{timestamp}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        return filename

    @staticmethod
    def cleanup(filename: str):
        """Remove temporary screenshot file"""
        if os.path.exists(filename):
            os.remove(filename)

class GeminiAnalyzer:
    @staticmethod
    async def analyze_image(image_path: str) -> ScreenSummary:
        """Analyze screenshot using Gemini Vision API"""
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()
        
        prompt = """
        Analyze this screenshot and provide:
        1. A brief summary of visible content
        2. Key activities or applications in view
        Focus on main activities and important details only.
        """
        
        response = model.generate_content([prompt, image_data])
        
        # Parse response into structured format
        # This is a simplified version - we'll need to enhance the parsing
        return ScreenSummary(
            timestamp=datetime.now(),
            summary=response.text,
            key_activities=[]  # TODO: Parse activities from response
        )

def main():
    while True:
        try:
            # Capture screenshot
            image_path = ScreenCapture.capture()
            
            # Analyze with Gemini
            summary = GeminiAnalyzer.analyze_image(image_path)
            
            # TODO: Implement summary collation and storage
            print(summary)
            
            # Cleanup
            ScreenCapture.cleanup(image_path)
            
            # Wait for next capture
            time.sleep(30)
            
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    main()
