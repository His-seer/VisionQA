"""
VisionQA Notifier
Sends notifications to Slack and generic webhooks.
Includes TTL-based deduplication to prevent duplicate notifications on retries.
"""

import json
import time

import httpx

from config import Config


PERSONA_PREFIX = "\033[94m[VisionQA Notify]\033[0m"


def _narrate(message: str):
    print(f"{PERSONA_PREFIX} {message}")


class Notifier:
    """Sends notifications via Slack webhooks and generic HTTP webhooks."""

    _DEDUP_TTL = 300  # 5 minutes

    def __init__(self):
        self._recent_notifications: dict[str, float] = {}

    def _is_duplicate(self, bug_id: str) -> bool:
        """Check if this bug_id was recently notified. Prunes expired entries."""
        now = time.time()
        expired = [k for k, v in self._recent_notifications.items() if now - v > self._DEDUP_TTL]
        for k in expired:
            del self._recent_notifications[k]
        return bug_id in self._recent_notifications

    def _mark_processed(self, bug_id: str):
        """Mark a bug_id as recently notified."""
        self._recent_notifications[bug_id] = time.time()

    def send_slack(self, message: str, analysis_result=None) -> dict:
        """Send a notification to Slack via incoming webhook."""
        if not Config.SLACK_WEBHOOK_URL:
            _narrate("⏭️ Slack webhook not configured. Skipping.")
            return {"status": "skipped", "reason": "SLACK_WEBHOOK_URL not set"}

        # Dedup by bug_id if an analysis_result is provided
        if analysis_result and hasattr(analysis_result, "bug_id"):
            if self._is_duplicate(analysis_result.bug_id):
                _narrate(f"⏭️ Duplicate notification for {analysis_result.bug_id}. Skipping.")
                return {"status": "skipped", "reason": "duplicate"}

        _narrate("📨 Sending Slack notification...")

        # Build a rich Slack message
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔍 VisionQA Report", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if analysis_result:
            status_emoji = {"PASS": "✅", "FAIL": "🚨", "NEEDS_REVIEW": "⚠️"}.get(
                analysis_result.status, "❓"
            )
            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* {status_emoji} {analysis_result.status}"},
                    {"type": "mrkdwn", "text": f"*Severity:* {analysis_result.severity}"},
                    {"type": "mrkdwn", "text": f"*Confidence:* {analysis_result.confidence:.0%}"},
                    {"type": "mrkdwn", "text": f"*Bug ID:* {analysis_result.bug_id}"},
                ],
            })

        payload = {"blocks": blocks, "text": message}

        try:
            response = httpx.post(
                Config.SLACK_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                _narrate("✅ Slack notification sent.")
                if analysis_result and hasattr(analysis_result, "bug_id"):
                    self._mark_processed(analysis_result.bug_id)
                return {"status": "success"}
            else:
                _narrate(f"⚠️ Slack responded with {response.status_code}")
                return {"status": "error", "response_code": response.status_code}

        except Exception as e:
            _narrate(f"❌ Slack notification failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def send_generic_webhook(self, payload: dict, url: str) -> dict:
        """Send a payload to any generic webhook URL."""
        _narrate(f"📤 Sending webhook to: {url[:50]}...")

        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code in (200, 201, 202):
                _narrate("✅ Webhook delivered.")
                return {"status": "success", "response_code": response.status_code}
            else:
                _narrate(f"⚠️ Webhook responded with {response.status_code}")
                return {"status": "error", "response_code": response.status_code}

        except Exception as e:
            _narrate(f"❌ Webhook failed: {str(e)}")
            return {"status": "error", "error": str(e)}
