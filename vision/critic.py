"""
VisionQA Critic
Second-pass hallucination guardrail — evaluates the primary analysis
for accuracy and grounding.
"""

import json
import re
from pathlib import Path

from google import genai
from google.genai import types

from config import Config


PERSONA_PREFIX = "\033[93m[VisionQA Critic]\033[0m"


def _narrate(message: str):
    print(f"{PERSONA_PREFIX} {message}")


class Critic:
    """
    The 'Critic' agent — a second Gemini call that reviews the primary
    analysis for hallucinations, unjustified confidence, and errors.
    Implements the self-reflection stage of the Multi-Headed Validation Loop.
    """

    SYSTEM_INSTRUCTION = """You are VisionQA Critic, a rigorous adversarial reviewer. Your job is to CHALLENGE the primary QA analysis and check for:

1. HALLUCINATIONS — Does the analysis reference UI elements not visible in the screenshot?
2. OVERCONFIDENCE — Is the confidence score justified by the visual evidence?
3. MISSED DEFECTS — Are there visible issues the primary analysis failed to catch?
4. LOGICAL ERRORS — Does the reasoning chain (Observe → Reason → Judge) hold up?

You are skeptical by nature. If something seems wrong, flag it. Be precise and cite specific visual details."""

    def __init__(self):
        self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        self.model = Config.GEMINI_PRO_MODEL
        _narrate(f"🧠 Critic model: {self.model}")

    def review(self, screenshot_path: str, original_analysis: dict) -> dict:
        """
        Review the primary analysis against the original screenshot.
        Returns adjusted confidence and critique notes.
        """
        _narrate("🧐 Initiating self-reflection review...")
        _narrate(f"📋 Reviewing analysis with status: {original_analysis.get('status', 'unknown')}")

        path = Path(screenshot_path)
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        mime_type = mime_map.get(path.suffix.lower(), "image/png")
        image_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)

        analysis_json = json.dumps(original_analysis, indent=2)

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        image_part,
                        types.Part.from_text(text=f"""Review this QA analysis against the screenshot. Check for hallucinations and errors.

PRIMARY ANALYSIS:
{analysis_json}

Return a JSON object:
{{
  "review_status": "CONFIRMED|DISPUTED|ADJUSTED",
  "hallucinations_found": false,
  "hallucination_details": "description if any hallucinations found",
  "missed_defects": ["any defects the primary analysis missed"],
  "confidence_justified": true,
  "adjusted_confidence": 0.92,
  "critique": "Your detailed critique of the analysis",
  "recommendation": "ACCEPT|REJECT|LOWER_CONFIDENCE"
}}"""),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        result = self._parse_response(response.text)

        review_status = result.get("review_status", "ADJUSTED")
        adjusted_confidence = float(result.get("adjusted_confidence", original_analysis.get("confidence", 0.5)))
        hallucinations = result.get("hallucinations_found", False)

        # Narrate the critique
        if hallucinations:
            _narrate(f"🚨 HALLUCINATION DETECTED: {result.get('hallucination_details', 'unspecified')}")
        elif review_status == "CONFIRMED":
            _narrate("✅ Analysis confirmed. No issues found.")
        elif review_status == "ADJUSTED":
            _narrate(f"🔧 Confidence adjusted: {adjusted_confidence:.0%}")
        else:
            _narrate(f"❌ Analysis DISPUTED: {result.get('critique', 'See details')}")

        missed = result.get("missed_defects", [])
        if missed:
            _narrate(f"👁️ Missed defects found: {len(missed)}")
            for defect in missed:
                _narrate(f"   • {defect}")

        return result

    def _parse_response(self, text: str) -> dict:
        """Parse JSON from response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {
                "review_status": "ADJUSTED",
                "hallucinations_found": False,
                "confidence_justified": False,
                "adjusted_confidence": 0.5,
                "critique": text[:500],
                "recommendation": "LOWER_CONFIDENCE",
            }
