"""
VisionQA Baseline Manager
Golden baseline storage and pixel-level comparison for deterministic fallback.
Supports local storage with optional GCS write-through for cloud persistence.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from config import Config

# Optional GCS support — degrades gracefully if not installed
try:
    from google.cloud import storage as gcs
    _HAS_GCS = True
except ImportError:
    _HAS_GCS = False


PERSONA_PREFIX = "\033[92m[VisionQA Baselines]\033[0m"


def _narrate(message: str):
    print(f"{PERSONA_PREFIX} {message}")


class BaselineManager:
    """
    Manages 'Golden Baseline' screenshots for deterministic pixel-diff
    comparison. Acts as the fallback when Gemini confidence is below threshold.

    Storage strategy:
    - Local filesystem is always the primary cache.
    - GCS is write-through (upload on save) and read-through (download on miss).
    - Gracefully degrades to local-only if GCS is unavailable.
    """

    def __init__(self, baselines_dir: str = None):
        self.baselines_dir = baselines_dir or Config.BASELINES_DIR
        os.makedirs(self.baselines_dir, exist_ok=True)

        # Initialize GCS if available and configured
        self._gcs_bucket = None
        if _HAS_GCS and Config.GCS_BUCKET:
            try:
                gcs_client = gcs.Client()
                self._gcs_bucket = gcs_client.bucket(Config.GCS_BUCKET)
                _narrate(f"☁️  GCS enabled: gs://{Config.GCS_BUCKET}")
            except Exception as e:
                _narrate(f"⚠️  GCS unavailable ({e}). Using local storage only.")

    def _baseline_path(self, name: str) -> str:
        """Get the file path for a named baseline."""
        safe_name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return os.path.join(self.baselines_dir, f"{safe_name}.png")

    def _gcs_key(self, name: str) -> str:
        """Get the GCS object key for a named baseline."""
        safe_name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return f"baselines/{safe_name}.png"

    def _upload_to_gcs(self, local_path: str, name: str) -> bool:
        """Upload a baseline to GCS. Returns True on success."""
        if not self._gcs_bucket:
            return False
        try:
            blob = self._gcs_bucket.blob(self._gcs_key(name))
            blob.upload_from_filename(local_path)
            _narrate(f"☁️  Uploaded to GCS: {self._gcs_key(name)}")
            return True
        except Exception as e:
            _narrate(f"⚠️  GCS upload failed ({e}). Local copy retained.")
            return False

    def _download_from_gcs(self, name: str) -> bool:
        """Download a baseline from GCS to local cache. Returns True on success."""
        if not self._gcs_bucket:
            return False
        try:
            blob = self._gcs_bucket.blob(self._gcs_key(name))
            if not blob.exists():
                return False
            local_path = self._baseline_path(name)
            blob.download_to_filename(local_path)
            _narrate(f"☁️  Downloaded from GCS: {self._gcs_key(name)}")
            return True
        except Exception as e:
            _narrate(f"⚠️  GCS download failed ({e}).")
            return False

    def save_baseline(self, name: str, screenshot_path: str) -> str:
        """
        Save a screenshot as the golden baseline for a given name.
        Returns the baseline file path.
        """
        baseline_path = self._baseline_path(name)
        shutil.copy2(screenshot_path, baseline_path)
        _narrate(f"💾 Baseline saved: {name} → {baseline_path}")

        # Write-through to GCS
        self._upload_to_gcs(baseline_path, name)

        return baseline_path

    def has_baseline(self, name: str) -> bool:
        """Check if a baseline exists for the given name (local or GCS)."""
        if os.path.exists(self._baseline_path(name)):
            return True
        # Try to pull from GCS
        return self._download_from_gcs(name)

    def compare(self, name: str, current_screenshot_path: str) -> dict:
        """
        Compare a current screenshot against the golden baseline.
        Returns diff metrics and a diff image path.
        """
        baseline_path = self._baseline_path(name)

        # Try to fetch from GCS if not available locally
        if not os.path.exists(baseline_path):
            self._download_from_gcs(name)

        if not os.path.exists(baseline_path):
            _narrate(f"⚠️ No baseline found for '{name}'. Saving current as baseline.")
            self.save_baseline(name, current_screenshot_path)
            return {
                "status": "NEW_BASELINE",
                "message": f"No existing baseline. Saved current screenshot as baseline for '{name}'.",
                "diff_percentage": 0.0,
                "baseline_path": baseline_path,
            }

        _narrate(f"🔍 Comparing against baseline: {name}")

        # Load images
        baseline_img = Image.open(baseline_path).convert("RGBA")
        current_img = Image.open(current_screenshot_path).convert("RGBA")

        # Resize current to match baseline if needed
        if baseline_img.size != current_img.size:
            _narrate(f"⚠️ Size mismatch: baseline={baseline_img.size}, current={current_img.size}. Resizing.")
            current_img = current_img.resize(baseline_img.size, Image.LANCZOS)

        # Pixel-by-pixel comparison
        baseline_pixels = list(baseline_img.getdata())
        current_pixels = list(current_img.getdata())

        total_pixels = len(baseline_pixels)
        diff_count = 0
        diff_img = Image.new("RGBA", baseline_img.size)
        diff_pixels = []

        for bp, cp in zip(baseline_pixels, current_pixels):
            r_diff = abs(bp[0] - cp[0])
            g_diff = abs(bp[1] - cp[1])
            b_diff = abs(bp[2] - cp[2])

            if r_diff > 15 or g_diff > 15 or b_diff > 15:
                diff_count += 1
                # Highlight differences in red
                diff_pixels.append((255, 0, 0, 180))
            else:
                # Dim unchanged areas
                diff_pixels.append((cp[0] // 3, cp[1] // 3, cp[2] // 3, 100))

        diff_img.putdata(diff_pixels)

        # Save diff image
        diff_dir = os.path.join(self.baselines_dir, "diffs")
        os.makedirs(diff_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        diff_path = os.path.join(diff_dir, f"{name}_{timestamp}_diff.png")
        diff_img.save(diff_path)

        diff_percentage = (diff_count / total_pixels * 100) if total_pixels > 0 else 0
        threshold_pct = Config.PIXEL_DIFF_THRESHOLD * 100

        passed = diff_percentage <= threshold_pct

        if passed:
            _narrate(f"✅ Pixel diff: {diff_percentage:.2f}% (threshold: {threshold_pct:.1f}%) — PASS")
        else:
            _narrate(f"❌ Pixel diff: {diff_percentage:.2f}% (threshold: {threshold_pct:.1f}%) — FAIL")

        return {
            "status": "PASS" if passed else "FAIL",
            "diff_percentage": round(diff_percentage, 2),
            "threshold_percentage": threshold_pct,
            "total_pixels": total_pixels,
            "changed_pixels": diff_count,
            "diff_image_path": diff_path,
            "baseline_path": baseline_path,
        }

    def list_baselines(self) -> list[dict]:
        """List all stored baselines (local + GCS)."""
        seen = set()
        baselines = []

        # Local baselines
        for f in Path(self.baselines_dir).glob("*.png"):
            stat = f.stat()
            seen.add(f.stem)
            baselines.append({
                "name": f.stem,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })

        # GCS baselines (deduplicated)
        if self._gcs_bucket:
            try:
                for blob in self._gcs_bucket.list_blobs(prefix="baselines/"):
                    name = Path(blob.name).stem
                    if name not in seen:
                        baselines.append({
                            "name": name,
                            "path": f"gs://{Config.GCS_BUCKET}/{blob.name}",
                            "size_bytes": blob.size or 0,
                            "modified": blob.updated.isoformat() if blob.updated else "",
                        })
            except Exception as e:
                _narrate(f"⚠️  GCS listing failed ({e}). Showing local baselines only.")

        return baselines

    def delete_baseline(self, name: str) -> bool:
        """Delete a baseline (local + GCS)."""
        deleted = False
        path = self._baseline_path(name)
        if os.path.exists(path):
            os.remove(path)
            _narrate(f"🗑️ Deleted baseline: {name}")
            deleted = True

        # Also delete from GCS
        if self._gcs_bucket:
            try:
                blob = self._gcs_bucket.blob(self._gcs_key(name))
                if blob.exists():
                    blob.delete()
                    _narrate(f"☁️  Deleted from GCS: {self._gcs_key(name)}")
                    deleted = True
            except Exception as e:
                _narrate(f"⚠️  GCS delete failed ({e}).")

        return deleted
