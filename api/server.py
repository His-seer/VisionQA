"""
VisionQA FastAPI Server
Exposes the Visual QA pipeline as a REST API.
"""

import os
import asyncio
import tempfile
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.requests import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.models import VerifyResponse, HealthResponse, ChatResponse
from config import Config
from vision.visual_qa_agent import VisualQAAgent
from vision.critic import Critic
from vision.baseline_manager import BaselineManager
from workflow.automator import WorkflowAutomator
from google import genai
from google.genai import types


# ── App Lifecycle ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = Config.validate()
    if errors:
        print(f"[VisionQA API] ⚠️  Config warnings: {errors}")
    Config.print_status()
    yield


# ── App Init ──────────────────────────────────────────────────────

app = FastAPI(
    title="VisionQA API",
    description=(
        "Autonomous Visual SDET — powered by Gemini 2.5 Flash.\n\n"
        "Sends a screenshot + a natural language instruction and receives a structured PASS/FAIL analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Shared Instances ──────────────────────────────────────────────

qa_agent = VisualQAAgent()
critic = Critic()
baseline_manager = BaselineManager()
automator = WorkflowAutomator()

# Thread safety lock for baseline file I/O
_baseline_lock = asyncio.Lock()


# ── Routes ────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint for Cloud Run and monitoring."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        model=Config.GEMINI_MODEL,
        confidence_threshold=Config.CONFIDENCE_THRESHOLD,
    )


@app.post("/v1/agent/verify", response_model=VerifyResponse, tags=["Visual QA"])
@limiter.limit(Config.RATE_LIMIT)
async def verify(
    request: Request,
    screenshot: UploadFile = File(..., description="Screenshot image to analyze (PNG/JPG)"),
    instruction: str = Form(..., description="Natural language test instruction"),
    run_critic: bool = Form(False, description="Run the self-reflection Critic pass"),
    baseline_name: str = Form("", description="Name of baseline to compare against (optional)"),
    create_ticket: bool = Form(False, description="Auto-create Jira/GitHub ticket if bug found"),
):
    """
    Analyze a UI screenshot against a test instruction using Gemini 2.5 Flash.

    - **screenshot**: The page screenshot to inspect
    - **instruction**: What to check, e.g. 'Verify the Add to Cart button is visible'
    - **run_critic**: Enable the second-pass hallucination guardrail
    - **baseline_name**: Compare against a saved golden baseline
    - **create_ticket**: Auto-push bug report to Jira/GitHub if a failure is found
    """
    # Validate file type
    if screenshot.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, or WebP images are supported.")

    # Save uploaded screenshot to temp file
    suffix = "." + (screenshot.filename or "upload.png").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await screenshot.read())
        tmp_path = tmp.name

    try:
        # Phase 2a: Visual QA Analysis
        result = qa_agent.analyze(tmp_path, instruction)

        # Phase 2b: Critic pass (optional)
        if run_critic and result.confidence > 0:
            critique = critic.review(tmp_path, result.to_dict())
            # Apply adjusted confidence from critic
            adjusted = float(critique.get("adjusted_confidence", result.confidence))
            if adjusted < result.confidence:
                result.confidence = adjusted
                if adjusted < Config.CONFIDENCE_THRESHOLD:
                    result.status = "NEEDS_REVIEW"

        # Phase 2c: Baseline comparison (if name provided and confidence is low)
        if baseline_name and result.status == "NEEDS_REVIEW":
            async with _baseline_lock:
                baseline_result = baseline_manager.compare(baseline_name, tmp_path)
            if baseline_result["status"] in ("PASS", "FAIL"):
                result.status = baseline_result["status"]
                result.analysis += f" (Baseline pixel diff: {baseline_result['diff_percentage']:.2f}%)"

        # Phase 3: Workflow (optional)
        ticket_url = None
        report_path = None
        if create_ticket and result.is_bug():
            workflow_result = automator.on_bug_found(result)
            report_path = workflow_result.get("report")

        return VerifyResponse(
            status=result.status,
            analysis=result.analysis,
            confidence=result.confidence,
            severity=result.severity,
            bug_id=result.bug_id,
            observations=result.observations,
            grounding_notes=result.grounding_notes,
            ticket_url=ticket_url,
            report_path=report_path,
            timestamp=result.timestamp,
        )

    finally:
        os.unlink(tmp_path)


@app.post("/v1/baseline/save", tags=["Baselines"])
@limiter.limit("30/minute")
async def save_baseline(
    request: Request,
    screenshot: UploadFile = File(..., description="Screenshot to save as golden baseline"),
    name: str = Form(..., description="Unique name for this baseline"),
):
    """Save a screenshot as a golden baseline for future comparisons."""
    suffix = "." + (screenshot.filename or "baseline.png").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await screenshot.read())
        tmp_path = tmp.name

    try:
        async with _baseline_lock:
            path = baseline_manager.save_baseline(name, tmp_path)
        return {"status": "saved", "name": name, "path": path}
    finally:
        os.unlink(tmp_path)


@app.get("/v1/baseline/list", tags=["Baselines"])
async def list_baselines():
    """List all stored golden baselines."""
    return {"baselines": baseline_manager.list_baselines()}


# ── Chat endpoint ─────────────────────────────────────────────────

from pydantic import BaseModel


class _ChatBody(BaseModel):
    question: str
    report_context: str = ""


@app.post("/v1/agent/chat", response_model=ChatResponse, tags=["Visual QA"])
async def chat(
    body: _ChatBody,
):
    """
    Ask the VisionQA agent a natural-language question about a test report.
    The agent answers using Gemini, grounded on the report context you supply.
    """
    client = genai.Client(api_key=Config.GOOGLE_API_KEY)
    system = (
        "You are VisionQA, an expert visual QA engineer. "
        "Answer the user's question concisely and precisely based on the report context provided. "
        "If the context doesn't have enough data, say so rather than guessing."
    )
    prompt = (
        f"Report context: {body.report_context}\n\n"
        f"User question: {body.question}"
    )
    try:
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,
            ),
        )
        return ChatResponse(answer=response.text.strip(), model=Config.GEMINI_MODEL)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini error: {exc}")


# ── SSE streaming analysis endpoint ──────────────────────────────

@app.post("/v1/agent/stream", tags=["Visual QA"])
@limiter.limit("5/minute")
async def stream_analysis(
    request: Request,
    screenshot: UploadFile = File(..., description="Screenshot image to analyze (PNG/JPG)"),
    instruction: str = Form(..., description="Natural language test instruction"),
):
    """
    Stream visual QA analysis as Server-Sent Events (SSE).
    Each `data:` line carries a narration step so the client sees live progress.
    """
    if screenshot.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, or WebP images are supported.")

    suffix = "." + (screenshot.filename or "upload.png").rsplit(".", 1)[-1]
    contents = await screenshot.read()

    async def event_stream() -> AsyncGenerator[str, None]:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name

            narration_steps = [
                f"🔍 Analyzing screenshot against: \"{instruction}\"",
                "👁️  Observing UI elements and layout...",
                "🧠 Reasoning about the test instruction...",
                "⚖️  Judging PASS / FAIL with confidence scoring...",
            ]

            for step in narration_steps:
                yield f"data: {step}\n\n"
                await asyncio.sleep(0.4)

            # Run analysis in thread pool to keep event loop responsive
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: qa_agent.analyze(tmp_path, instruction)
            )

            yield f"data: ✅ Analysis complete — {result.status} ({result.confidence:.0%} confidence)\n\n"
            yield f"data: 📊 Severity: {result.severity}\n\n"
            yield f"data: 💬 {result.analysis}\n\n"

            if result.observations:
                for obs in result.observations:
                    yield f"data: • {obs}\n\n"

            if result.grounding_notes:
                yield "data: 🔍 Grounding Evidence:\n\n"
                for note in result.grounding_notes:
                    yield f"data:   — {note[:120]}\n\n"

            import json
            yield f"data: [DONE] {json.dumps(result.to_dict())}\n\n"

        except Exception as exc:
            yield f"data: [ERROR] {str(exc)}\n\n"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Navigate Endpoint ─────────────────────────────────────────────────────────

@app.post(
    "/v1/agent/navigate",
    response_model=None,   # returns NavigateVerifyResponse, imported below
    summary="Navigate a URL with AI-driven steps then run visual QA",
    tags=["Navigator"],
)
@limiter.limit("5/minute")
async def navigate_and_verify(request: Request):
    """
    Full autonomous navigation flow:
    1. Launch a headless Chrome browser
    2. Navigate to the given URL
    3. Execute each natural-language step — Gemini chooses WHAT to click / type
    4. Annotate before-screenshots with a crosshair showing Gemini's click target
    5. Run VisualQAAgent on the final page state
    6. Generate an HTML report with the full Navigator Execution Trail embedded
    7. Return structured JSON with per-step results + annotated screenshot paths

    Request body (JSON):
    {
      "url": "https://example.com",
      "steps": ["Click Login", "Type admin@example.com in the email field"],
      "qa_prompt": "Verify the dashboard heading is visible",
      "run_critic": false
    }
    """
    from api.models import NavigateRequest, NavigateVerifyResponse, NavigateStepResult
    from navigator.web_navigator import WebNavigator
    from workflow.report_generator import ReportGenerator

    import json as _json

    # Parse JSON body manually (avoids needing a Pydantic body param with file uploads)
    try:
        body = await request.json()
        nav_req = NavigateRequest(**body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid request body: {exc}")

    if not nav_req.url:
        raise HTTPException(status_code=400, detail="url is required")

    loop = asyncio.get_event_loop()

    def _run_flow():
        """Runs the blocking navigator + QA flow in a thread pool."""
        nav_step_results = []
        action_dicts = []   # raw dicts for report_generator nav_steps
        qa_results = []
        final_screenshot = None

        with WebNavigator(headless=True) as nav:
            # Navigate to the URL
            nav_result = nav.navigate_to(nav_req.url)
            final_screenshot = nav_result.get("screenshot")

            # Execute each step
            for i, instruction in enumerate(nav_req.steps, 1):
                action = nav.perform_action(instruction)
                final_screenshot = action.get("screenshot_after") or final_screenshot

                # Build per-step model
                target = action.get("target") or {}
                step_model = NavigateStepResult(
                    step_number=i,
                    instruction=instruction,
                    status=action.get("status", "executed"),
                    target_label=target.get("label"),
                    action_type=(action.get("action") or {}).get("type"),
                    confidence=action.get("confidence", 0.0),
                    reasoning=action.get("reasoning", ""),
                    screenshot_before_url=action.get("screenshot_before"),
                    screenshot_annotated_url=action.get("screenshot_before_annotated"),
                    screenshot_after_url=action.get("screenshot_after"),
                )
                nav_step_results.append(step_model)

                # Build raw dict for HTML template (report_generator needs `result` key)
                action_dicts.append({
                    "instruction": instruction,
                    "result": action,
                })

        # Run VisualQA on the final page state
        if nav_req.qa_prompt and final_screenshot:
            qa_agent = VisualQAAgent()
            qa_result = qa_agent.analyze(final_screenshot, nav_req.qa_prompt)

            if nav_req.run_critic:
                critic = Critic()
                critique = critic.review(final_screenshot, qa_result.to_dict())
                adjusted = float(critique.get("adjusted_confidence", qa_result.confidence))
                if adjusted < qa_result.confidence:
                    qa_result.confidence = adjusted
                    if adjusted < Config.CONFIDENCE_THRESHOLD:
                        qa_result.status = "NEEDS_REVIEW"

            qa_results.append(qa_result)

        # Generate HTML report with Navigator Execution Trail
        rg = ReportGenerator()
        report_path = rg.generate_html_report(
            qa_results,
            title=f"VisionQA Navigate — {nav_req.url}",
            nav_steps=action_dicts,
        )

        # Build response
        flow_status = "PASS"
        if any(r.status == "FAIL" for r in qa_results):
            flow_status = "FAIL"
        elif any(r.status == "NEEDS_REVIEW" for r in qa_results):
            flow_status = "NEEDS_REVIEW"

        qa_response = [
            VerifyResponse(
                status=r.status,
                analysis=r.analysis,
                confidence=r.confidence,
                severity=r.severity,
                bug_id=r.bug_id,
                observations=r.observations,
                grounding_notes=getattr(r, "grounding_notes", []),
                report_path=report_path,
                timestamp=r.timestamp,
            )
            for r in qa_results
        ]

        return NavigateVerifyResponse(
            flow_status=flow_status,
            steps_executed=len(nav_step_results),
            nav_steps=nav_step_results,
            qa_results=qa_response,
            report_path=report_path,
        )

    try:
        response = await loop.run_in_executor(None, _run_flow)
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Navigation flow failed: {exc}")

