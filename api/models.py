"""
VisionQA API Models
Pydantic request/response schemas for the FastAPI server.
"""

from pydantic import BaseModel, Field
from typing import Optional


class VerifyResponse(BaseModel):
    status: str = Field(..., description="PASS, FAIL, or NEEDS_REVIEW")
    analysis: str = Field(..., description="Human-readable analysis of the finding")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, or INFO")
    bug_id: str = Field(..., description="Unique identifier for this analysis")
    observations: list[str] = Field(default_factory=list)
    grounding_notes: list[str] = Field(
        default_factory=list,
        description="Google Search grounding evidence for FAIL results",
    )
    ticket_url: Optional[str] = Field(None, description="URL of created Jira/GitHub ticket")
    report_path: Optional[str] = Field(None, description="Path to generated Markdown report")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Agent answer to the user's question")
    model: str = Field(..., description="Gemini model used for the answer")


class NavigateStepResult(BaseModel):
    step_number: int
    instruction: str
    status: str = Field(..., description="executed or skipped")
    target_label: Optional[str] = None
    action_type: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    screenshot_before_url: Optional[str] = Field(
        None, description="Path to before-action screenshot"
    )
    screenshot_annotated_url: Optional[str] = Field(
        None, description="Path to annotated screenshot showing Gemini's click target"
    )
    screenshot_after_url: Optional[str] = Field(
        None, description="Path to after-action screenshot"
    )


class NavigateRequest(BaseModel):
    url: str = Field(..., description="URL to navigate to")
    steps: list[str] = Field(default_factory=list, description="Navigation steps to perform")
    qa_prompt: Optional[str] = Field(
        None, description="Final visual QA instruction to run after navigation"
    )
    run_critic: bool = Field(False, description="Enable the self-reflection Critic pass")


class NavigateVerifyResponse(BaseModel):
    flow_status: str = Field(..., description="overall flow result: PASS or FAIL")
    steps_executed: int
    nav_steps: list[NavigateStepResult] = Field(
        default_factory=list,
        description="Per-step results with annotated screenshot paths",
    )
    qa_results: list[VerifyResponse]
    report_path: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    model: str
    confidence_threshold: float

