"""
VisionQA Test Suite
Integration tests for the Visual QA Agent, API, and core pipeline.
"""

import os
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from fastapi.testclient import TestClient

# ── Test configuration ──────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Ensure fixtures directory exists
FIXTURES_DIR.mkdir(exist_ok=True)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_screenshot(tmp_path_factory):
    """Create a minimal PNG image to use as a test screenshot."""
    from PIL import Image, ImageDraw

    tmp = tmp_path_factory.mktemp("screenshots")
    img_path = tmp / "test_page.png"

    # Create a synthetic "page" with a button and text
    img = Image.new("RGB", (1280, 720), color="#f0f0f0")
    draw = ImageDraw.Draw(img)

    # Draw a header bar
    draw.rectangle([0, 0, 1280, 60], fill="#1a73e8")
    draw.text((20, 20), "VisionQA Test App", fill="white")

    # Draw a green "Add to Cart" button
    draw.rectangle([540, 320, 740, 370], fill="#34a853")
    draw.text((560, 335), "Add to Cart", fill="white")

    # Draw some body text
    draw.text((200, 200), "Product: Widget Pro", fill="#333333")
    draw.text((200, 230), "Price: $29.99", fill="#333333")

    img.save(str(img_path))
    return str(img_path)


@pytest.fixture(scope="module")
def broken_screenshot(tmp_path_factory):
    """Create a screenshot with the button clipped/hidden."""
    from PIL import Image, ImageDraw

    tmp = tmp_path_factory.mktemp("screenshots_broken")
    img_path = tmp / "broken_page.png"

    img = Image.new("RGB", (1280, 720), color="#f0f0f0")
    draw = ImageDraw.Draw(img)

    # Draw red error banner covering the button area
    draw.rectangle([0, 300, 1280, 420], fill="#d93025")
    draw.text((480, 350), "Error: Failed to load component", fill="white")

    img.save(str(img_path))
    return str(img_path)


def _make_analysis_result(status="FAIL", analysis="Bug found", confidence=0.92,
                          observations=None, severity="HIGH", instruction="Check button"):
    """Helper to create AnalysisResult instances for tests."""
    from vision.visual_qa_agent import AnalysisResult
    return AnalysisResult(
        status=status, analysis=analysis, confidence=confidence,
        observations=observations or ["Observation 1"], severity=severity,
        instruction=instruction,
    )


# ── Unit Tests: AnalysisResult ──────────────────────────────────────

class TestAnalysisResult:
    def test_is_bug_on_fail(self):
        from vision.visual_qa_agent import AnalysisResult
        result = AnalysisResult(
            status="FAIL", analysis="Button hidden", confidence=0.92,
            observations=[], severity="HIGH"
        )
        assert result.is_bug() is True

    def test_is_not_bug_on_pass(self):
        from vision.visual_qa_agent import AnalysisResult
        result = AnalysisResult(
            status="PASS", analysis="Button visible", confidence=0.96,
            observations=[], severity="INFO"
        )
        assert result.is_bug() is False

    def test_needs_review_on_low_confidence(self):
        from vision.visual_qa_agent import AnalysisResult
        result = AnalysisResult(
            status="NEEDS_REVIEW", analysis="Unclear", confidence=0.6,
            observations=[], severity="INFO"
        )
        assert result.needs_review() is True

    def test_to_dict_has_required_keys(self):
        from vision.visual_qa_agent import AnalysisResult
        result = AnalysisResult(
            status="PASS", analysis="All good", confidence=0.95,
            observations=["Button found"], severity="INFO",
            instruction="Check button"
        )
        d = result.to_dict()
        for key in ["bugId", "status", "severity", "confidence", "analysis", "observations", "timestamp"]:
            assert key in d


# ── Unit Tests: BaselineManager ─────────────────────────────────────

class TestBaselineManager:
    def test_save_and_retrieve_baseline(self, sample_screenshot, tmp_path):
        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "baselines"))
        path = bm.save_baseline("test_page", sample_screenshot)
        assert os.path.exists(path)
        assert bm.has_baseline("test_page")

    def test_compare_identical_is_pass(self, sample_screenshot, tmp_path):
        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "baselines2"))
        bm.save_baseline("homepage", sample_screenshot)
        result = bm.compare("homepage", sample_screenshot)
        assert result["status"] == "PASS"
        assert result["diff_percentage"] == 0.0

    def test_compare_different_is_fail(self, sample_screenshot, broken_screenshot, tmp_path):
        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "baselines3"))
        bm.save_baseline("homepage", sample_screenshot)
        result = bm.compare("homepage", broken_screenshot)
        assert result["status"] == "FAIL"
        assert result["diff_percentage"] > 5.0

    def test_new_baseline_when_missing(self, sample_screenshot, tmp_path):
        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "baselines4"))
        result = bm.compare("nonexistent", sample_screenshot)
        assert result["status"] == "NEW_BASELINE"


# ── Unit Tests: BaselineManager GCS ─────────────────────────────────

class TestBaselineManagerGCS:
    @patch("vision.baseline_manager._HAS_GCS", True)
    @patch("vision.baseline_manager.gcs")
    def test_save_uploads_to_gcs(self, mock_gcs, sample_screenshot, tmp_path):
        """Verify save_baseline uploads to GCS when available."""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs.Client.return_value.bucket.return_value = mock_bucket

        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "gcs_baselines"))
        bm._gcs_bucket = mock_bucket

        bm.save_baseline("test_gcs", sample_screenshot)
        mock_bucket.blob.assert_called_once_with("baselines/test_gcs.png")
        mock_blob.upload_from_filename.assert_called_once()

    @patch("vision.baseline_manager._HAS_GCS", True)
    @patch("vision.baseline_manager.gcs")
    def test_compare_downloads_from_gcs_when_local_missing(self, mock_gcs, sample_screenshot, tmp_path):
        """Verify compare downloads from GCS when local baseline is missing."""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_gcs.Client.return_value.bucket.return_value = mock_bucket

        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "gcs_baselines2"))
        bm._gcs_bucket = mock_bucket

        # The download side-effect copies the sample screenshot to simulate GCS download
        def download_side_effect(filename):
            import shutil
            shutil.copy2(sample_screenshot, filename)

        mock_blob.download_to_filename.side_effect = download_side_effect

        result = bm.compare("from_gcs", sample_screenshot)
        mock_blob.download_to_filename.assert_called_once()
        assert result["status"] == "PASS"

    def test_fallback_when_gcs_unavailable(self, sample_screenshot, tmp_path):
        """Verify local-only behavior when GCS bucket is None."""
        from vision.baseline_manager import BaselineManager
        bm = BaselineManager(baselines_dir=str(tmp_path / "local_only"))
        assert bm._gcs_bucket is None

        # Should work fine with local storage only
        bm.save_baseline("local_test", sample_screenshot)
        assert bm.has_baseline("local_test")


# ── Unit Tests: ReportGenerator ─────────────────────────────────────

class TestReportGenerator:
    def test_report_created(self, tmp_path):
        from workflow.report_generator import ReportGenerator
        from vision.visual_qa_agent import AnalysisResult

        rg = ReportGenerator(output_dir=str(tmp_path / "reports"))
        results = [
            AnalysisResult("PASS", "Button visible", 0.95, ["Nav bar present"], "INFO", instruction="Check nav"),
            AnalysisResult("FAIL", "Button clipped", 0.91, ["Footer overlap"], "HIGH", instruction="Check footer"),
        ]
        path = rg.generate_markdown_report(results, title="Test Report")
        assert os.path.exists(path)

        content = open(path, encoding="utf-8").read()
        assert "# Test Report" in content
        assert "PASS" in content
        assert "FAIL" in content
        assert "Pass Rate" in content

    def test_report_has_executive_summary(self, tmp_path):
        from workflow.report_generator import ReportGenerator
        from vision.visual_qa_agent import AnalysisResult

        rg = ReportGenerator(output_dir=str(tmp_path / "reports2"))
        results = [AnalysisResult("PASS", "OK", 0.98, [], "INFO")]
        path = rg.generate_markdown_report(results)
        content = open(path, encoding="utf-8").read()
        assert "Executive Summary" in content
        assert "VERDICT" in content


class TestHTMLReport:
    def test_html_report_created(self, tmp_path):
        from workflow.report_generator import ReportGenerator

        rg = ReportGenerator(output_dir=str(tmp_path / "html_reports"))
        results = [
            _make_analysis_result("PASS", "All good", 0.95, severity="INFO"),
            _make_analysis_result("FAIL", "Button missing", 0.90, severity="HIGH"),
        ]
        path = rg.generate_html_report(results, title="HTML Test Report")
        assert os.path.exists(path)
        assert path.endswith(".html")

    def test_html_report_contains_results(self, tmp_path):
        from workflow.report_generator import ReportGenerator

        rg = ReportGenerator(output_dir=str(tmp_path / "html_reports2"))
        results = [_make_analysis_result("FAIL", "Error found", 0.88, severity="CRITICAL")]
        path = rg.generate_html_report(results, title="Bug Report")

        content = open(path, encoding="utf-8").read()
        assert "<html" in content
        assert "Bug Report" in content
        assert "FAIL" in content
        assert "CRITICAL" in content


# ── Integration Tests: Visual QA Agent (mocked Gemini) ──────────────

class TestVisualQAAgent:
    @patch("vision.visual_qa_agent.genai.Client")
    def test_analyze_returns_pass(self, mock_client_cls, sample_screenshot):
        """Test that the agent correctly parses a PASS response from Gemini."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "observation": "The Add to Cart button is clearly visible.",
            "reasoning": "Button is present and unobscured.",
            "status": "PASS",
            "analysis": "Add to Cart button is fully visible and enabled.",
            "confidence": 0.96,
            "severity": "INFO",
            "observations": ["Green button found at center", "No overlapping elements"],
            "visual_evidence": "Green rectangle labeled 'Add to Cart' at (540,320)-(740,370)",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.visual_qa_agent import VisualQAAgent
        agent = VisualQAAgent()
        result = agent.analyze(sample_screenshot, "Verify the Add to Cart button is visible")

        assert result.status == "PASS"
        assert result.confidence == 0.96
        assert result.is_bug() is False

    @patch("vision.visual_qa_agent.genai.Client")
    def test_analyze_returns_fail(self, mock_client_cls, broken_screenshot):
        """Test that the agent correctly parses a FAIL response from Gemini."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "observation": "A red error banner covers the page content.",
            "reasoning": "The button is not visible due to the error overlay.",
            "status": "FAIL",
            "analysis": "Add to Cart button is hidden by an error banner.",
            "confidence": 0.94,
            "severity": "CRITICAL",
            "observations": ["Red error banner at center", "Button not visible"],
            "visual_evidence": "Red rectangle at (0,300)-(1280,420) with error text",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.visual_qa_agent import VisualQAAgent
        agent = VisualQAAgent()
        result = agent.analyze(broken_screenshot, "Verify the Add to Cart button is visible")

        assert result.status == "FAIL"
        assert result.severity == "CRITICAL"
        assert result.is_bug() is True

    @patch("vision.visual_qa_agent.genai.Client")
    def test_low_confidence_triggers_needs_review(self, mock_client_cls, sample_screenshot):
        """Test that low confidence is gated to NEEDS_REVIEW."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "status": "PASS",
            "analysis": "Uncertain.",
            "confidence": 0.50,
            "severity": "INFO",
            "observations": [],
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.visual_qa_agent import VisualQAAgent
        agent = VisualQAAgent()
        result = agent.analyze(sample_screenshot, "Check something ambiguous")

        assert result.status == "NEEDS_REVIEW"
        assert result.needs_review() is True


# ── Unit Tests: Critic ──────────────────────────────────────────────

class TestCritic:
    @patch("vision.critic.genai.Client")
    def test_review_confirmed(self, mock_client_cls, sample_screenshot):
        """Test that a confirmed review returns CONFIRMED status."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "review_status": "CONFIRMED",
            "hallucinations_found": False,
            "hallucination_details": "",
            "missed_defects": [],
            "confidence_justified": True,
            "adjusted_confidence": 0.95,
            "critique": "Analysis is accurate.",
            "recommendation": "ACCEPT",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.critic import Critic
        critic = Critic()
        result = critic.review(sample_screenshot, {"status": "PASS", "confidence": 0.95})

        assert result["review_status"] == "CONFIRMED"
        assert result["hallucinations_found"] is False

    @patch("vision.critic.genai.Client")
    def test_review_detects_hallucination(self, mock_client_cls, sample_screenshot):
        """Test that hallucinations are detected and flagged."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "review_status": "DISPUTED",
            "hallucinations_found": True,
            "hallucination_details": "Analysis mentions a dropdown that is not visible.",
            "missed_defects": [],
            "confidence_justified": False,
            "adjusted_confidence": 0.3,
            "critique": "Primary analysis hallucinated a UI element.",
            "recommendation": "REJECT",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.critic import Critic
        critic = Critic()
        result = critic.review(sample_screenshot, {"status": "FAIL", "confidence": 0.9})

        assert result["hallucinations_found"] is True
        assert result["recommendation"] == "REJECT"

    @patch("vision.critic.genai.Client")
    def test_review_adjusts_confidence(self, mock_client_cls, sample_screenshot):
        """Test that the critic can lower confidence."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "review_status": "ADJUSTED",
            "hallucinations_found": False,
            "adjusted_confidence": 0.70,
            "critique": "Confidence seems high for ambiguous screenshot.",
            "recommendation": "LOWER_CONFIDENCE",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.critic import Critic
        critic = Critic()
        result = critic.review(sample_screenshot, {"status": "PASS", "confidence": 0.95})

        assert result["adjusted_confidence"] == 0.70

    @patch("vision.critic.genai.Client")
    def test_review_handles_malformed_json(self, mock_client_cls, sample_screenshot):
        """Test fallback behavior on malformed Gemini response."""
        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON at all!!"
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from vision.critic import Critic
        critic = Critic()
        result = critic.review(sample_screenshot, {"status": "PASS", "confidence": 0.9})

        assert result["review_status"] == "ADJUSTED"
        assert result["adjusted_confidence"] == 0.5

    @patch("vision.critic.genai.Client")
    def test_critic_uses_pro_model(self, mock_client_cls):
        """Test that Critic uses GEMINI_PRO_MODEL by default."""
        from vision.critic import Critic
        from config import Config
        critic = Critic()
        assert critic.model == Config.GEMINI_PRO_MODEL


# ── Unit Tests: Notifier ────────────────────────────────────────────

class TestNotifier:
    @patch("workflow.notifier.httpx.post")
    def test_send_slack_success(self, mock_post, monkeypatch):
        """Test successful Slack notification."""
        monkeypatch.setattr("config.Config.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        mock_post.return_value = MagicMock(status_code=200)

        from workflow.notifier import Notifier
        notifier = Notifier()
        result = notifier.send_slack("Test message")

        assert result["status"] == "success"
        mock_post.assert_called_once()

    def test_send_slack_skipped_when_not_configured(self, monkeypatch):
        """Test that Slack is skipped when URL is not set."""
        monkeypatch.setattr("config.Config.SLACK_WEBHOOK_URL", "")

        from workflow.notifier import Notifier
        notifier = Notifier()
        result = notifier.send_slack("Test message")

        assert result["status"] == "skipped"

    @patch("workflow.notifier.httpx.post")
    def test_send_slack_with_analysis_result(self, mock_post, monkeypatch):
        """Test Slack notification includes analysis result details."""
        monkeypatch.setattr("config.Config.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        mock_post.return_value = MagicMock(status_code=200)

        from workflow.notifier import Notifier
        notifier = Notifier()
        analysis = _make_analysis_result()
        result = notifier.send_slack("Bug found", analysis_result=analysis)

        assert result["status"] == "success"
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(payload["blocks"]) == 3  # header + message + fields

    @patch("workflow.notifier.httpx.post")
    def test_send_slack_handles_http_error(self, mock_post, monkeypatch):
        """Test Slack error handling on HTTP 500."""
        monkeypatch.setattr("config.Config.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        mock_post.return_value = MagicMock(status_code=500)

        from workflow.notifier import Notifier
        notifier = Notifier()
        result = notifier.send_slack("Test message")

        assert result["status"] == "error"

    @patch("workflow.notifier.httpx.post")
    def test_send_generic_webhook_success(self, mock_post):
        """Test successful generic webhook delivery."""
        mock_post.return_value = MagicMock(status_code=201)

        from workflow.notifier import Notifier
        notifier = Notifier()
        result = notifier.send_generic_webhook({"data": "test"}, "https://example.com/hook")

        assert result["status"] == "success"
        assert result["response_code"] == 201


# ── Unit Tests: TicketGenerator ─────────────────────────────────────

class TestTicketGenerator:
    def test_create_ticket_structure(self):
        """Test that create_ticket returns a properly structured ticket."""
        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        analysis = _make_analysis_result()
        ticket = tg.create_ticket(analysis)

        for key in ["bugId", "severity", "title", "analysis", "observations",
                     "reproductionSteps", "timestamp", "confidence"]:
            assert key in ticket

    def test_create_ticket_title_format(self):
        """Test ticket title follows [VisionQA] format."""
        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        analysis = _make_analysis_result(severity="CRITICAL")
        ticket = tg.create_ticket(analysis)

        assert ticket["title"].startswith("[VisionQA]")
        assert "CRITICAL" in ticket["title"]

    def test_push_to_jira_skipped(self, monkeypatch):
        """Test Jira push is skipped when URL not configured."""
        monkeypatch.setattr("config.Config.JIRA_WEBHOOK_URL", "")

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())
        result = tg.push_to_jira(ticket)

        assert result["status"] == "skipped"

    @patch("workflow.ticket_generator.httpx.post")
    def test_push_to_jira_success(self, mock_post, monkeypatch):
        """Test successful Jira ticket push."""
        monkeypatch.setattr("config.Config.JIRA_WEBHOOK_URL", "https://jira.example.com/hook")
        mock_post.return_value = MagicMock(status_code=201)

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())
        result = tg.push_to_jira(ticket)

        assert result["status"] == "success"

    def test_push_to_github_skipped(self, monkeypatch):
        """Test GitHub push is skipped when not configured."""
        monkeypatch.setattr("config.Config.GITHUB_TOKEN", "")
        monkeypatch.setattr("config.Config.GITHUB_REPO", "")

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())
        result = tg.push_to_github(ticket)

        assert result["status"] == "skipped"

    @patch("workflow.ticket_generator.httpx.post")
    def test_push_to_github_success(self, mock_post, monkeypatch):
        """Test successful GitHub issue creation."""
        monkeypatch.setattr("config.Config.GITHUB_TOKEN", "ghp_test")
        monkeypatch.setattr("config.Config.GITHUB_REPO", "owner/repo")
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"html_url": "https://github.com/owner/repo/issues/1"},
        )

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())
        result = tg.push_to_github(ticket)

        assert result["status"] == "success"
        assert "url" in result

    def test_save_ticket_json(self, tmp_path):
        """Test local JSON ticket file creation."""
        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())
        filepath = tg.save_ticket_json(ticket, output_dir=str(tmp_path))

        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["bugId"] == ticket["bugId"]

    @patch("workflow.ticket_generator.httpx.post")
    def test_push_to_jira_dedup(self, mock_post, monkeypatch):
        """Test that pushing the same ticket twice deduplicates."""
        monkeypatch.setattr("config.Config.JIRA_WEBHOOK_URL", "https://jira.example.com/hook")
        mock_post.return_value = MagicMock(status_code=201)

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())

        result1 = tg.push_to_jira(ticket)
        assert result1["status"] == "success"

        result2 = tg.push_to_jira(ticket)
        assert result2["status"] == "skipped"
        assert result2["reason"] == "duplicate"

    @patch("workflow.ticket_generator.httpx.post")
    def test_push_to_github_dedup(self, mock_post, monkeypatch):
        """Test that pushing the same ticket twice to GitHub deduplicates."""
        monkeypatch.setattr("config.Config.GITHUB_TOKEN", "ghp_test")
        monkeypatch.setattr("config.Config.GITHUB_REPO", "owner/repo")
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"html_url": "https://github.com/owner/repo/issues/1"},
        )

        from workflow.ticket_generator import TicketGenerator
        tg = TicketGenerator()
        ticket = tg.create_ticket(_make_analysis_result())

        result1 = tg.push_to_github(ticket)
        assert result1["status"] == "success"

        result2 = tg.push_to_github(ticket)
        assert result2["status"] == "skipped"
        assert result2["reason"] == "duplicate"


# ── Unit Tests: WorkflowAutomator ──────────────────────────────────

class TestWorkflowAutomator:
    @patch("workflow.automator.Notifier")
    @patch("workflow.automator.TicketGenerator")
    def test_on_bug_found_calls_all_steps(self, MockTicketGen, MockNotifier):
        """Test that on_bug_found triggers all workflow steps."""
        mock_tg = MockTicketGen.return_value
        mock_tg.create_ticket.return_value = {"bugId": "VQA-TEST", "severity": "HIGH",
                                               "analysis": "Bug", "confidence": 0.9}
        mock_tg.save_ticket_json.return_value = "/tmp/test.json"
        mock_tg.push_to_jira.return_value = {"status": "skipped"}
        mock_tg.push_to_github.return_value = {"status": "skipped"}
        MockNotifier.return_value.send_slack.return_value = {"status": "skipped"}

        from workflow.automator import WorkflowAutomator
        automator = WorkflowAutomator()
        analysis = _make_analysis_result()
        result = automator.on_bug_found(analysis)

        mock_tg.create_ticket.assert_called_once()
        mock_tg.save_ticket_json.assert_called_once()
        mock_tg.push_to_jira.assert_called_once()
        mock_tg.push_to_github.assert_called_once()
        MockNotifier.return_value.send_slack.assert_called_once()

    @patch("workflow.automator.Notifier")
    @patch("workflow.automator.TicketGenerator")
    def test_on_bug_found_returns_results_dict(self, MockTicketGen, MockNotifier):
        """Test the returned dict structure."""
        mock_tg = MockTicketGen.return_value
        mock_tg.create_ticket.return_value = {"bugId": "VQA-TEST"}
        mock_tg.save_ticket_json.return_value = "/tmp/test.json"
        mock_tg.push_to_jira.return_value = {"status": "skipped"}
        mock_tg.push_to_github.return_value = {"status": "skipped"}
        MockNotifier.return_value.send_slack.return_value = {"status": "skipped"}

        from workflow.automator import WorkflowAutomator
        automator = WorkflowAutomator()
        result = automator.on_bug_found(_make_analysis_result())

        for key in ["ticket", "local_json", "jira", "github", "slack"]:
            assert key in result

    @patch("workflow.automator.Notifier")
    @patch("workflow.automator.TicketGenerator")
    @patch("workflow.automator.ReportGenerator")
    def test_process_results_generates_report(self, MockReportGen, MockTicketGen, MockNotifier):
        """Test that process_results generates a report for passing results."""
        MockReportGen.return_value.generate_markdown_report.return_value = "/tmp/report.md"
        MockReportGen.return_value.generate_html_report.return_value = "/tmp/report.html"

        from workflow.automator import WorkflowAutomator
        automator = WorkflowAutomator()
        results = [_make_analysis_result("PASS", severity="INFO")]
        workflow_result = automator.process_results(results)

        MockReportGen.return_value.generate_markdown_report.assert_called_once()
        MockReportGen.return_value.generate_html_report.assert_called_once()
        assert workflow_result["report"] is not None
        assert len(workflow_result["bugs_processed"]) == 0

    @patch("workflow.automator.Notifier")
    @patch("workflow.automator.TicketGenerator")
    @patch("workflow.automator.ReportGenerator")
    def test_process_results_triggers_bug_workflow_on_failure(self, MockReportGen, MockTicketGen, MockNotifier):
        """Test that failures trigger the bug workflow."""
        MockReportGen.return_value.generate_markdown_report.return_value = "/tmp/report.md"
        MockReportGen.return_value.generate_html_report.return_value = "/tmp/report.html"
        mock_tg = MockTicketGen.return_value
        mock_tg.create_ticket.return_value = {"bugId": "VQA-TEST", "severity": "HIGH",
                                               "analysis": "Bug", "confidence": 0.9}
        mock_tg.save_ticket_json.return_value = "/tmp/test.json"
        mock_tg.push_to_jira.return_value = {"status": "skipped"}
        mock_tg.push_to_github.return_value = {"status": "skipped"}
        MockNotifier.return_value.send_slack.return_value = {"status": "skipped"}

        from workflow.automator import WorkflowAutomator
        automator = WorkflowAutomator()
        results = [_make_analysis_result("FAIL")]
        workflow_result = automator.process_results(results)

        assert len(workflow_result["bugs_processed"]) == 1
        mock_tg.create_ticket.assert_called_once()


# ── Unit Tests: WebNavigator ────────────────────────────────────────

class TestWebNavigator:
    @patch("navigator.web_navigator.PageAnalyzer")
    @patch("navigator.web_navigator.webdriver.Chrome")
    def test_start_creates_driver(self, mock_chrome, mock_analyzer):
        """Test that start() creates a Chrome WebDriver."""
        from navigator.web_navigator import WebNavigator
        nav = WebNavigator(headless=True)
        nav.start()

        mock_chrome.assert_called_once()
        nav.stop()

    @patch("navigator.web_navigator.PageAnalyzer")
    @patch("navigator.web_navigator.webdriver.Chrome")
    def test_stop_quits_driver(self, mock_chrome, mock_analyzer):
        """Test that stop() calls driver.quit()."""
        from navigator.web_navigator import WebNavigator
        nav = WebNavigator(headless=True)
        nav.start()
        nav.stop()

        mock_chrome.return_value.quit.assert_called_once()

    @patch("navigator.web_navigator.PageAnalyzer")
    @patch("navigator.web_navigator.webdriver.Chrome")
    def test_take_screenshot(self, mock_chrome, mock_analyzer, tmp_path):
        """Test that take_screenshot saves a file."""
        mock_chrome.return_value.save_screenshot.return_value = True

        from navigator.web_navigator import WebNavigator
        nav = WebNavigator(headless=True)
        nav.start()
        nav.screenshot_dir = str(tmp_path)

        # Mock save_screenshot to create a file
        def save_side_effect(path):
            from PIL import Image
            img = Image.new("RGB", (100, 100), "white")
            img.save(path)
            return True

        mock_chrome.return_value.save_screenshot.side_effect = save_side_effect
        path = nav.take_screenshot("test_capture")

        assert "test_capture" in path
        nav.stop()

    @patch("navigator.web_navigator.PageAnalyzer")
    @patch("navigator.web_navigator.webdriver.Chrome")
    def test_perform_action_skips_low_confidence(self, mock_chrome, mock_analyzer_cls):
        """Test that low-confidence actions are skipped."""
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.find_element_by_intent.return_value = {
            "target_element": {"label": "button"},
            "action": {"type": "click"},
            "confidence": 0.3,
            "reasoning": "Uncertain match",
        }
        # Mock save_screenshot
        def save_side_effect(path):
            from PIL import Image
            img = Image.new("RGB", (100, 100), "white")
            img.save(path)
            return True

        mock_chrome.return_value.save_screenshot.side_effect = save_side_effect

        from navigator.web_navigator import WebNavigator
        nav = WebNavigator(headless=True)
        nav.start()

        result = nav.perform_action("Click the invisible button")
        assert result["status"] == "skipped"
        nav.stop()

    @patch("navigator.web_navigator.PageAnalyzer")
    @patch("navigator.web_navigator.webdriver.Chrome")
    def test_context_manager(self, mock_chrome, mock_analyzer):
        """Test context manager calls start and stop."""
        from navigator.web_navigator import WebNavigator
        with WebNavigator(headless=True) as nav:
            mock_chrome.assert_called_once()

        mock_chrome.return_value.quit.assert_called_once()


# ── Unit Tests: PageAnalyzer ────────────────────────────────────────

class TestPageAnalyzer:
    @patch("navigator.page_analyzer.genai.Client")
    def test_detect_elements_returns_structure(self, mock_client_cls, sample_screenshot):
        """Test that detect_elements returns a properly structured dict."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "page_title": "Test Page",
            "elements": [
                {"type": "button", "label": "Add to Cart", "location": "center",
                 "description": "Purchase button", "is_visible": True, "is_enabled": True}
            ],
            "page_state": "loaded",
            "observations": ["Page fully loaded"],
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from navigator.page_analyzer import PageAnalyzer
        analyzer = PageAnalyzer()
        result = analyzer.detect_elements(sample_screenshot)

        assert "page_title" in result
        assert "elements" in result
        assert len(result["elements"]) > 0

    @patch("navigator.page_analyzer.genai.Client")
    def test_find_element_by_intent_returns_target(self, mock_client_cls, sample_screenshot):
        """Test that find_element_by_intent returns action and target."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "target_element": {
                "type": "button", "label": "Add to Cart",
                "location": "center", "css_hints": ".add-to-cart-btn"
            },
            "action": {"type": "click", "value": "", "description": "Click Add to Cart button"},
            "confidence": 0.95,
            "reasoning": "Green button with text 'Add to Cart'",
        })
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        from navigator.page_analyzer import PageAnalyzer
        analyzer = PageAnalyzer()
        result = analyzer.find_element_by_intent("Click the Add to Cart button", sample_screenshot)

        assert "target_element" in result
        assert "action" in result
        assert result["confidence"] == 0.95

    def test_is_page_stable_identical_images(self, sample_screenshot):
        """Test that identical screenshots are detected as stable."""
        from navigator.page_analyzer import PageAnalyzer
        analyzer = PageAnalyzer.__new__(PageAnalyzer)  # Skip __init__ (no API key needed)
        result = analyzer.is_page_stable(sample_screenshot, sample_screenshot)

        assert result["is_stable"] is True
        assert result["diff_percentage"] == 0.0

    def test_is_page_stable_different_images(self, sample_screenshot, broken_screenshot):
        """Test that different screenshots are detected as unstable."""
        from navigator.page_analyzer import PageAnalyzer
        analyzer = PageAnalyzer.__new__(PageAnalyzer)  # Skip __init__
        result = analyzer.is_page_stable(sample_screenshot, broken_screenshot)

        assert result["is_stable"] is False
        assert result["diff_percentage"] > 2.0


# ── Integration Tests: API ──────────────────────────────────────────

class TestAPI:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-placeholder")

    @pytest.fixture()
    def client(self, set_env):
        from api.server import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "confidence_threshold" in data

    @patch("api.server.qa_agent")
    def test_verify_endpoint_pass(self, mock_agent, client, sample_screenshot):
        from vision.visual_qa_agent import AnalysisResult
        mock_result = AnalysisResult(
            status="PASS", analysis="Button visible", confidence=0.95,
            observations=["Button found"], severity="INFO",
            screenshot_path=sample_screenshot, instruction="Check button"
        )
        mock_agent.analyze.return_value = mock_result

        with open(sample_screenshot, "rb") as f:
            response = client.post(
                "/v1/agent/verify",
                files={"screenshot": ("test.png", f, "image/png")},
                data={"instruction": "Verify the Add to Cart button is visible"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PASS"
        assert data["confidence"] == 0.95
        assert "bug_id" in data

    def test_verify_rejects_non_image(self, client):
        response = client.post(
            "/v1/agent/verify",
            files={"screenshot": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
            data={"instruction": "Check something"},
        )
        assert response.status_code == 400


class TestRateLimiting:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-placeholder")

    @patch("api.server.qa_agent")
    def test_rate_limit_exceeded(self, mock_agent, sample_screenshot):
        """Test that rate limiting kicks in after exceeding the limit."""
        from api.server import app
        from vision.visual_qa_agent import AnalysisResult

        mock_result = AnalysisResult(
            status="PASS", analysis="OK", confidence=0.95,
            observations=[], severity="INFO", instruction="Check"
        )
        mock_agent.analyze.return_value = mock_result

        client = TestClient(app)

        # Send requests up to the limit — rate limit is 10/minute
        last_status = None
        for i in range(12):
            with open(sample_screenshot, "rb") as f:
                response = client.post(
                    "/v1/agent/verify",
                    files={"screenshot": ("test.png", f, "image/png")},
                    data={"instruction": "Check"},
                )
            last_status = response.status_code
            if response.status_code == 429:
                break

        # At some point we should hit 429
        assert last_status == 429
