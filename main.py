"""
VisionQA CLI -- Main Orchestrator

Usage:
    # Analyze a screenshot (streaming Gemini tokens)
    python main.py --image screenshot.png --prompt "Verify login button visible" --stream

    # Navigate a URL and run a visual check
    python main.py --url https://example.com --prompt "Check the heading says Example Domain"

    # Live monitoring mode (watches URL every N seconds, Ctrl+C to stop)
    python main.py --live https://example.com --prompt "Check the page loaded" --interval 30

    # Start the API server
    python main.py --serve
"""

import argparse
import json
import sys
import os

from config import Config


BANNER = """
\033[95m+==================================================+
|        VisionQA -- Autonomous Visual SDET        |
|        Powered by Gemini 2.5 Flash               |
+==================================================+\033[0m
"""


def run_image_analysis(image_path: str, prompt: str, run_critic: bool,
                       baseline: str, stream: bool = False) -> int:
    """Analyze a local screenshot and return exit code (0=pass, 1=fail)."""
    from vision.visual_qa_agent import VisualQAAgent
    from vision.critic import Critic
    from vision.baseline_manager import BaselineManager
    from workflow.automator import WorkflowAutomator

    if not os.path.exists(image_path):
        print(f"\033[91m[ERROR] Image not found: {image_path}\033[0m")
        return 2

    agent = VisualQAAgent()
    result = agent.analyze_stream(image_path, prompt) if stream else agent.analyze(image_path, prompt)

    if run_critic:
        critic = Critic()
        critique = critic.review(image_path, result.to_dict())
        adjusted = float(critique.get("adjusted_confidence", result.confidence))
        if adjusted < result.confidence:
            result.confidence = adjusted
            if adjusted < Config.CONFIDENCE_THRESHOLD:
                result.status = "NEEDS_REVIEW"

    if baseline:
        bm = BaselineManager()
        if result.status == "NEEDS_REVIEW":
            baseline_result = bm.compare(baseline, image_path)
            if baseline_result["status"] in ("PASS", "FAIL"):
                result.status = baseline_result["status"]
                result.analysis += f" (Pixel diff: {baseline_result['diff_percentage']:.2f}%)"

    # Process results — generate report and handle bugs
    automator = WorkflowAutomator()
    automator.process_results([result], report_title=f"VisionQA — {os.path.basename(image_path)}")

    # Print final JSON output to stdout (CI/CD consumable)
    print("\n\033[97m── Final Result ──────────────────────────────────\033[0m")
    print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.status == "PASS" else 1


def run_live_monitor(url: str, prompt: str, interval: int, run_critic: bool) -> int:
    """
    Live monitoring mode: navigate to a URL and run visual QA every `interval` seconds.
    Prints streaming Gemini reasoning + a live countdown. Press Ctrl+C to stop.
    """
    import time as _time
    from navigator.web_navigator import WebNavigator
    from vision.visual_qa_agent import VisualQAAgent
    from vision.critic import Critic

    print(f"\033[95m[VisionQA Live Monitor]\033[0m Watching: {url}")
    print(f"\033[95m[VisionQA Live Monitor]\033[0m Instruction: {prompt}")
    print(f"\033[95m[VisionQA Live Monitor]\033[0m Interval: {interval}s -- Press Ctrl+C to stop")

    check_count = 0
    try:
        while True:
            check_count += 1
            print(f"\n\033[95m{'='*55}\033[0m")
            print(f"\033[95m[Check #{check_count}] {_time.strftime('%H:%M:%S')}\033[0m")
            print(f"\033[95m{'='*55}\033[0m")

            with WebNavigator(headless=True) as nav:
                nav_result = nav.navigate_to(url)
                screenshot = nav_result.get("screenshot")

            if not screenshot:
                print("\033[91m[ERROR] Screenshot capture failed.\033[0m")
            else:
                agent = VisualQAAgent()
                result = agent.analyze_stream(screenshot, prompt)

                if run_critic:
                    critic = Critic()
                    critique = critic.review(screenshot, result.to_dict())
                    adjusted = float(critique.get("adjusted_confidence", result.confidence))
                    if adjusted < result.confidence:
                        result.confidence = adjusted
                        if adjusted < Config.CONFIDENCE_THRESHOLD:
                            result.status = "NEEDS_REVIEW"

                colors = {
                    "PASS": "\033[92m", "FAIL": "\033[91m", "NEEDS_REVIEW": "\033[93m"
                }
                c = colors.get(result.status, "\033[0m")
                print(f"{c}[Check #{check_count}] {result.status} "
                      f"({result.confidence:.0%}) -- {result.analysis[:80]}\033[0m")

            for remaining in range(interval, 0, -1):
                print(f"\r\033[90mNext check in {remaining}s  ", end="", flush=True)
                _time.sleep(1)
            print("\033[0m")

    except KeyboardInterrupt:
        print(f"\n\033[95m[VisionQA Live Monitor]\033[0m Stopped after {check_count} checks.")
        return 0


def run_navigation_flow(url: str, steps: list[str], prompt: str, run_critic: bool) -> int:
    """Navigate a URL, run steps, then perform visual QA."""
    from navigator.web_navigator import WebNavigator
    from vision.visual_qa_agent import VisualQAAgent
    from vision.critic import Critic
    from workflow.automator import WorkflowAutomator

    qa_results = []

    with WebNavigator(headless=True) as nav:
        # Run navigation steps
        flow_results = nav.run_flow(url, steps) if steps else [nav.navigate_to(url)]

        # Get final screenshot for QA
        final_screenshot = None
        for step_result in reversed(flow_results):
            result = step_result.get("result", {})
            if "screenshot_after" in result:
                final_screenshot = result["screenshot_after"]
                break
            if "screenshot" in result:
                final_screenshot = result["screenshot"]
                break

        if not final_screenshot:
            print("\033[91m[ERROR] Could not capture a final screenshot.\033[0m")
            return 2

        # Visual QA on the final state
        if prompt:
            agent = VisualQAAgent()
            qa_result = agent.analyze(final_screenshot, prompt)

            if run_critic:
                critic = Critic()
                critique = critic.review(final_screenshot, qa_result.to_dict())
                adjusted = float(critique.get("adjusted_confidence", qa_result.confidence))
                if adjusted < qa_result.confidence:
                    qa_result.confidence = adjusted
                    if adjusted < Config.CONFIDENCE_THRESHOLD:
                        qa_result.status = "NEEDS_REVIEW"

            qa_results.append(qa_result)

    # Process all results
    automator = WorkflowAutomator()
    automator.process_results(qa_results, report_title=f"VisionQA — {url}")

    if qa_results:
        print("\n\033[97m── Final QA Result ───────────────────────────────\033[0m")
        print(json.dumps(qa_results[-1].to_dict(), indent=2))
        return 0 if qa_results[-1].status == "PASS" else 1

    return 0


def start_server():
    """Start the FastAPI API server."""
    import uvicorn
    print("\033[92m[VisionQA] Starting API server...\033[0m")
    print(f"\033[92m[VisionQA] Swagger UI: http://localhost:{Config.PORT}/docs\033[0m")
    uvicorn.run("api.server:app", host="0.0.0.0", port=Config.PORT, reload=Config.DEBUG)


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="VisionQA — Autonomous Visual SDET powered by Gemini 2.5 Flash",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Modes
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", metavar="PATH", help="Path to a screenshot image to analyze")
    mode.add_argument("--url", metavar="URL", help="URL to navigate to before analysis")
    mode.add_argument("--live", metavar="URL",
                      help="Live monitoring mode: watch a URL continuously at --interval seconds")
    mode.add_argument("--serve", action="store_true", help="Start the FastAPI API server")

    # Options
    parser.add_argument("--prompt", metavar="TEXT", help="Test instruction")
    parser.add_argument("--steps", nargs="+", metavar="STEP",
                        help="Navigation steps to perform before final QA check")
    parser.add_argument("--critic", action="store_true",
                        help="Enable the self-reflection Critic pass")
    parser.add_argument("--baseline", metavar="NAME",
                        help="Golden baseline name to compare against")
    parser.add_argument("--stream", action="store_true",
                        help="Stream Gemini reasoning tokens live to stdout")
    parser.add_argument("--interval", type=int, default=30,
                        help="Seconds between checks in --live mode (default: 30)")

    args = parser.parse_args()

    # Validate config
    errors = Config.validate()
    if errors:
        for err in errors:
            print(f"\033[91m[CONFIG ERROR] {err}\033[0m")
        sys.exit(2)

    if args.serve:
        start_server()
    elif args.image:
        if not args.prompt:
            print("\033[91m[ERROR] --prompt is required when using --image\033[0m")
            sys.exit(2)
        sys.exit(run_image_analysis(args.image, args.prompt, args.critic,
                                    args.baseline or "", stream=args.stream))
    elif args.url:
        if not args.prompt and not args.steps:
            print("\033[91m[ERROR] Provide at least --prompt or --steps when using --url\033[0m")
            sys.exit(2)
        sys.exit(run_navigation_flow(args.url, args.steps or [], args.prompt or "", args.critic))
    elif args.live:
        if not args.prompt:
            print("\033[91m[ERROR] --prompt is required when using --live\033[0m")
            sys.exit(2)
        sys.exit(run_live_monitor(args.live, args.prompt, args.interval, args.critic))


if __name__ == "__main__":
    main()
