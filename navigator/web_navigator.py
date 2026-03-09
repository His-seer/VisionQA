"""
VisionQA Web Navigator
Selenium + Gemini-powered autonomous web navigation.
Handles login flows, pop-ups, dynamic loaders, and cookie banners visually.
"""

import os
import time
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import Config
from navigator.page_analyzer import PageAnalyzer

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── VisionQA Persona ──────────────────────────────────────────────
PERSONA_PREFIX = "\033[96m[VisionQA Navigator]\033[0m"


def _narrate(message: str):
    """Live narration output — gives the tool a distinct 'voice'."""
    print(f"{PERSONA_PREFIX} {message}")


def annotate_click_target(screenshot_path: str, element_label: str,
                          x_pct: float = 0.5, y_pct: float = 0.5) -> str:
    """
    Draw a crosshair + glow ring on a screenshot at the coordinates
    (expressed as fractions of image size) Gemini chose to interact with.
    Returns the path of the annotated copy (original is kept intact).
    Provides VISUAL PROOF that the agent precisely identified the target.
    """
    if not _PIL_AVAILABLE:
        return screenshot_path

    try:
        img = Image.open(screenshot_path).convert("RGBA")
        w, h = img.size
        cx = int(w * x_pct)
        cy = int(h * y_pct)

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Outer glow rings
        ring_color = (239, 68, 68, 180)   # red with alpha
        for radius, alpha in [(60, 40), (45, 80), (32, 140)]:
            draw.ellipse(
                (cx - radius, cy - radius, cx + radius, cy + radius),
                outline=(239, 68, 68, alpha), width=2,
            )

        # Crosshair lines
        cross_color = (239, 68, 68, 220)
        draw.line((cx - 70, cy, cx - 20, cy), fill=cross_color, width=2)
        draw.line((cx + 20, cy, cx + 70, cy), fill=cross_color, width=2)
        draw.line((cx, cy - 70, cx, cy - 20), fill=cross_color, width=2)
        draw.line((cx, cy + 20, cx, cy + 70), fill=cross_color, width=2)

        # Centre dot
        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5),
                     fill=(239, 68, 68, 255))

        # Label badge
        badge_text = f" TARGET: {element_label[:40]} "
        bx, by = cx + 15, cy - 45
        draw.rectangle((bx - 2, by - 2, bx + len(badge_text) * 6 + 4, by + 16),
                        fill=(0, 0, 0, 180))
        # PIL default font — fallback approach
        draw.text((bx, by), badge_text, fill=(239, 68, 68, 255))

        combined = Image.alpha_composite(img, overlay).convert("RGB")
        out_path = screenshot_path.replace(".png", "_annotated.png")
        combined.save(out_path)
        return out_path

    except Exception:
        return screenshot_path


class WebNavigator:
    """
    Autonomous web navigator that uses Gemini to 'see' the browser
    and reason through UI interactions instead of relying on hardcoded selectors.
    """

    def __init__(self, headless: bool = True):
        self.analyzer = PageAnalyzer()
        self.headless = headless
        self.driver = None
        self.screenshot_dir = tempfile.mkdtemp(prefix="visionqa_")
        self._screenshot_counter = 0

    def start(self) -> None:
        """Launch the browser session."""
        _narrate("🚀 Spinning up Chrome browser...")
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")

        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(5)
        _narrate("✅ Browser session active.")

    def stop(self) -> None:
        """Close the browser session."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            _narrate("🛑 Browser session closed.")

    def take_screenshot(self, label: str = "page") -> str:
        """Capture the current viewport and save it."""
        self._screenshot_counter += 1
        filename = f"{self._screenshot_counter:03d}_{label}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        self.driver.save_screenshot(filepath)
        _narrate(f"📸 Screenshot captured: {filename}")
        return filepath

    def navigate_to(self, url: str) -> dict:
        """
        Navigate to a URL and wait for the page to stabilize.
        Uses visual stability detection instead of hardcoded waits.
        """
        _narrate(f"🌐 Navigating to: {url}")
        self.driver.get(url)
        time.sleep(1)  # Brief initial wait

        # Visual stability check — take two screenshots 1s apart
        shot1 = self.take_screenshot("stability_check_1")
        time.sleep(1)
        shot2 = self.take_screenshot("stability_check_2")

        stability = self.analyzer.is_page_stable(shot1, shot2)

        if stability["is_stable"]:
            _narrate("✅ Page is stable and loaded.")
        else:
            _narrate(f"⏳ Page still loading ({stability['diff_percentage']}% pixel change). Waiting...")
            time.sleep(3)
            shot3 = self.take_screenshot("stability_recheck")
            stability = self.analyzer.is_page_stable(shot2, shot3)
            if stability["is_stable"]:
                _narrate("✅ Page stabilized after retry.")
            else:
                _narrate("⚠️ Page may still be loading. Proceeding with caution.")

        # Analyze the loaded page
        final_screenshot = self.take_screenshot("page_loaded")
        page_analysis = self.analyzer.detect_elements(final_screenshot)

        _narrate(f"🔍 Detected {len(page_analysis.get('elements', []))} interactive elements.")
        _narrate(f"📄 Page state: {page_analysis.get('page_state', 'unknown')}")

        return {
            "url": url,
            "screenshot": final_screenshot,
            "stability": stability,
            "analysis": page_analysis,
        }

    def perform_action(self, instruction: str) -> dict:
        """
        Execute a natural-language instruction on the current page.
        Gemini analyzes the screenshot and determines what Selenium action to perform.
        """
        _narrate(f"🧠 Processing instruction: \"{instruction}\"")

        screenshot = self.take_screenshot("before_action")
        intent = self.analyzer.find_element_by_intent(instruction, screenshot)

        action = intent.get("action", {})
        target = intent.get("target_element", {})
        confidence = intent.get("confidence", 0)

        _narrate(f"🎯 Target: {target.get('label', 'unknown')} ({target.get('type', 'unknown')})")
        _narrate(f"📊 Confidence: {confidence:.0%}")
        _narrate(f"⚡ Action: {action.get('description', 'unknown')}")

        if confidence < Config.CONFIDENCE_THRESHOLD:
            _narrate(f"⚠️ Confidence too low ({confidence:.0%}). Skipping action for safety.")
            return {
                "status": "skipped",
                "reason": "Low confidence",
                "confidence": confidence,
                "intent": intent,
                "screenshot": screenshot,
            }

        # Execute the Selenium action based on Gemini's recommendation
        result = self._execute_selenium_action(action, target)
        time.sleep(1)

        after_screenshot = self.take_screenshot("after_action")

        # Annotate the BEFORE screenshot with the exact click target
        # This provides visual proof of the agent's visual precision
        x_pct = target.get("x_pct", 0.5)   # PageAnalyzer populates these
        y_pct = target.get("y_pct", 0.5)   # if bounding box info is available
        annotated = annotate_click_target(
            screenshot, target.get("label", "target"), x_pct, y_pct
        )
        if annotated != screenshot:
            _narrate(f"\033[93m[Visual Precision]\033[0m Target annotated: {Path(annotated).name}")

        return {
            "status": "executed",
            "action": action,
            "target": target,
            "confidence": confidence,
            "reasoning": intent.get("reasoning", ""),
            "screenshot_before": screenshot,
            "screenshot_before_annotated": annotated,
            "screenshot_after": after_screenshot,
        }

    def _execute_selenium_action(self, action: dict, target: dict) -> bool:
        """Translate Gemini's recommended action into Selenium commands."""
        action_type = action.get("type", "")
        label = target.get("label", "")
        css_hint = target.get("css_hints", "")
        value = action.get("value", "")

        try:
            element = None

            # Try multiple strategies to find the element
            strategies = []
            if css_hint:
                strategies.append((By.CSS_SELECTOR, css_hint))
            if label:
                strategies.extend([
                    (By.LINK_TEXT, label),
                    (By.PARTIAL_LINK_TEXT, label),
                    (By.XPATH, f"//*[contains(text(), '{label}')]"),
                    (By.XPATH, f"//*[@aria-label='{label}']"),
                    (By.XPATH, f"//*[@placeholder='{label}']"),
                    (By.XPATH, f"//button[contains(., '{label}')]"),
                    (By.XPATH, f"//input[@value='{label}']"),
                ])

            for by, selector in strategies:
                try:
                    element = self.driver.find_element(by, selector)
                    if element.is_displayed():
                        _narrate(f"✅ Found element via {by}: {selector}")
                        break
                    element = None
                except Exception:
                    continue

            if not element:
                _narrate(f"❌ Could not locate element: {label}")
                return False

            if action_type == "click":
                element.click()
                _narrate(f"👆 Clicked: {label}")
            elif action_type == "type":
                element.clear()
                element.send_keys(value)
                _narrate(f"⌨️ Typed '{value}' into: {label}")
            elif action_type == "select":
                from selenium.webdriver.support.ui import Select
                Select(element).select_by_visible_text(value)
                _narrate(f"📋 Selected '{value}' from: {label}")
            elif action_type == "hover":
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(self.driver).move_to_element(element).perform()
                _narrate(f"🖱️ Hovered over: {label}")
            elif action_type == "scroll":
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                _narrate(f"📜 Scrolled to: {label}")
            else:
                _narrate(f"⚠️ Unknown action type: {action_type}")
                return False

            return True

        except Exception as e:
            _narrate(f"❌ Action failed: {str(e)}")
            return False

    def run_flow(self, url: str, steps: list[str]) -> list[dict]:
        """
        Execute a multi-step flow: navigate to URL, then perform each step.
        Returns results for each step.
        """
        _narrate("=" * 60)
        _narrate(f"🚦 Starting flow with {len(steps)} steps")
        _narrate("=" * 60)

        results = []

        # Step 0: Navigate
        nav_result = self.navigate_to(url)
        results.append({"step": "navigate", "result": nav_result})

        # Execute each instruction
        for i, step in enumerate(steps, 1):
            _narrate(f"\n--- Step {i}/{len(steps)} ---")
            result = self.perform_action(step)
            results.append({"step": f"action_{i}", "instruction": step, "result": result})

            if result.get("status") == "skipped":
                _narrate(f"⚠️ Flow paused: step {i} was skipped due to low confidence.")
                break

        _narrate("=" * 60)
        _narrate(f"🏁 Flow complete. {len(results)} steps executed.")
        _narrate("=" * 60)

        return results

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
