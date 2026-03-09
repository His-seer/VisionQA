"""
VisionQA Architecture Diagram Generator
Generates docs/architecture.png using matplotlib -- no browser needed.
Run: python docs/generate_architecture.py
"""

import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Force UTF-8 output so the print at the end works on Windows
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None

# ---- Canvas setup ---------------------------------------------------
fig, ax = plt.subplots(figsize=(22, 14))
fig.patch.set_facecolor("#0f172a")
ax.set_facecolor("#0f172a")
ax.set_xlim(0, 22)
ax.set_ylim(0, 14)
ax.axis("off")

C = {
    "bg":     "#0f172a",
    "panel":  "#1e293b",
    "border": "#334155",
    "blue":   "#3b82f6",
    "purple": "#8b5cf6",
    "green":  "#22c55e",
    "orange": "#f59e0b",
    "red":    "#ef4444",
    "indigo": "#6366f1",
    "teal":   "#14b8a6",
    "white":  "#f8fafc",
    "muted":  "#94a3b8",
    "gblue":  "#4285F4",
}


def rbox(ax, x, y, w, h, color, alpha=0.18, radius=0.3, lw=1.5, bc=None):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw, edgecolor=bc or color, facecolor=color,
        alpha=alpha, zorder=2,
    )
    ax.add_patch(box)


def header(ax, x, y, w, h, color, text, fontsize=10):
    hdr = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.2",
        linewidth=0, facecolor=color, alpha=0.9, zorder=3,
    )
    ax.add_patch(hdr)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color="#ffffff", zorder=4)


def lbl(ax, x, y, text, size=8.5, color=None, ha="center", va="center",
        bold=False, zorder=4):
    ax.text(x, y, text, ha=ha, va=va, fontsize=size,
            color=color or C["white"],
            fontweight="bold" if bold else "normal", zorder=zorder)


def pill(ax, x, y, w, h, color, text, fontsize=7.8, alpha=0.35):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.15",
        linewidth=1, edgecolor=color, facecolor=color,
        alpha=alpha, zorder=5,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=C["white"], zorder=6)


def arrow(ax, x1, y1, x2, y2, color=None, lw=1.5, dashed=False):
    ls = "dashed" if dashed else "solid"
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color or C["muted"],
                        lw=lw, linestyle=ls,
                        connectionstyle="arc3,rad=0.0"),
        zorder=3,
    )


# ====================================================================
# TITLE
# ====================================================================
ax.text(11, 13.45, "VisionQA  --  The Autonomous Visual SDET",
        ha="center", va="center", fontsize=17, fontweight="bold",
        color=C["white"], zorder=5)
ax.text(11, 13.0,
        "Gemini 2.5 Flash (Inspector)  +  Gemini 2.5 Pro (Critic)"
        "  |  Google Cloud Run  |  SSE Streaming  |  Speech Synthesis",
        ha="center", va="center", fontsize=9, color=C["muted"], zorder=5)

# ====================================================================
# LEFT -- Developer / Input
# ====================================================================
rbox(ax, 0.3, 5.8, 1.9, 2.2, C["indigo"], alpha=0.22, lw=1.5)
# Stick figure
circle = plt.Circle((1.25, 7.45), 0.3, color=C["indigo"], alpha=0.75, zorder=4)
ax.add_patch(circle)
for pts in [([1.25, 1.25], [7.15, 6.65]),
            ([0.85, 1.65], [6.85, 6.85]),
            ([1.25, 0.95], [6.65, 6.25]),
            ([1.25, 1.55], [6.65, 6.25])]:
    ax.plot(pts[0], pts[1], color=C["indigo"], lw=2.5, zorder=4)
lbl(ax, 1.25, 6.05, "Developer\n/ CI-CD", size=8, color=C["muted"])

rbox(ax, 2.5, 6.2, 2.2, 1.5, C["indigo"], alpha=0.25, lw=1.8)
header(ax, 2.5, 7.3, 2.2, 0.4, C["indigo"], "CLI / API Server", fontsize=9)
lbl(ax, 3.6, 6.85, "FastAPI + Uvicorn", size=8, color=C["muted"])
lbl(ax, 3.6, 6.50, "POST /v1/agent/verify", size=7.5, color=C["muted"])
lbl(ax, 3.6, 6.15, "GET  /v1/agent/stream (SSE)", size=7.5, color=C["muted"])
arrow(ax, 2.2, 6.95, 2.5, 6.95)

# ====================================================================
# PHASE 1 -- NAVIGATOR
# ====================================================================
rbox(ax, 5.1, 4.5, 3.6, 4.5, C["blue"], alpha=0.15, lw=1.8, bc=C["blue"])
header(ax, 5.1, 8.6, 3.6, 0.4, C["blue"], "Phase 1 -- NAVIGATOR", fontsize=9.5)
lbl(ax, 6.9, 8.1, "Selenium WebDriver", size=8.5)
lbl(ax, 6.9, 7.75, "Headless Chrome (1920x1080)", size=7.5, color=C["muted"])
ax.plot([5.3, 8.5], [7.5, 7.5], color=C["border"], lw=0.8, zorder=3)
lbl(ax, 6.9, 7.2, "Gemini 2.5 Flash", size=8.5, color=C["blue"], bold=True)
lbl(ax, 6.9, 6.85, "LLM-Driven Navigation", size=7.5, color=C["muted"])
lbl(ax, 6.9, 6.55, "No CSS selectors -- sees the screen", size=7.5, color=C["muted"])
ax.plot([5.3, 8.5], [6.3, 6.3], color=C["border"], lw=0.8, zorder=3)
pill(ax, 5.4, 5.85, 2.7, 0.35, C["blue"],   "Screenshot Capture", fontsize=7.5)
pill(ax, 5.4, 5.42, 2.7, 0.35, C["teal"],   "Visual Stability Check", fontsize=7.5)
pill(ax, 5.4, 4.99, 2.7, 0.35, C["indigo"], "navigate > action > verify", fontsize=7.5)
arrow(ax, 4.7, 6.95, 5.1, 6.95, color=C["blue"])

# ====================================================================
# PHASE 2 -- VISUAL QA AGENT
# ====================================================================
rbox(ax, 9.1, 4.5, 3.8, 4.5, C["purple"], alpha=0.15, lw=1.8, bc=C["purple"])
header(ax, 9.1, 8.6, 3.8, 0.4, C["purple"], "Phase 2 -- VISUAL QA AGENT", fontsize=9.5)
lbl(ax, 11.0, 8.1, "Gemini 2.5 Flash", size=8.5, color=C["purple"], bold=True)
lbl(ax, 11.0, 7.75, "temp=0.1  |  JSON schema output", size=7.5, color=C["muted"])
ax.plot([9.3, 12.7], [7.5, 7.5], color=C["border"], lw=0.8, zorder=3)
lbl(ax, 11.0, 7.2, "ReAct Pattern", size=8.5, bold=True)
for i, s in enumerate(["1. OBSERVE -- describe UI elements",
                        "2. REASON  -- compare vs instruction",
                        "3. JUDGE   -- PASS / FAIL + confidence"]):
    lbl(ax, 11.0, 6.85 - i * 0.32, s, size=7.3, color=C["muted"])
ax.plot([9.3, 12.7], [6.1, 6.1], color=C["border"], lw=0.8, zorder=3)
pill(ax, 9.35, 5.65, 3.35, 0.35, C["orange"], "Confidence Gate  >= 0.85", fontsize=7.5)
pill(ax, 9.35, 5.22, 3.35, 0.35, C["red"],    "FAIL  ->  Google Search Grounding", fontsize=7.5)
pill(ax, 9.35, 4.79, 3.35, 0.35, C["teal"],   "<0.85  ->  Pixel-Diff Fallback", fontsize=7.5)
arrow(ax, 8.7, 6.95, 9.1, 6.95, color=C["purple"])

# ====================================================================
# PHASE 3 -- WORKFLOW AUTOMATOR
# ====================================================================
rbox(ax, 13.3, 4.5, 3.8, 4.5, C["green"], alpha=0.15, lw=1.8, bc=C["green"])
header(ax, 13.3, 8.6, 3.8, 0.4, C["green"], "Phase 3 -- WORKFLOW AUTOMATOR", fontsize=9.5)
lbl(ax, 15.2, 8.1, "Auto Bug Triage", size=8.5, color=C["green"], bold=True)
lbl(ax, 15.2, 7.75, "CRITICAL / HIGH / MEDIUM / LOW", size=7.3, color=C["muted"])
ax.plot([13.5, 16.9], [7.5, 7.5], color=C["border"], lw=0.8, zorder=3)
pill(ax, 13.55, 7.08, 3.35, 0.34, C["indigo"], "Jira Webhook", fontsize=7.5)
pill(ax, 13.55, 6.67, 3.35, 0.34, C["green"],  "GitHub Issues", fontsize=7.5)
pill(ax, 13.55, 6.26, 3.35, 0.34, C["orange"], "Slack Notifications", fontsize=7.5)
pill(ax, 13.55, 5.85, 3.35, 0.34, C["blue"],   "Markdown + HTML Reports", fontsize=7.5)
pill(ax, 13.55, 5.44, 3.35, 0.34, C["purple"], "Speech Synthesis (HTML)", fontsize=7.5)
pill(ax, 13.55, 5.03, 3.35, 0.34, C["teal"],   "SSE Streaming Narration", fontsize=7.5)
pill(ax, 13.55, 4.62, 3.35, 0.34, C["indigo"], "Ask VisionQA (Chat API)", fontsize=7.5)
arrow(ax, 12.9, 6.95, 13.3, 6.95, color=C["green"])

# ====================================================================
# CRITIC AGENT
# ====================================================================
rbox(ax, 9.1, 10.0, 3.8, 2.6, C["red"], alpha=0.18, lw=1.8, bc="#f87171")
header(ax, 9.1, 12.2, 3.8, 0.4, "#f87171", "Critic Agent  (Gemini 2.5 Pro)", fontsize=9)
lbl(ax, 11.0, 11.75, "Adversarial Self-Reflection", size=8.5, bold=True)
lbl(ax, 11.0, 11.42, "temp=0.2  |  --critic flag", size=7.5, color=C["muted"])
ax.plot([9.3, 12.7], [11.15, 11.15], color=C["border"], lw=0.8, zorder=3)
for i, s in enumerate(["Hallucination detection",
                        "Overconfidence check",
                        "Missed-defect scan",
                        "Confidence adjustment"]):
    lbl(ax, 11.0, 10.85 - i * 0.26, "* " + s, size=7.5, color=C["muted"])
# bi-directional arrow
ax.annotate("", xy=(11.0, 9.0), xytext=(11.0, 10.0),
            arrowprops=dict(arrowstyle="<->", color="#f87171", lw=1.8,
                            connectionstyle="arc3,rad=0.0"), zorder=4)
lbl(ax, 11.85, 9.5, "self-reflection", size=7, color="#f87171", ha="left")

# ====================================================================
# GCS Baseline
# ====================================================================
rbox(ax, 17.4, 6.0, 4.2, 2.2, C["teal"], alpha=0.18, lw=1.5, bc=C["teal"])
header(ax, 17.4, 7.8, 4.2, 0.4, C["teal"], "GCS Pixel-Diff Baseline", fontsize=9)
lbl(ax, 19.5, 7.35, "Golden Baseline Storage", size=8.5)
lbl(ax, 19.5, 7.0,  "gs://visionqa-baselines", size=7.5, color=C["muted"])
lbl(ax, 19.5, 6.65, "Pixel diff < 5%  ->  PASS", size=7.5, color=C["muted"])
lbl(ax, 19.5, 6.30, "Pixel diff >= 5% ->  FAIL", size=7.5, color=C["muted"])
arrow(ax, 12.9, 5.0, 17.4, 6.8, color=C["teal"], dashed=True)

# ====================================================================
# Google Search Grounding
# ====================================================================
rbox(ax, 17.4, 3.5, 4.2, 2.2, C["orange"], alpha=0.18, lw=1.5, bc=C["orange"])
header(ax, 17.4, 5.3, 4.2, 0.4, C["orange"], "Google Search Grounding", fontsize=9)
lbl(ax, 19.5, 4.85, "Gemini 2.5 Flash  +  google_search", size=8.5)
lbl(ax, 19.5, 4.50, "Fires on every FAIL result", size=7.5, color=C["muted"])
lbl(ax, 19.5, 4.15, "Finds known CSS / a11y bugs", size=7.5, color=C["muted"])
lbl(ax, 19.5, 3.80, "Surfaces in reports + API response", size=7.5, color=C["muted"])
arrow(ax, 12.9, 5.2, 17.4, 4.6, color=C["orange"], dashed=True)

# ====================================================================
# BOTTOM -- Google Cloud strip
# ====================================================================
rbox(ax, 0.3, 0.4, 21.4, 2.8, C["gblue"], alpha=0.10, lw=1.5, bc=C["gblue"])
lbl(ax, 1.2, 2.9, "Google Cloud", size=9, color=C["gblue"], bold=True, ha="left")
cloud = [
    (1.0,  "Cloud Run\n(visionqa-api)",     C["gblue"]),
    (5.5,  "Artifact Registry\n(Docker)",   "#34a853"),
    (10.0, "Cloud Build CI/CD\n(cloudbuild.yaml)", "#fbbc04"),
    (14.5, "Secret Manager\n(GOOGLE_API_KEY)",     "#ea4335"),
    (19.0, "/health probe\n(Cloud Run)",    C["teal"]),
]
for i, (bx, txt, col) in enumerate(cloud):
    rbox(ax, bx, 0.7, 3.8, 1.8, col, alpha=0.22, lw=1.2)
    lbl(ax, bx + 1.9, 1.6, txt, size=7.8)
    if i < len(cloud) - 1:
        arrow(ax, bx + 3.8, 1.6, bx + 5.5, 1.6, color=C["gblue"], lw=1.2)
arrow(ax, 11.0, 4.5, 11.0, 3.2, color=C["gblue"], lw=1.5)
lbl(ax, 11.75, 3.85, "deploys to", size=7, color=C["gblue"], ha="left")

# ====================================================================
# LEGEND
# ====================================================================
legend_items = [
    (C["blue"],   "Phase 1 -- Navigator"),
    (C["purple"], "Phase 2 -- Visual QA Agent"),
    (C["green"],  "Phase 3 -- Workflow Automator"),
    ("#f87171",   "Critic Agent (Gemini 2.5 Pro)"),
    (C["teal"],   "GCS Pixel-Diff Fallback"),
    (C["orange"], "Google Search Grounding"),
]
for i, (col, lbl_txt) in enumerate(legend_items):
    y = 12.6 - i * 0.38
    rbox(ax, 17.4, y - 0.1, 0.35, 0.3, col, alpha=0.6, lw=0)
    ax.text(17.9, y + 0.05, lbl_txt, ha="left", va="center",
            fontsize=7.3, color=C["muted"], zorder=4)
ax.text(19.05, 13.1, "Legend", ha="left", va="center",
        fontsize=8, color=C["muted"], fontweight="bold", zorder=4)

# ---- Save -----------------------------------------------------------
out_path = os.path.join(os.path.dirname(__file__), "architecture.png")
fig.savefig(out_path, dpi=180, bbox_inches="tight",
            facecolor="#0f172a", edgecolor="none")
plt.close(fig)
print("Saved: " + out_path)
