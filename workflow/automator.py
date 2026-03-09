"""
VisionQA Workflow Automator
Orchestrates the full workflow: bug detection → ticketing → notification → reporting.
"""

from config import Config
from workflow.ticket_generator import TicketGenerator
from workflow.notifier import Notifier
from workflow.report_generator import ReportGenerator


PERSONA_PREFIX = "\033[96m[VisionQA Workflow]\033[0m"


def _narrate(message: str):
    print(f"{PERSONA_PREFIX} {message}")


class WorkflowAutomator:
    """
    The 'Glue' layer — sits on top of the Visual QA Agent and triggers
    downstream actions when bugs are found.
    """

    def __init__(self):
        self.ticket_gen = TicketGenerator()
        self.notifier = Notifier()
        self.report_gen = ReportGenerator()

    def on_bug_found(self, analysis_result) -> dict:
        """
        Full workflow trigger when a bug is detected.
        1. Create a structured ticket
        2. Push to Jira / GitHub Issues
        3. Send Slack notification
        4. Save local JSON
        """
        _narrate("=" * 60)
        _narrate(f"🚨 BUG WORKFLOW TRIGGERED — {analysis_result.bug_id}")
        _narrate("=" * 60)

        results = {}

        # Step 1: Create ticket
        _narrate("\n📋 Step 1: Creating bug ticket...")
        ticket = self.ticket_gen.create_ticket(analysis_result)
        results["ticket"] = ticket

        # Step 2: Save locally
        _narrate("\n💾 Step 2: Saving ticket locally...")
        json_path = self.ticket_gen.save_ticket_json(ticket)
        results["local_json"] = json_path

        # Step 3: Push to Jira
        _narrate("\n📤 Step 3: Pushing to Jira...")
        jira_result = self.ticket_gen.push_to_jira(ticket)
        results["jira"] = jira_result

        # Step 4: Push to GitHub Issues
        _narrate("\n📤 Step 4: Pushing to GitHub Issues...")
        github_result = self.ticket_gen.push_to_github(ticket)
        results["github"] = github_result

        # Step 5: Slack notification
        _narrate("\n📨 Step 5: Sending Slack notification...")
        slack_message = (
            f"🚨 *VisionQA Bug Detected*\n"
            f"*ID:* {analysis_result.bug_id}\n"
            f"*Severity:* {analysis_result.severity}\n"
            f"*Analysis:* {analysis_result.analysis[:200]}\n"
            f"*Confidence:* {analysis_result.confidence:.0%}"
        )
        slack_result = self.notifier.send_slack(slack_message, analysis_result)
        results["slack"] = slack_result

        _narrate("\n" + "=" * 60)
        _narrate("✅ Bug workflow complete.")
        _narrate("=" * 60)

        return results

    def process_results(self, results: list, report_title: str = "VisionQA Test Report") -> dict:
        """
        Process a batch of analysis results:
        - Generate report for all results
        - Trigger bug workflow for any failures
        """
        _narrate(f"📦 Processing {len(results)} analysis results...")

        workflow_results = {
            "report": None,
            "bugs_processed": [],
        }

        # Generate reports for all results
        _narrate("\n📝 Generating test reports...")
        report_path = self.report_gen.generate_markdown_report(results, title=report_title)
        html_path = self.report_gen.generate_html_report(results, title=report_title)
        workflow_results["report"] = report_path
        workflow_results["html_report"] = html_path

        # Process each failure
        failures = [r for r in results if r.is_bug()]
        if failures:
            _narrate(f"\n🚨 {len(failures)} failure(s) detected. Triggering bug workflows...")
            for failure in failures:
                bug_result = self.on_bug_found(failure)
                workflow_results["bugs_processed"].append(bug_result)
        else:
            _narrate("✅ No failures detected. No bug workflows triggered.")

        # Process reviews
        reviews = [r for r in results if r.needs_review()]
        if reviews:
            _narrate(f"\n🔶 {len(reviews)} check(s) flagged for human review.")

        return workflow_results
