#!/usr/bin/env python3
"""
Product Radar V3 - Auto Build Script
Reads data from data/ directory, generates JSON files for frontend consumption.
Run after scan: python3 build_platform.py
"""
import json, sys, re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "config.json").read_text())


def get_recent_dates(days=7):
    """Get list of recent dates in YYYY-MM-DD format."""
    today = datetime.now()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def load_scan_data(date_str):
    """Load scan data for a given date."""
    channels_dir = BASE / "data" / "channels"
    # Find the latest scan file for this date
    pattern = f"{date_str}_*.json"
    files = sorted(channels_dir.glob(pattern))
    for f in files:
        if "-rejected" not in f.stem and "-trends" not in f.stem:
            try:
                return json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
    return None


def load_discovery_data(date_str):
    """Load discovery data for a given date."""
    disc_dir = BASE / "data" / "discovery"
    disc_file = disc_dir / f"{date_str}.json"
    if disc_file.exists():
        try:
            return json.loads(disc_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def build_radar_json():
    """Aggregate recent scan data → output/radar.json"""
    radar_all = {}
    for date_str in get_recent_dates(7):
        data = load_scan_data(date_str)
        if data and data.get("products"):
            radar_all[date_str] = {
                "products": data["products"],
                "scan_time": data.get("scan_time", ""),
                "scan_ts": data.get("scan_ts", ""),
                "stats": data.get("stats", {}),
                "trend_summary": data.get("trend_summary", {})
            }

    output_path = BASE / "output" / "radar.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(radar_all, ensure_ascii=False, separators=(',', ':')))
    print(f"Built radar.json: {len(radar_all)} dates, {sum(len(v['products']) for v in radar_all.values())} products")
    return radar_all


def build_discovery_json():
    """Aggregate recent discovery data → output/discovery.json"""
    disc_all = {}
    for date_str in get_recent_dates(7):
        data = load_discovery_data(date_str)
        if data:
            disc_all[date_str] = data

    output_path = BASE / "output" / "discovery.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(disc_all, ensure_ascii=False, separators=(',', ':')))
    print(f"Built discovery.json: {len(disc_all)} dates")
    return disc_all


def build_festivals_json():
    """Extract festivals data → output/festivals.json"""
    # Try to read from festivals.js
    festivals_js = BASE / "output" / "festivals.js"
    if not festivals_js.exists():
        festivals_js = BASE / "festivals_only.js"
    if not festivals_js.exists():
        festivals_js = BASE / "fest_data.js"

    if festivals_js.exists():
        content = festivals_js.read_text(encoding="utf-8")
        # Extract the JSON array from "const FESTIVALS = [...];"
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            try:
                festivals = json.loads(match.group())
                output_path = BASE / "output" / "festivals.json"
                output_path.write_text(json.dumps(festivals, ensure_ascii=False, separators=(',', ':')))
                print(f"Built festivals.json: {len(festivals)} festivals")
                return festivals
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse festivals.js: {e}")

    print("Warning: No festivals data found")
    return []


def build_signal_scores():
    """Build keyword-level signal scores → output/signals.json"""
    signals = {}
    for date_str in get_recent_dates(7):
        disc_data = load_discovery_data(date_str)
        if not disc_data:
            continue
        # Extract signal scores from discovery data
        insights = disc_data.get("insights", [])
        for ins in insights:
            kw = ins.get("keyword", "")
            if not kw:
                continue
            if kw not in signals:
                signals[kw] = {
                    "keyword": kw,
                    "keyword_cn": ins.get("keyword_cn", ""),
                    "trend_score": ins.get("trend_score", 0),
                    "signal_scores": ins.get("signal_scores", {}),
                    "first_seen": date_str,
                    "last_seen": date_str,
                    "recommendation": ins.get("signal_scores", {}).get("recommendation", "WATCH")
                }
            else:
                signals[kw]["last_seen"] = date_str
                # Update with latest scores
                if ins.get("trend_score", 0) > signals[kw]["trend_score"]:
                    signals[kw]["trend_score"] = ins.get("trend_score", 0)
                    signals[kw]["signal_scores"] = ins.get("signal_scores", {})

    output_path = BASE / "output" / "signals.json"
    output_path.write_text(json.dumps(signals, ensure_ascii=False, separators=(',', ':')))
    print(f"Built signals.json: {len(signals)} keywords")
    return signals


def build_keywords_json():
    """Build pending keywords stats → output/keywords.json"""
    pending_path = BASE / "data" / "pending_keywords.json"
    if pending_path.exists():
        try:
            data = json.loads(pending_path.read_text(encoding="utf-8"))
            # Build summary for frontend
            active = [k for k in data.get("keywords", []) if k.get("status") == "active"]
            summary = {
                "active": len(active),
                "urgent": len([k for k in active if k["priority"] == "urgent"]),
                "high": len([k for k in active if k["priority"] == "high"]),
                "normal": len([k for k in active if k["priority"] == "normal"]),
                "from_discovery": len([k for k in active if "discovery" in k.get("sources", [])]),
                "from_festival": len([k for k in active if "festival" in k.get("sources", [])]),
                "keywords": active[:20]  # Top 20 for display
            }
            output_path = BASE / "output" / "keywords.json"
            output_path.write_text(json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
            print(f"Built keywords.json: {summary['active']} active keywords")
        except (json.JSONDecodeError, OSError):
            pass


def build_feedback_json():
    """Copy feedback.json to output for frontend access."""
    feedback_path = BASE / "data" / "feedback.json"
    if feedback_path.exists():
        output_path = BASE / "output" / "feedback.json"
        output_path.write_text(feedback_path.read_text())
        print("Built feedback.json")


def build_platform_html():
    """Verify platform.html has V3 data loading code. No transformation needed."""
    template_path = BASE / "output" / "platform.html"
    if not template_path.exists():
        print("Warning: platform.html not found, skipping")
        return

    content = template_path.read_text(encoding="utf-8")

    # Verify V3 markers exist
    has_load = "loadAllData" in content
    has_fetch = "fetch('radar.json')" in content
    has_fp_init = "fpInit" in content

    if has_load and has_fetch:
        print("platform.html: V3 data loading OK")
    else:
        print("WARNING: platform.html missing V3 data loading code!")
        if not has_load:
            print("  - Missing: loadAllData function")
        if not has_fetch:
            print("  - Missing: fetch('radar.json') call")

    if has_fp_init:
        print("platform.html: fpInit present OK")
    else:
        print("WARNING: platform.html missing fpInit!")


def main():
    print("=" * 50)
    print("Product Radar V3 - Build")
    print("=" * 50)
    build_radar_json()
    build_discovery_json()
    build_festivals_json()
    build_signal_scores()
    build_keywords_json()
    build_feedback_json()
    build_platform_html()
    print("=" * 50)
    print("Build complete!")


if __name__ == "__main__":
    main()
