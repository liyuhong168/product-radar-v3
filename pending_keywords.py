#!/usr/bin/env python3
"""
Product Radar V3 - Pending Keywords Manager
Shared keyword queue for three-source linkage:
  1. Discovery (trend-driven) → STRONG_BUY/BUY keywords
  2. Festival (event-driven) → festival-related keywords based on sea freight deadline
  3. Radar (category-driven) → reads queue and scans
"""
import json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
PENDING_FILE = BASE / "data" / "pending_keywords.json"

# Sea freight deadline: 60 days transit + 14 days buffer = 74 days before festival
SEA_FREIGHT_LEAD_DAYS = 74


def load_pending():
    """Load pending keywords from file."""
    if PENDING_FILE.exists():
        try:
            return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"keywords": [], "stats": {"total_injected": 0, "active": 0, "expired": 0, "stale": 0}, "last_updated": ""}


def save_pending(data):
    """Save pending keywords to file."""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    # Update stats
    active = [k for k in data["keywords"] if k.get("status") == "active"]
    expired = [k for k in data["keywords"] if k.get("status") == "expired"]
    stale = [k for k in data["keywords"] if k.get("status") == "stale"]
    data["stats"]["active"] = len(active)
    data["stats"]["expired"] = len(expired)
    data["stats"]["stale"] = len(stale)
    PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def inject_keyword(data, keyword, source, priority="normal", reason="", ttl_days=14,
                   festival_id=None, festival_date=None):
    """Inject or update a keyword in the queue. Returns True if new keyword added."""
    keyword = keyword.strip().lower()
    if not keyword:
        return False

    now = datetime.now()
    expires_at = (now + timedelta(days=ttl_days)).isoformat()

    # Check for existing keyword
    existing = None
    for kw in data["keywords"]:
        if kw["keyword"] == keyword and kw.get("status") in ("active",):
            existing = kw
            break

    if existing:
        # Merge: keep highest priority, update sources
        priority_order = {"urgent": 0, "high": 1, "normal": 2}
        if priority_order.get(priority, 9) < priority_order.get(existing["priority"], 9):
            existing["priority"] = priority
        if source not in existing.get("sources", []):
            existing["sources"].append(source)
        # Keep shortest TTL (more urgent)
        if ttl_days < (existing.get("ttl_days", 999) or 999):
            existing["ttl_days"] = ttl_days
            existing["expires_at"] = expires_at
        existing["reason"] = reason or existing.get("reason", "")
        return False
    else:
        # New keyword
        kw_entry = {
            "keyword": keyword,
            "sources": [source],
            "injected_at": now.isoformat(),
            "priority": priority,
            "reason": reason,
            "ttl_days": ttl_days,
            "expires_at": expires_at,
            "scan_count": 0,
            "last_scanned": None,
            "products_found_total": 0,
            "top_score": 0,
            "top_asin": "",
            "consecutive_empty": 0,
            "status": "active"
        }
        if festival_id:
            kw_entry["festival_id"] = festival_id
        if festival_date:
            kw_entry["festival_date"] = festival_date
        data["keywords"].append(kw_entry)
        data["stats"]["total_injected"] = data["stats"].get("total_injected", 0) + 1
        return True


def cleanup_expired(data):
    """Remove expired and stale keywords. Returns count of removed."""
    now = datetime.now()
    removed = 0
    active_keywords = []
    for kw in data["keywords"]:
        if kw.get("status") != "active":
            active_keywords.append(kw)
            continue
        # Check TTL expiration
        try:
            expires = datetime.fromisoformat(kw["expires_at"])
            if now > expires:
                kw["status"] = "expired"
                removed += 1
                active_keywords.append(kw)
                continue
        except (ValueError, KeyError):
            pass
        # Check stale: 3+ consecutive empty scans
        if kw.get("consecutive_empty", 0) >= 3:
            kw["status"] = "stale"
            removed += 1
        active_keywords.append(kw)
    data["keywords"] = active_keywords
    return removed


def get_keywords_to_scan(data, max_urgent=5, max_high=10, max_normal=10):
    """Get keywords sorted by priority for scanning."""
    active = [k for k in data["keywords"] if k.get("status") == "active"]
    priority_order = {"urgent": 0, "high": 1, "normal": 2}
    active.sort(key=lambda k: (priority_order.get(k["priority"], 9), k.get("scan_count", 0)))

    result = []
    counts = {"urgent": 0, "high": 0, "normal": 0}
    for kw in active:
        p = kw["priority"]
        if p == "urgent" and counts["urgent"] < max_urgent:
            result.append(kw)
            counts["urgent"] += 1
        elif p == "high" and counts["high"] < max_high:
            result.append(kw)
            counts["high"] += 1
        elif p == "normal" and counts["normal"] < max_normal:
            result.append(kw)
            counts["normal"] += 1
    return result


def update_scan_result(data, keyword, products_found, top_score=0, top_asin=""):
    """Update keyword with scan results."""
    for kw in data["keywords"]:
        if kw["keyword"] == keyword and kw.get("status") == "active":
            kw["scan_count"] = kw.get("scan_count", 0) + 1
            kw["last_scanned"] = datetime.now().strftime("%Y-%m-%d")
            kw["products_found_total"] = kw.get("products_found_total", 0) + products_found
            if top_score > kw.get("top_score", 0):
                kw["top_score"] = top_score
                kw["top_asin"] = top_asin
            if products_found == 0:
                kw["consecutive_empty"] = kw.get("consecutive_empty", 0) + 1
                # Auto-downgrade if consecutive empty
                if kw["consecutive_empty"] >= 2 and kw["priority"] == "high":
                    kw["priority"] = "normal"
                elif kw["consecutive_empty"] >= 2 and kw["priority"] == "normal":
                    kw["status"] = "stale"
            else:
                kw["consecutive_empty"] = 0
            break


def get_stats_summary(data):
    """Get a human-readable summary of pending keywords."""
    active = [k for k in data["keywords"] if k.get("status") == "active"]
    urgent = [k for k in active if k["priority"] == "urgent"]
    high = [k for k in active if k["priority"] == "high"]
    normal = [k for k in active if k["priority"] == "normal"]
    discovery = [k for k in active if "discovery" in k.get("sources", [])]
    festival = [k for k in active if "festival" in k.get("sources", [])]
    return {
        "active": len(active),
        "urgent": len(urgent),
        "high": len(high),
        "normal": len(normal),
        "from_discovery": len(discovery),
        "from_festival": len(festival),
        "total_scans": sum(k.get("scan_count", 0) for k in active),
        "total_products": sum(k.get("products_found_total", 0) for k in active)
    }
