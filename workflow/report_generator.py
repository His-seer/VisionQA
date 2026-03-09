"""
VisionQA Report Generator
Produces structured Markdown and HTML test reports from analysis results.
"""

import os
import base64
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from config import Config


PERSONA_PREFIX = "\033[97m[VisionQA Report]\033[0m"


def _narrate(message: str):
    print(f"{PERSONA_PREFIX} {message}")


def _screenshot_to_b64(path: str) -> str:
    """Convert a screenshot file to a base64 data URI string."""
    if not path or not os.path.exists(path):
        return ""
    try:
        ext = Path(path).suffix.lower().lstrip(".")
        mime = "image/png" if ext == "png" else "image/jpeg"
        data = base64.b64encode(open(path, "rb").read()).decode("utf-8")
        return f"data:{mime};base64,{data}"
    except Exception:
        return ""


class ReportGenerator:
    """Generates comprehensive Markdown and HTML test reports."""

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; }
        .container { max-width: 980px; margin: 0 auto; padding: 2rem; }
        /* Header */
        .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; }
        h1 { font-size: 1.8rem; color: #f8fafc; }
        .meta { color: #94a3b8; font-size: 0.85rem; margin-bottom: 2rem; }
        /* Speech button */
        #speech-btn {
            background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.4);
            color: #a5b4fc; border-radius: 8px; padding: 0.4rem 0.9rem;
            cursor: pointer; font-size: 0.85rem; font-family: inherit;
            transition: all 0.2s; white-space: nowrap;
        }
        #speech-btn:hover { background: rgba(99,102,241,0.3); }
        /* Summary grid */
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat { background: #1e293b; border-radius: 8px; padding: 1rem; text-align: center; }
        .stat .value { font-size: 1.8rem; font-weight: 700; }
        .stat .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }
        .stat.pass .value { color: #4ade80; }
        .stat.fail .value { color: #f87171; }
        .stat.review .value { color: #fbbf24; }
        .stat.rate .value { color: #60a5fa; }
        /* Verdict banner */
        .verdict { padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-weight: 600; }
        .verdict.all-pass { background: #14532d; color: #4ade80; }
        .verdict.has-fail { background: #7f1d1d; color: #fca5a5; }
        .verdict.has-review { background: #713f12; color: #fde68a; }
        /* Result cards */
        .result { background: #1e293b; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; border-left: 4px solid; }
        .result.PASS { border-color: #4ade80; }
        .result.FAIL { border-color: #f87171; }
        .result.NEEDS_REVIEW { border-color: #fbbf24; }
        .result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
        .badge { padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
        .badge.PASS { background: #14532d; color: #4ade80; }
        .badge.FAIL { background: #7f1d1d; color: #fca5a5; }
        .badge.NEEDS_REVIEW { background: #713f12; color: #fde68a; }
        .badge.severity { background: #312e81; color: #a5b4fc; }
        /* Confidence bar */
        .confidence-bar { height: 6px; background: #334155; border-radius: 3px; margin: 0.5rem 0; }
        .confidence-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #3b82f6, #818cf8); transition: width 0.8s ease; }
        /* Observations & grounding */
        .observations { margin-top: 0.5rem; }
        .observations li { margin-left: 1.2rem; font-size: 0.85rem; color: #cbd5e1; }
        .grounding-section { margin-top: 0.75rem; padding: 0.75rem; background: #0f172a; border-radius: 6px; border: 1px solid #334155; }
        .grounding-section h4 { font-size: 0.8rem; color: #818cf8; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.3rem; }
        .grounding-section li { font-size: 0.8rem; color: #94a3b8; margin-left: 1rem; word-break: break-all; }
        .grounding-section a { color: #60a5fa; text-decoration: none; }
        .grounding-section a:hover { text-decoration: underline; }
        /* Screenshot */
        details summary { cursor: pointer; font-size: 0.8rem; color: #64748b; user-select: none; margin-top: 0.8rem; }
        details img { margin-top: 0.5rem; max-width: 100%; border-radius: 6px; border: 1px solid #334155; }
        /* Navigator steps trail */
        .nav-trail { margin-bottom: 2rem; }
        .nav-trail h2 { font-size: 1.2rem; margin-bottom: 1rem; }
        .nav-step { background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; border-left: 4px solid #3b82f6; }
        .nav-step-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; font-size: 0.85rem; }
        .step-badge { background: #1d4ed8; color: #bfdbfe; border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.7rem; font-weight: 700; }
        .step-badge.skipped { background: #713f12; color: #fde68a; }
        .screenshots-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.75rem; }
        .shot-panel { background: #0f172a; border-radius: 6px; padding: 0.4rem; }
        .shot-panel .shot-label { font-size: 0.65rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
        .shot-panel img { width: 100%; border-radius: 4px; border: 1px solid #334155; display: block; }
        .shot-panel.annotated .shot-label { color: #f87171; }
        .shot-panel.annotated img { border-color: #f87171; }
        /* Chat panel */
        .chat-panel {
            margin-top: 3rem; background: #1e293b; border-radius: 12px;
            padding: 1.5rem; border: 1px solid #334155;
        }
        .chat-panel h2 { font-size: 1.1rem; margin-bottom: 0.4rem; color: #f8fafc; }
        .chat-panel p { font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem; }
        #chat-messages { min-height: 80px; max-height: 320px; overflow-y: auto; margin-bottom: 1rem; }
        .msg { padding: 0.6rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.875rem; line-height: 1.5; }
        .msg.user { background: #312e81; color: #c7d2fe; align-self: flex-end; }
        .msg.agent { background: #0f172a; color: #cbd5e1; border: 1px solid #334155; white-space: pre-wrap; }
        .msg.thinking { color: #64748b; font-style: italic; }
        .chat-input-row { display: flex; gap: 0.5rem; }
        #chat-input {
            flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 8px;
            padding: 0.6rem 0.8rem; color: #e2e8f0; font-family: inherit; font-size: 0.875rem;
            resize: none;
        }
        #chat-input:focus { outline: none; border-color: #6366f1; }
        #chat-send {
            background: #6366f1; color: white; border: none; border-radius: 8px;
            padding: 0.6rem 1.2rem; cursor: pointer; font-family: inherit;
            font-size: 0.875rem; font-weight: 600; transition: background 0.2s;
        }
        #chat-send:hover { background: #4f46e5; }
        #chat-send:disabled { background: #334155; cursor: not-allowed; }
        /* Footer */
        .footer { text-align: center; color: #64748b; font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>{{ title }}</h1>
                <div class="meta">Generated {{ timestamp }} | Engine: VisionQA with {{ model }} | Threshold: {{ threshold }}%</div>
            </div>
            <button id="speech-btn" onclick="toggleSpeech()">🔊 Replay Verdict</button>
        </div>

        <div class="summary">
            <div class="stat"><div class="value">{{ total }}</div><div class="label">Total Checks</div></div>
            <div class="stat pass"><div class="value">{{ passed }}</div><div class="label">Passed</div></div>
            <div class="stat fail"><div class="value">{{ failed }}</div><div class="label">Failed</div></div>
            <div class="stat review"><div class="value">{{ review }}</div><div class="label">Needs Review</div></div>
            <div class="stat rate"><div class="value">{{ pass_rate }}%</div><div class="label">Pass Rate</div></div>
        </div>

        {% if failed == 0 and review == 0 %}
        <div class="verdict all-pass">✅ ALL CHECKS PASSED — No visual regressions detected.</div>
        {% elif failed > 0 %}
        <div class="verdict has-fail">🚨 {{ failed }} FAILURE(S) DETECTED — Visual regressions found.</div>
        {% else %}
        <div class="verdict has-review">⚠️ {{ review }} CHECK(S) NEED HUMAN REVIEW — Confidence below threshold.</div>
        {% endif %}

        <h2 style="margin-bottom: 1rem; font-size: 1.2rem;">Detailed Results</h2>

        {% if nav_steps %}
        <!-- Navigator Execution Trail -->
        <div class="nav-trail">
            <h2>&#x1F916; Navigator Execution Trail</h2>
            {% for step in nav_steps %}
            <div class="nav-step">
                <div class="nav-step-header">
                    <span class="step-badge {% if step.status == 'skipped' %}skipped{% endif %}">Step {{ step.step_number }}</span>
                    <strong>{{ step.instruction }}</strong>
                    {% if step.target_label %}
                    <span style="color:#94a3b8;">&#x2192; <em>{{ step.target_label }}</em></span>
                    {% endif %}
                    <span style="color:#94a3b8;margin-left:auto;font-size:0.78rem;">{{ (step.confidence * 100)|round(0)|int }}% confidence</span>
                </div>
                {% if step.reasoning %}
                <div style="font-size:0.8rem;color:#64748b;margin-bottom:0.5rem;">{{ step.reasoning[:160] }}</div>
                {% endif %}
                {% if step.screenshot_before_b64 or step.screenshot_annotated_b64 or step.screenshot_after_b64 %}
                <div class="screenshots-row">
                    {% if step.screenshot_before_b64 %}
                    <div class="shot-panel">
                        <div class="shot-label">Before</div>
                        <img src="{{ step.screenshot_before_b64 }}" alt="before">
                    </div>
                    {% endif %}
                    {% if step.screenshot_annotated_b64 %}
                    <div class="shot-panel annotated">
                        <div class="shot-label">&#x1F3AF; Gemini Target</div>
                        <img src="{{ step.screenshot_annotated_b64 }}" alt="annotated">
                    </div>
                    {% endif %}
                    {% if step.screenshot_after_b64 %}
                    <div class="shot-panel">
                        <div class="shot-label">After</div>
                        <img src="{{ step.screenshot_after_b64 }}" alt="after">
                    </div>
                    {% endif %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% for r in results %}
        <div class="result {{ r.status }}">
            <div class="result-header">
                <div>
                    <span class="badge {{ r.status }}">{{ r.status }}</span>
                    <span class="badge severity">{{ r.severity }}</span>
                    <span style="font-size: 0.8rem; color: #94a3b8; margin-left: 0.5rem;">{{ r.bug_id }}</span>
                </div>
                <span style="font-size: 0.85rem; color: #94a3b8;">{{ (r.confidence * 100)|round(0)|int }}% confidence</span>
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 0.3rem;">{{ r.instruction }}</div>
            <div class="confidence-bar"><div class="confidence-fill" style="width: {{ (r.confidence * 100)|round(0)|int }}%;"></div></div>
            <div style="margin-top: 0.5rem;">{{ r.analysis }}</div>
            {% if r.observations %}
            <ul class="observations">
                {% for obs in r.observations %}
                <li>{{ obs }}</li>
                {% endfor %}
            </ul>
            {% endif %}
            {% if r.grounding_notes %}
            <div class="grounding-section">
                <h4>🔍 Grounding Evidence</h4>
                <ul>
                {% for note in r.grounding_notes %}
                    <li>{% if note.startswith('http') %}<a href="{{ note }}" target="_blank" rel="noopener">{{ note }}</a>{% else %}{{ note }}{% endif %}</li>
                {% endfor %}
                </ul>
            </div>
            {% endif %}
            {% if r.screenshot_b64 %}
            <details>
                <summary>📷 Screenshot Evidence</summary>
                <img src="{{ r.screenshot_b64 }}" alt="screenshot">
            </details>
            {% endif %}
        </div>
        {% endfor %}

        <!-- Ask VisionQA chat panel -->
        <div class="chat-panel">
            <h2>💬 Ask VisionQA</h2>
            <p>Ask the agent anything about this report — e.g. <em>"Why did check 1 fail?"</em> or <em>"What should I fix first?"</em></p>
            <div id="chat-messages"></div>
            <div class="chat-input-row">
                <textarea id="chat-input" rows="2" placeholder="Ask about this report…" onkeydown="handleKey(event)"></textarea>
                <button id="chat-send" onclick="sendChat()">Ask →</button>
            </div>
        </div>

        <div class="footer">Report ID: VQA-RPT-{{ report_id }} | VisionQA — The Autonomous Visual SDET</div>
    </div>

    <script>
        // ── Speech Synthesis ──────────────────────────────────────────────
        (function() {
            const status = "{{ 'ALL CHECKS PASSED' if failed == 0 and review == 0 else (failed|string + ' failure' + ('' if failed == 1 else 's') + ' detected') if failed > 0 else (review|string + ' check' + ('' if review == 1 else 's') + ' need human review') }}";
            const text = "VisionQA verdict. " + status + ". Pass rate: {{ pass_rate }} percent.";
            let currentUtterance = null;
            let isMuted = false;

            function speakVerdict() {
                if (isMuted || !window.speechSynthesis) return;
                window.speechSynthesis.cancel();
                currentUtterance = new SpeechSynthesisUtterance(text);
                currentUtterance.rate = 0.95;
                currentUtterance.pitch = 1.0;
                window.speechSynthesis.speak(currentUtterance);
            }

            window.toggleSpeech = function() {
                const btn = document.getElementById('speech-btn');
                if (!isMuted) {
                    window.speechSynthesis.cancel();
                    isMuted = true;
                    btn.textContent = '🔇 Muted';
                    btn.style.color = '#64748b';
                } else {
                    isMuted = false;
                    btn.textContent = '🔊 Replay Verdict';
                    btn.style.color = '#a5b4fc';
                    speakVerdict();
                }
            };

            // Speak ~600ms after page load (allows voices to load)
            setTimeout(speakVerdict, 600);
        })();

        // ── Chat Panel ────────────────────────────────────────────────────
        const reportSummary = `VisionQA Report: {{ title }}. {{ total }} checks. {{ passed }} passed, {{ failed }} failed, {{ review }} need review. Pass rate: {{ pass_rate }}%.`;

        function appendMsg(cls, text) {
            const div = document.createElement('div');
            div.className = 'msg ' + cls;
            div.textContent = text;
            const container = document.getElementById('chat-messages');
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
            return div;
        }

        async function sendChat() {
            const input = document.getElementById('chat-input');
            const sendBtn = document.getElementById('chat-send');
            const question = input.value.trim();
            if (!question) return;

            input.value = '';
            sendBtn.disabled = true;
            appendMsg('user', question);
            const thinking = appendMsg('thinking', 'VisionQA is thinking…');

            try {
                const res = await fetch('/v1/agent/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: question, report_context: reportSummary }),
                });
                const data = await res.json();
                thinking.remove();
                appendMsg('agent', data.answer || 'No answer returned.');

                // Speak the answer
                if (window.speechSynthesis) {
                    const utt = new SpeechSynthesisUtterance(data.answer);
                    utt.rate = 1.0;
                    window.speechSynthesis.speak(utt);
                }
            } catch(e) {
                thinking.remove();
                appendMsg('agent', '⚠️ Could not reach the VisionQA API. Make sure the server is running on localhost:8080.');
            } finally {
                sendBtn.disabled = false;
            }
        }

        function handleKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
        }
    </script>
</body>
</html>"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Config.REPORTS_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_markdown_report(self, results: list, title: str = "VisionQA Test Report") -> str:
        """
        Generate a Markdown report from a list of AnalysisResults.
        Returns the file path of the generated report.
        """
        _narrate(f"📝 Generating report: {title}")

        timestamp = datetime.now(timezone.utc)
        filename = f"visionqa_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.output_dir, filename)

        # Compute stats
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        review = sum(1 for r in results if r.status == "NEEDS_REVIEW")
        pass_rate = (passed / total * 100) if total > 0 else 0
        avg_confidence = sum(r.confidence for r in results) / total if total > 0 else 0

        # Build report
        lines = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"**Engine:** VisionQA with Gemini 2.5 Flash")
        lines.append(f"**Confidence Threshold:** {Config.CONFIDENCE_THRESHOLD:.0%}")
        lines.append("")

        # Summary box
        lines.append("---")
        lines.append("")
        lines.append("## 📊 Executive Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| **Total Checks** | {total} |")
        lines.append(f"| **Passed** | ✅ {passed} |")
        lines.append(f"| **Failed** | ❌ {failed} |")
        lines.append(f"| **Needs Review** | 🔶 {review} |")
        lines.append(f"| **Pass Rate** | **{pass_rate:.1f}%** |")
        lines.append(f"| **Avg. Confidence** | {avg_confidence:.0%} |")
        lines.append("")

        # Overall verdict
        if failed == 0 and review == 0:
            lines.append("> ✅ **VERDICT: ALL CHECKS PASSED** — No visual regressions detected.")
        elif failed > 0:
            lines.append(f"> 🚨 **VERDICT: {failed} FAILURE(S) DETECTED** — Visual regressions found. See details below.")
        else:
            lines.append(f"> ⚠️ **VERDICT: {review} CHECK(S) NEED HUMAN REVIEW** — Confidence was below threshold.")
        lines.append("")

        # Detailed results
        lines.append("---")
        lines.append("")
        lines.append("## 🔍 Detailed Results")
        lines.append("")

        for i, result in enumerate(results, 1):
            status_icon = {"PASS": "✅", "FAIL": "❌", "NEEDS_REVIEW": "🔶"}.get(result.status, "❓")
            severity_badge = f"`{result.severity}`"

            lines.append(f"### Check {i}: {status_icon} {result.status}")
            lines.append("")
            lines.append(f"- **Instruction:** {result.instruction}")
            lines.append(f"- **Severity:** {severity_badge}")
            lines.append(f"- **Confidence:** {result.confidence:.0%}")
            lines.append(f"- **Bug ID:** `{result.bug_id}`")
            lines.append("")
            lines.append(f"**Analysis:** {result.analysis}")
            lines.append("")

            if result.observations:
                lines.append("**Observations:**")
                for obs in result.observations:
                    lines.append(f"- {obs}")
                lines.append("")

            grounding = getattr(result, "grounding_notes", [])
            if grounding:
                lines.append("**🔍 Grounding Evidence:**")
                for note in grounding:
                    lines.append(f"- {note}")
                lines.append("")

            if result.screenshot_path and os.path.exists(result.screenshot_path):
                b64 = _screenshot_to_b64(result.screenshot_path)
                if b64:
                    lines.append(f"![Screenshot — {Path(result.screenshot_path).name}]({b64})")
                else:
                    lines.append(f"**Screenshot:** `{Path(result.screenshot_path).name}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Footer
        lines.append("## 🏷️ Metadata")
        lines.append("")
        lines.append("| Key | Value |")
        lines.append("|---|---|")
        lines.append(f"| Report ID | `VQA-RPT-{timestamp.strftime('%Y%m%d%H%M%S')}` |")
        lines.append(f"| Model | `{Config.GEMINI_MODEL}` |")
        lines.append(f"| Total Checks | {total} |")
        lines.append(f"| Generation Time | {timestamp.isoformat()} |")
        lines.append("")
        lines.append("---")
        lines.append("*Report generated by VisionQA — The Autonomous Visual SDET*")

        report_content = "\n".join(lines)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)

        _narrate(f"✅ Report saved: {filepath}")
        _narrate(f"📊 Summary: {passed} PASS | {failed} FAIL | {review} REVIEW ({pass_rate:.1f}% pass rate)")

        return filepath

    def generate_html_report(self, results: list, title: str = "VisionQA Test Report",
                             nav_steps: list = None) -> str:
        """
        Generate an HTML report from a list of AnalysisResults.
        Optionally accepts nav_steps (list of dicts from WebNavigator.perform_action)
        to render the Navigator Execution Trail with annotated screenshots.
        Returns the file path of the generated report.
        """
        _narrate(f"[VisionQA] Generating HTML report: {title}")

        timestamp = datetime.now(timezone.utc)
        filename = f"visionqa_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.output_dir, filename)

        # Compute stats
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        review = sum(1 for r in results if r.status == "NEEDS_REVIEW")
        pass_rate = round((passed / total * 100), 1) if total > 0 else 0

        # Convert results to template-friendly dicts with embedded screenshots
        result_dicts = []
        for r in results:
            screenshot_path = getattr(r, "screenshot_path", "")
            result_dicts.append({
                "status": r.status,
                "analysis": r.analysis,
                "confidence": r.confidence,
                "severity": r.severity,
                "bug_id": r.bug_id,
                "instruction": getattr(r, "instruction", "N/A"),
                "observations": r.observations,
                "grounding_notes": getattr(r, "grounding_notes", []),
                "screenshot_b64": _screenshot_to_b64(screenshot_path),
            })

        # Convert nav_steps screenshots to base64 for inline embedding
        nav_step_dicts = []
        for step in (nav_steps or []):
            result = step.get("result", {})
            instruction = step.get("instruction", "navigate")
            nav_step_dicts.append({
                "step_number": len(nav_step_dicts) + 1,
                "instruction": instruction,
                "status": result.get("status", "executed"),
                "target_label": (result.get("target") or {}).get("label", ""),
                "confidence": result.get("confidence", 0.0),
                "reasoning": result.get("reasoning", ""),
                "screenshot_before_b64": _screenshot_to_b64(
                    result.get("screenshot_before", "")
                ),
                "screenshot_annotated_b64": _screenshot_to_b64(
                    result.get("screenshot_before_annotated", "")
                ),
                "screenshot_after_b64": _screenshot_to_b64(
                    result.get("screenshot_after", "")
                ),
            })

        # Render template
        template = Template(self.HTML_TEMPLATE)
        html_content = template.render(
            title=title,
            timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            model=Config.GEMINI_MODEL,
            threshold=int(Config.CONFIDENCE_THRESHOLD * 100),
            total=total,
            passed=passed,
            failed=failed,
            review=review,
            pass_rate=pass_rate,
            results=result_dicts,
            nav_steps=nav_step_dicts,
            report_id=timestamp.strftime("%Y%m%d%H%M%S"),
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        _narrate(f"✅ HTML report saved: {filepath}")

        return filepath
