# VisionQA — The Autonomous Visual SDET

> **Powered by Gemini 2.5 Flash**

VisionQA replaces brittle, selector-based automation with **multimodal reasoning**. It acts as a "Digital QA Engineer" that visually perceives the browser, interprets user intent, and validates complex UI states — bridging the gap between manual testing and traditional automation.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     VisionQA Pipeline                      │
├────────────────┬────────────────────┬──────────────────────┤
│  Phase 1       │  Phase 2           │  Phase 3             │
│  NAVIGATOR     │  VISUAL QA AGENT   │  WORKFLOW AUTOMATOR  │
│                │                    │                      │
│  Selenium +    │  Gemini 2.5 Flash  │  Jira / GitHub       │
│  Gemini        │  ↓                 │  Slack               │
│  LLM-driven    │  Critic (self-     │  Markdown Report     │
│  navigation    │  reflection)       │  JSON Artifacts      │
│                │  ↓                 │                      │
│                │  Confidence Gate   │                      │
│                │  (0.85 threshold)  │                      │
│                │  ↓                 │                      │
│                │  Pixel-Diff        │                      │
│                │  Fallback (GCS)    │                      │
└────────────────┴────────────────────┴──────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **Visual Execution Engine** | Gemini 2.5 Flash analyzes screenshots and determines PASS/FAIL |
| **ReAct Pattern** | Observe → Reason → Judge prevents hallucinations |
| **Self-Reflection Critic** | Second Gemini call (Pro model) audits the primary analysis |
| **Confidence Gate** | < 0.85 confidence triggers pixel-diff baseline fallback |
| **Google Search Grounding** | FAIL results trigger a Gemini + Google Search call for known issues |
| **LLM-Driven Navigation** | Selenium driven by Gemini's visual reasoning, not CSS selectors |
| **Auto Bug Triage** | CRITICAL/HIGH/MEDIUM/LOW severity assigned automatically |
| **Jira / GitHub Issues** | Bug tickets pushed automatically on failure |
| **Slack Notifications** | Rich block messages with bug details |
| **Markdown + HTML Reports** | CI/CD-ready reports with audible verdict (Web Speech API) |
| **Interactive Chat** | Ask VisionQA questions about any report via API |
| **SSE Streaming** | Live-streaming analysis narration via `/v1/agent/stream` |

---

## Dual-Model Architecture

VisionQA uses two separate Gemini models in a chained multi-agent pattern:

```
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ Agent: Gemini 2.5 Flash           │   │ Critic: Gemini 2.5 Pro            │
│ Role: Primary Visual QA Inspector │→ │ Role: Adversarial Hallucination   │
│ Task: Observe → Reason → Judge    │   │       Guard + Confidence Auditor  │
│ Temp: 0.1 (precise)               │   │ Temp: 0.2 (skeptical)             │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
                                               ↓
                             Confidence < 0.85 → Pixel-Diff Fallback (GCS)
                             Status = FAIL → Google Search Grounding
```

- **Primary Agent (Flash):** Fast, cost-effective visual inspection with structured JSON output and prompt-injection defences.
- **Critic Agent (Pro):** Runs only when `--critic` flag is active. Checks for hallucinations, overconfidence, and missed defects.
- **Grounding (Flash + Google Search):** On every FAIL, a third call with the `google_search` tool surfaces known browser/CSS bugs.

See [`docs/architecture.png`](docs/architecture.png) for the full visual diagram.

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/EtornamKoko/visionqa
cd visionqa
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
```

### 2. Analyze a Screenshot

```bash
python main.py --image screenshot.png --prompt "Verify the Add to Cart button is not hidden"
```

### 3. Navigate + Inspect a Live Page

```bash
python main.py --url https://example.com --prompt "Check the heading says Example Domain"
```

### 4. Multi-Step Flow

```bash
python main.py \
  --url https://app.example.com \
  --steps "Click the Login button" "Type admin@example.com in the email field" \
  --prompt "Verify the dashboard is visible after login" \
  --critic
```

### 5. Start the API Server

```bash
python main.py --serve
# Open http://localhost:8080/docs for Swagger UI
```

---

## API Reference

### `POST /v1/agent/verify`

Analyze a screenshot against a test instruction.

**Request** (`multipart/form-data`):

| Field | Type | Required | Description |
|---|---|---|---|
| `screenshot` | File | ✅ | PNG/JPG screenshot |
| `instruction` | String | ✅ | Natural language test instruction |
| `run_critic` | Bool | ❌ | Enable hallucination self-review |
| `baseline_name` | String | ❌ | Golden baseline to compare against |
| `create_ticket` | Bool | ❌ | Auto-push ticket to Jira/GitHub |

**Response** (`200 OK`):

```json
{
  "status": "FAIL",
  "analysis": "The Pay Now button is clipped by the navigation bar.",
  "confidence": 0.93,
  "severity": "CRITICAL",
  "bug_id": "VQA-20260302-151234",
  "observations": ["Nav bar overlaps footer", "Button partially hidden"],
  "ticket_url": null,
  "report_path": "reports/visionqa_report_20260302_151234.md",
  "timestamp": "2026-03-02T15:12:34Z"
}
```

### `GET /health`

Health check for Cloud Run. Returns `200 OK` with model info.

---

## Tech Stack

| Requirement | Implementation |
|---|---|
| **Primary Agent** | `gemini-2.5-flash` — visual inspection + grounding search |
| **Critic Agent** | `gemini-2.5-pro` — hallucination guard + confidence audit |
| **Google GenAI SDK** | Python `google-genai` with `google_search` tool |
| **Cloud** | Google Cloud Run + Artifact Registry |
| **Automation** | Selenium WebDriver (headless Chrome) |
| **API** | FastAPI + Uvicorn + SSE streaming |
| **CI/CD** | GitHub Actions + Cloud Build |

---

## Output Formats

- **CLI**: Color-coded live narration with structured JSON at the end
- **API**: JSON response via `POST /v1/agent/verify`
- **Markdown Report**: `reports/visionqa_report_*.md` — suitable as CI artifact
- **Bug Ticket JSON**: `reports/VQA-*.json` — structured bug reports
- **Slack**: Rich block messages on failure

---

## Deployment

See [`docs/SETUP.md`](docs/SETUP.md) for full local and Cloud Run deployment instructions.
