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
    """Generate platform.html with data file references."""
    template_path = BASE / "output" / "platform.html"
    if not template_path.exists():
        print("Warning: platform.html template not found, skipping HTML build")
        return

    content = template_path.read_text(encoding="utf-8")

    # Replace inline data with fetch calls
    # Find and replace RADAR_ALL inline data
    radar_pattern = r'const RADAR_ALL\s*=\s*\{[^;]*\};'
    radar_replacement = 'let RADAR_ALL = {};\nlet DISC_ALL = {};\nlet FESTIVALS_DATA = [];\nlet SIGNALS_DATA = {};\nlet FEEDBACK_DATA = {rejected:[],selected:{},outcomes:{}};'
    content = re.sub(radar_pattern, radar_replacement, content, count=1, flags=re.DOTALL)

    # Find and replace DISC_ALL inline data
    disc_pattern = r'const DISC_ALL\s*=\s*\{[^;]*\};'
    content = re.sub(disc_pattern, '', content, count=1, flags=re.DOTALL)

    # Add data loading function before the closing </script>
    load_code = """
// ===== V3 Data Loading =====
async function loadAllData() {
  try {
    const [radar, disc, fest, sigs, fb] = await Promise.all([
      fetch('radar.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
      fetch('discovery.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
      fetch('festivals.json').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('signals.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
      fetch('feedback.json').then(r => r.ok ? r.json() : {rejected:[],selected:{},outcomes:{}}).catch(() => ({rejected:[],selected:{},outcomes:{}}))
    ]);
    RADAR_ALL = radar;
    DISC_ALL = disc;
    FESTIVALS_DATA = fest;
    SIGNALS_DATA = sigs;
    FEEDBACK_DATA = fb;

    // Update dates
    const radarDates = Object.keys(RADAR_ALL).sort().reverse();
    const discDates = Object.keys(DISC_ALL).sort().reverse();
    if (radarDates.length > 0) {
      DATES = radarDates;
      RADAR_DATES = radarDates;
    }
    if (discDates.length > 0) {
      DISC_DATES = discDates;
    }
    if (!DATES || DATES.length === 0) {
      DATES = [...new Set([...radarDates, ...discDates])].sort().reverse();
    }

    // Init
    if (typeof initDatePicker === 'function') initDatePicker(DATES, picker);
    if (typeof initDatePicker === 'function' && pickerRadar) initDatePicker(RADAR_DATES, pickerRadar);
    if (typeof renderAll === 'function') renderAll();
    if (typeof fpInit === 'function') fpInit();

    // Show freshness
    const freshnessEl = document.getElementById('dataFreshness');
    if (freshnessEl && radarDates.length > 0) {
      const latest = radarDates[0];
      const diff = Math.floor((Date.now() - new Date(latest).getTime()) / 86400000);
      const dot = diff <= 1 ? 'green' : diff <= 3 ? 'yellow' : 'orange';
      const msg = diff <= 0 ? '数据刚刚更新' : diff <= 1 ? '数据更新于昨天' : '数据已' + diff + '天未更新';
      freshnessEl.innerHTML = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--' + (dot === 'green' ? 'green' : dot === 'yellow' ? 'orange' : 'red') + ');margin-right:6px"></span>' + msg;
    }

    console.log('[V3] Data loaded:', radarDates.length, 'radar dates,', discDates.length, 'discovery dates,', fest.length, 'festivals');
  } catch (e) {
    console.error('[V3] Failed to load data:', e);
  }
}

loadAllData();
"""
    content = content.replace('</script>\n<script src="festivals.js">', load_code + '</script>\n<!-- festivals.js loaded via JSON -->\n<!--')
    content = content.replace('</script>\n<script src="festival_render.js">', '-->\n<script src="festival_render.js">')

    output_path = BASE / "output" / "platform.html"
    output_path.write_text(content, encoding="utf-8")
    print("Built platform.html (data externalized)")


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
