"""
VisionQA Configuration Module
Loads environment variables and provides centralized configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv(".env", override=True)
load_dotenv(".ENV", override=True)  # Windows: also try uppercase



class Config:
    """Central configuration for VisionQA."""

    # Google GenAI
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

    # Vision Engine
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
    PIXEL_DIFF_THRESHOLD: float = float(os.getenv("PIXEL_DIFF_THRESHOLD", "0.05"))

    # Google Cloud Storage
    GCS_BUCKET: str = os.getenv("GCS_BUCKET", "visionqa-baselines")

    # Workflow Automator
    JIRA_WEBHOOK_URL: str = os.getenv("JIRA_WEBHOOK_URL", "")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")

    # Application
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    PORT: int = int(os.getenv("PORT", "8080"))
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "10/minute")
    BASELINES_DIR: str = os.getenv("BASELINES_DIR", "baselines")
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of errors."""
        errors = []
        if not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is required. Set it in .env or environment.")
        return errors

    @classmethod
    def print_status(cls):
        """Print configuration status for debugging."""
        print("=" * 50)
        print("VisionQA Configuration")
        print("=" * 50)
        print(f"  Gemini Model:        {cls.GEMINI_MODEL}")
        print(f"  Critic Model:        {cls.GEMINI_PRO_MODEL}")
        print(f"  Confidence Threshold:{cls.CONFIDENCE_THRESHOLD}")
        print(f"  Pixel Diff Threshold:{cls.PIXEL_DIFF_THRESHOLD}")
        print(f"  GCS Bucket:          {cls.GCS_BUCKET}")
        print(f"  Jira Webhook:        {'Configured' if cls.JIRA_WEBHOOK_URL else 'Not Set'}")
        print(f"  Slack Webhook:       {'Configured' if cls.SLACK_WEBHOOK_URL else 'Not Set'}")
        print(f"  Debug Mode:          {cls.DEBUG}")
        print("=" * 50)
