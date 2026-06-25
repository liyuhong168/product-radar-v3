#!/usr/bin/env python3
"""
Product Radar V3 - Discovery Keyword Injector
Reads discovery data, injects STRONG_BUY/BUY keywords into pending_keywords.json.

Run at 11:00 (between radar scans) or after discovery data is generated.
"""
import json, sys, os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from pending_keywords import load_pending, save_pending, inject_keyword, cleanup_expired, get_stats_summary


def load_discovery_insights():
    """Load the latest discovery insights from data/discovery/."""
    disc_dir = BASE / "data" / "discovery"
    if not disc_dir.exists():
        return []

    # Find the most recent discovery file
    files = sorted(disc_dir.glob("*.json"), reverse=True)
    for f in files:
        if f.name in ("signal_scores.json", "seasonal_keywords.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            insights = data.get("insights", [])
            if insights:
                return insights
        except (json.JSONDecodeError, OSError):
            continue
    return []


def load_signal_scores():
    """Load signal scores from data/discovery/signal_scores.json."""
    fpath = BASE / "data" / "discovery" / "signal_scores.json"
    if not fpath.exists():
        return {}
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def main():
    print("=" * 50, file=sys.stderr)
    print("Discovery Keyword Injector", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    data = load_pending()
    injected = 0

    # Source 1: Discovery insights (STRONG_BUY / BUY)
    insights = load_discovery_insights()
    print(f"  Found {len(insights)} discovery insights", file=sys.stderr)

    for ins in insights:
        recommendation = ins.get("recommendation", ins.get("signal_scores", {}).get("recommendation", ""))
        if recommendation not in ("STRONG_BUY", "BUY"):
            continue

        keyword = ins.get("keyword", "")
        if not keyword:
            continue

        priority = "high" if recommendation == "STRONG_BUY" else "normal"
        trend_score = ins.get("trend_score", ins.get("signal_scores", {}).get("trend", 0))
        gap_score = ins.get("signal_scores", {}).get("gap", 0)
        reason = f"{recommendation}, trend={trend_score}, gap={gap_score}"
        ttl = 14  # Trend window ~2 weeks

        is_new = inject_keyword(
            data, keyword,
            source="discovery",
            priority=priority,
            reason=reason,
            ttl_days=ttl
        )
        if is_new:
            injected += 1
            print(f"  🔍 [{priority}] {keyword} ({reason})", file=sys.stderr)

    # Source 2: Signal scores (high-scoring keywords)
    signals = load_signal_scores()
    for kw, info in signals.items():
        final_score = info.get("final_score", info.get("signal_scores", {}).get("final", 0))
        if final_score >= 70:
            recommendation = info.get("recommendation", "BUY")
            priority = "high" if final_score >= 85 else "normal"
            reason = f"signal_score={final_score}, {recommendation}"

            is_new = inject_keyword(
                data, kw,
                source="discovery",
                priority=priority,
                reason=reason,
                ttl_days=14
            )
            if is_new:
                injected += 1
                print(f"  📊 [{priority}] {kw} (score={final_score})", file=sys.stderr)

    # Cleanup and save
    removed = cleanup_expired(data)
    save_pending(data)

    stats = get_stats_summary(data)
    print(f"\n  Summary:", file=sys.stderr)
    print(f"  - New keywords injected: {injected}", file=sys.stderr)
    print(f"  - Expired/stale removed: {removed}", file=sys.stderr)
    print(f"  - Active: {stats['active']} (urgent={stats['urgent']}, high={stats['high']}, normal={stats['normal']})",
          file=sys.stderr)

    print(json.dumps({"injected": injected, "removed": removed, "active": stats["active"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
