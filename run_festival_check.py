#!/usr/bin/env python3
"""
Product Radar V3 - Festival Deadline Checker
Reads festivals.json, calculates sea freight deadlines,
injects keywords into pending_keywords.json.

Run daily at 08:00 (before radar scan).
Also called by cron_scan.sh before each scan.
"""
import json, sys, re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
from pending_keywords import (
    load_pending, save_pending, inject_keyword, cleanup_expired,
    SEA_FREIGHT_LEAD_DAYS
)


def load_festivals():
    """Load festivals from output/festivals.json."""
    fpath = BASE / "output" / "festivals.json"
    if not fpath.exists():
        # Try alternative locations
        for alt in ["festivals_only.js", "fest_data.js"]:
            alt_path = BASE / alt
            if alt_path.exists():
                content = alt_path.read_text(encoding="utf-8")
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
        print("Warning: No festivals data found", file=sys.stderr)
        return []
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def extract_festival_keywords(festival):
    """Extract Amazon search keywords from festival data."""
    keywords = set()

    # 1. Festival English name (cleaned)
    name_en = festival.get("nameEn", "")
    if name_en:
        # Take first 3-4 words as search term
        words = name_en.split()[:4]
        keywords.add(" ".join(words).lower())

    # 2. SKU keywords
    for product in festival.get("products", []):
        for kw in product.get("keywords", []):
            keywords.add(kw.lower())
        # Also add SKU English name
        sku_en = product.get("skuEn", "")
        if sku_en and len(sku_en) > 5:
            # Take first 3 words
            words = sku_en.split()[:3]
            keywords.add(" ".join(words).lower())

    # 3. Category-based keywords
    categories = set()
    for product in festival.get("products", []):
        cat = product.get("category", "")
        if cat:
            categories.add(cat)

    # Combine category + festival name for more specific searches
    for cat in categories:
        if name_en:
            first_word = name_en.split()[0].lower() if name_en.split() else ""
            if first_word:
                keywords.add(f"{cat} {first_word}")

    # Filter out too-short or generic keywords
    filtered = set()
    for kw in keywords:
        kw = kw.strip()
        if len(kw) >= 5 and not kw.isdigit():
            filtered.add(kw)

    return list(filtered)[:8]  # Max 8 keywords per festival


def main():
    print("=" * 50, file=sys.stderr)
    print("Festival Deadline Checker", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    festivals = load_festivals()
    if not festivals:
        print("No festivals found", file=sys.stderr)
        return

    data = load_pending()
    today = datetime.now().date()
    injected = 0
    upgraded = 0

    for fest in festivals:
        fest_date_str = fest.get("date", "")
        if not fest_date_str:
            continue

        try:
            fest_date = datetime.strptime(fest_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Calculate sea freight deadline
        deadline = fest_date - timedelta(days=SEA_FREIGHT_LEAD_DAYS)
        days_to_deadline = (deadline - today).days

        # Skip if deadline is past or too far (>90 days)
        if days_to_deadline < 0:
            continue
        if days_to_deadline > 90:
            continue

        # Determine priority based on days to deadline
        if days_to_deadline <= 7:
            priority = "urgent"
            ttl = 7
        elif days_to_deadline <= 30:
            priority = "high"
            ttl = 30
        else:
            priority = "normal"
            ttl = days_to_deadline

        # Extract keywords
        keywords = extract_festival_keywords(fest)
        fest_name = fest.get("name", fest.get("nameEn", ""))
        fest_id = fest.get("id", "")

        print(f"  {fest.get('icon', '📅')} {fest_name}: {len(keywords)} keywords, "
              f"deadline={deadline}, {days_to_deadline}d left, priority={priority}",
              file=sys.stderr)

        for kw in keywords:
            is_new = inject_keyword(
                data, kw,
                source="festival",
                priority=priority,
                reason=f"{fest_name} 海运截止{days_to_deadline}天",
                ttl_days=ttl,
                festival_id=fest_id,
                festival_date=fest_date_str
            )
            if is_new:
                injected += 1

    # Cleanup expired
    removed = cleanup_expired(data)
    save_pending(data)

    # Print summary
    from pending_keywords import get_stats_summary
    stats = get_stats_summary(data)
    print(f"\n  Summary:", file=sys.stderr)
    print(f"  - New keywords injected: {injected}", file=sys.stderr)
    print(f"  - Expired/stale removed: {removed}", file=sys.stderr)
    print(f"  - Active keywords: {stats['active']} "
          f"(urgent={stats['urgent']}, high={stats['high']}, normal={stats['normal']})",
          file=sys.stderr)
    print(f"  - From discovery: {stats['from_discovery']}, from festival: {stats['from_festival']}",
          file=sys.stderr)

    # Output JSON summary for cron
    print(json.dumps({
        "injected": injected,
        "removed": removed,
        "active": stats["active"],
        "urgent": stats["urgent"],
        "high": stats["high"],
        "normal": stats["normal"]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
