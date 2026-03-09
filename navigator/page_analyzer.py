"""
VisionQA Page Analyzer
Uses Gemini to visually analyze page screenshots and identify UI elements.
"""

import base64
import json
import re
from pathlib import Path

from google import genai
from google.genai import types

from config import Config


class PageAnalyzer:
    """Analyzes page screenshots using Gemini multimodal capabilities."""

    def __init__(self):
        self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        self.model = Config.GEMINI_MODEL

    def _load_image(self, image_path: str) -> types.Part:
        """Load an image file and return as a GenAI Part."""
        path = Path(image_path)
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        mime_type = mime_map.get(path.suffix.lower(), "image/png")
        image_bytes = path.read_bytes()
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    def detect_elements(self, screenshot_path: str) -> dict:
        """
        Detect all interactive elements on a page screenshot.
        Returns structured data about buttons, inputs, links, etc.
        """
        image_part = self._load_image(screenshot_path)

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        image_part,
                        types.Part.from_text(text="""You are VisionQA, an expert UI analyst. Analyze this screenshot and identify ALL interactive elements.

Return a JSON object with this exact structure:
{
  "page_title": "detected page title or description",
  "elements": [
    {
      "type": "button|input|link|dropdown|checkbox|other",
      "label": "visible text or aria label",
      "location": "top-left|top-center|top-right|center-left|center|center-right|bottom-left|bottom-center|bottom-right",
      "description": "brief description of the element's purpose",
      "is_visible": true,
      "is_enabled": true
    }
  ],
  "page_state": "loaded|loading|error|empty",
  "observations": ["any notable visual observations about the page"]
}

Be thorough. Include navigation items, form fields, action buttons, and any clickable elements."""),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"page_title": "Unknown", "elements": [], "page_state": "unknown", "observations": [response.text]}

    def find_element_by_intent(self, instruction: str, screenshot_path: str) -> dict:
        """
        Given a natural language instruction, identify the target element.
        Returns the element description and suggested Selenium action.
        """
        image_part = self._load_image(screenshot_path)

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        image_part,
                        types.Part.from_text(text=f"""You are VisionQA, an expert UI navigator. A tester wants to: "{instruction}"

Look at this screenshot and determine:
1. Which element should be interacted with?
2. What Selenium action should be performed?

Return a JSON object:
{{
  "target_element": {{
    "type": "button|input|link|dropdown|checkbox|other",
    "label": "visible text of the element",
    "location": "description of where it is on screen",
    "css_hints": "suggested CSS selector if visible (e.g., button text, input placeholder)"
  }},
  "action": {{
    "type": "click|type|select|scroll|hover|wait",
    "value": "text to type or option to select (if applicable)",
    "description": "human-readable description of what to do"
  }},
  "confidence": 0.95,
  "reasoning": "Why this element matches the intent"
}}"""),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {
                "target_element": {"type": "unknown", "label": "unknown"},
                "action": {"type": "unknown", "description": response.text},
                "confidence": 0.0,
                "reasoning": "Failed to parse response",
            }

    def is_page_stable(self, screenshot1_path: str, screenshot2_path: str) -> dict:
        """
        Compare two screenshots to determine if the page has finished loading.
        Uses pixel comparison to detect if spinners/loaders are still active.
        """
        from PIL import Image

        img1 = Image.open(screenshot1_path).convert("RGBA")
        img2 = Image.open(screenshot2_path).convert("RGBA")

        # Ensure same size
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        total_pixels = len(pixels1)
        diff_count = 0

        for p1, p2 in zip(pixels1, pixels2):
            if abs(p1[0] - p2[0]) > 10 or abs(p1[1] - p2[1]) > 10 or abs(p1[2] - p2[2]) > 10:
                diff_count += 1

        diff_percentage = diff_count / total_pixels if total_pixels > 0 else 0

        return {
            "is_stable": diff_percentage < 0.02,  # Less than 2% change = stable
            "diff_percentage": round(diff_percentage * 100, 2),
            "total_pixels": total_pixels,
            "changed_pixels": diff_count,
        }
