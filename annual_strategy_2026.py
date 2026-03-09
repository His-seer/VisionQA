import os, sys

SKILL_DIR = os.path.expanduser("~/.claude/skills/create-pptx")
if os.path.exists(".claude/skills/create-pptx"):
    SKILL_DIR = os.path.abspath(".claude/skills/create-pptx")
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

from pptx_bcg_patterns import BCGSlideBuilder

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Annual_Strategy_2026.pptx")

bcg = BCGSlideBuilder(
    os.path.join(SKILL_DIR, "assets/templates/AmaliTech_Blank.pptx"),
    os.path.join(SKILL_DIR, "assets/brand_config.json")
)

bcg.preload_icons(['chart', 'rocket', 'target', 'check', 'calendar', 'team', 'lightbulb', 'arrow-right'])

# ─── Slide 1: Title ───────────────────────────────────────────────────────────
bcg.add_title_slide(
    title="Annual Strategy Planning 2026",
    subtitle="Aligning our team on priorities, roadmap, and goals for the year ahead",
    date="March 2026",
    notes="Welcome everyone. Today we're covering where we've been, where we are, and exactly where we're headed in 2026. This session is designed to align the full team on our shared priorities."
)

# ─── Slide 2: Agenda (as process flow) ───────────────────────────────────────
bcg.add_process_flow_slide(
    title="Today's session: recap, priorities, and decisions",
    steps=[
        {"label": "2025 Recap", "description": "Wins & lessons learned"},
        {"label": "Highlights", "description": "Key performance metrics"},
        {"label": "Priorities", "description": "Three focus areas for 2026"},
        {"label": "Roadmap", "description": "Q1–Q4 milestones"},
        {"label": "Decisions", "description": "Actions needed today"},
    ],
    notes="Here's how the session is structured. We'll spend most time on priorities and the roadmap — that's where we need alignment before we leave today."
)

# ─── Slide 3: Last Year's Recap (SCR) ────────────────────────────────────────
bcg.add_scr_slide(
    title="2025 delivered growth, but exposed gaps to close",
    situation=[
        {"text": "Revenue grew 22% YoY to $4.9M, beating target by 7%", "highlights": ["22%", "$4.9M", "7%"]},
        {"text": "Customer base expanded from 310 to 415 active accounts", "highlights": ["310", "415"]},
        {"text": "Delivery delays hit 31% of Q3 projects — capacity gap exposed", "highlights": ["31%"]},
        {"text": "Customer churn rose to 14% vs 9% target", "highlights": ["14%", "9%"]},
    ],
    resolution=[
        {"type": "heading", "text": "Lessons Carried Into 2026"},
        {"text": "Scale delivery capacity before committing new accounts", "highlights": []},
        {"text": "Launch retention program targeting at-risk accounts by Q2", "highlights": ["Q2"]},
        {"text": "Implement cost governance for all tooling spend", "highlights": []},
    ],
    callout="Decision needed: Approve H1 2026 headcount plan before end of March",
    source="Internal performance review, Q4 2025",
    notes="This slide captures the honest picture of 2025. The growth story is real — 22% is strong. But the gaps in retention and delivery are what we need to address head-on this year."
)

# ─── Slide 4: 2025 Performance Highlights ────────────────────────────────────
bcg.add_stats_slide(
    title="2025 performance: strong top-line with room to improve",
    stats=[
        {"value": "22%", "label": "Revenue Growth YoY"},
        {"value": "415", "label": "Active Accounts"},
        {"value": "87%", "label": "Employee Engagement"},
        {"value": "14%", "label": "Customer Churn Rate"},
    ],
    source="Internal HR & Finance Report, Q4 2025",
    notes="Four headline numbers from 2025. Three green, one red. The churn number is the one to watch — it's the thread we'll pull on hardest this year."
)

# ─── Slide 5: Strategic Priorities 2026 ──────────────────────────────────────
bcg.add_icon_bullets_slide(
    title="Three priorities will define our success in 2026",
    items=[
        {
            "icon": "target",
            "title": "Retain & Grow Existing Accounts",
            "description": "Reduce churn 14% → 8% via proactive retention program and quarterly account reviews for top 50 clients.",
        },
        {
            "icon": "rocket",
            "title": "Scale Delivery Without Sacrificing Quality",
            "description": "Hire 12 delivery roles in H1, standardise delivery playbook, reach 90%+ on-time rate by Q3 2026.",
        },
        {
            "icon": "lightbulb",
            "title": "Build Repeatable, Scalable Processes",
            "description": "Deploy cost governance, automate 60% of internal reporting by Q2, cut onboarding time by 30%.",
        },
    ],
    source="Leadership Strategy Session, Feb 2026",
    notes="Three priorities sequenced intentionally — retention first (cheapest growth), delivery second (unlocks revenue), process third (makes it sustainable)."
)

# ─── Slide 6: 2026 Roadmap ────────────────────────────────────────────────────
bcg.add_gantt_slide(
    title="2026 roadmap: phased delivery across all three priorities",
    columns=["Q1", "Q2", "Q3", "Q4"],
    tasks=[
        {
            "name": "Retention program launch",
            "bars": [{"start": 0, "span": 1, "status": "done"}]
        },
        {
            "name": "Quarterly business reviews (top 50)",
            "bars": [{"start": 1, "span": 3, "status": "planned"}]
        },
        {
            "name": "H1 delivery hiring (12 roles)",
            "bars": [{"start": 0, "span": 2, "status": "done"}]
        },
        {
            "name": "Delivery playbook rollout",
            "bars": [{"start": 1, "span": 1, "status": "planned"}]
        },
        {
            "name": "90% on-time delivery target",
            "bars": [{"start": 2, "span": 2, "status": "planned"}]
        },
        {
            "name": "Cost governance framework",
            "bars": [{"start": 0, "span": 1, "status": "done"}]
        },
        {
            "name": "Internal reporting automation",
            "bars": [{"start": 1, "span": 1, "status": "planned"}]
        },
        {
            "name": "Internal knowledge-base launch",
            "bars": [{"start": 2, "span": 1, "status": "planned"}]
        },
    ],
    legend=[
        {"label": "Underway", "color": "accent"},
        {"label": "Planned", "color": "primary"},
    ],
    source="PMO Planning, March 2026",
    notes="Eight workstreams mapped across four quarters. The orange bars are already underway — we're not starting from zero. The blue bars require decisions and resources we're discussing today."
)

# ─── Slide 7: Next Steps & Decisions ─────────────────────────────────────────
bcg.add_decisions_slide(
    title="Three decisions needed to unlock the 2026 plan",
    decisions=[
        {
            "action": "Approve H1 headcount plan (12 delivery roles)",
            "owner": "Leadership Team",
            "date": "31 Mar 2026",
            "icon": "team"
        },
        {
            "action": "Sign off on retention program budget ($85K)",
            "owner": "Finance & CEO",
            "date": "15 Apr 2026",
            "icon": "money"
        },
        {
            "action": "Assign cost governance framework lead",
            "owner": "COO",
            "date": "15 Apr 2026",
            "icon": "target"
        },
    ],
    source="Strategy Session, March 2026",
    notes="Three concrete decisions. Each one unlocks a priority. If we leave today with these three approved, the team can execute. If not, flag which one is blocked and we'll address it immediately."
)

# ─── Slide 8: End ─────────────────────────────────────────────────────────────
bcg.add_end_slide("Questions & Discussion")

# ─── Score & Save ─────────────────────────────────────────────────────────────
result = bcg.score_quality()
print(f"\nQuality Score: {result['total']}/100 — Passed: {result['passed']}")
for k, v in result['scores'].items():
    print(f"  {k}: {v}")
if result.get('suggestions'):
    print("\nSuggestions:")
    for s in result['suggestions']:
        print(f"  - {s}")

bcg.save(OUTPUT)
print(f"\nSaved: {OUTPUT}")
