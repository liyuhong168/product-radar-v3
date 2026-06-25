#!/usr/bin/env python3
"""
Product Radar - Core utilities
Provides: is_forbidden (keyword/category filter), calc_profit (margin calculator).
Scoring is handled by scoring_engine.py.
"""
import json, os, sys, re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "config.json").read_text())


def load_history(days=7):
    """Load recent snapshots for trend detection."""
    hist_dir = BASE / CONFIG["output"]["history_dir"]
    history = {}
    cutoff = datetime.now() - timedelta(days=days)
    for f in sorted(hist_dir.glob("*.json")):
        try:
            d = datetime.strptime(f.stem, "%Y-%m-%d")
            if d >= cutoff:
                data = json.loads(f.read_text())
                for item in data:
                    key = item.get("asin") or item.get("name", "").lower().strip()
                    if key not in history:
                        history[key] = []
                    history[key].append({
                        "date": f.stem,
                        "rank": item.get("rank"),
                        "price": item.get("price"),
                        "reviews": item.get("reviews"),
                        "score": item.get("score", 0)
                    })
        except (ValueError, json.JSONDecodeError):
            continue
    return history


def is_forbidden(name, category=""):
    """Check if product matches forbidden categories."""
    text = (name + " " + category).lower()
    for kw in CONFIG["forbidden_keywords"]:
        # Use word-boundary matching to avoid false positives
        # e.g., "paint" should not match "painter" or "painters"
        pattern = r'(?<![a-z])' + re.escape(kw.strip()) + r'(?![a-z])' if kw.strip().isalpha() else re.escape(kw)
        if re.search(pattern, text):
            return True, kw

    # Brand filtering (V3)
    forbidden_brands = CONFIG.get("forbidden_brands", [])
    brand_exemptions = CONFIG.get("brand_exemptions", [])
    if forbidden_brands:
        for brand in forbidden_brands:
            brand_lower = brand.lower().strip()
            if not brand_lower:
                continue
            pattern = r'(?<![a-z])' + re.escape(brand_lower) + r'(?![a-z])'
            if re.search(pattern, text):
                is_accessory = any(ex.lower() in text for ex in brand_exemptions)
                if not is_accessory:
                    return True, f"brand:{brand}"

    # Volume/weight detection - use config limits
    max_ml = 0     # 0 = reject ALL liquids (except containers)
    max_l = 0      # reject all litre-sized liquids too
    max_kg = CONFIG.get("max_weight_g", 300) / 1000  # 300g = 0.3kg

    # Skip volume check for containers (bottles, flasks, tumblers) — their volume is capacity, not content
    CONTAINER_KEYWORDS = {'bottle', 'flask', 'tumbler', 'jug', 'carafe', 'pitcher', 'thermos', 'canteen'}
    is_container = any(kw in text for kw in CONTAINER_KEYWORDS)

    if not is_container:
        # Volume: "2.5 litre", "10L", "500ml"
        vol_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:l\b|litre|litres|liter|liters)', text)
        if vol_match and float(vol_match.group(1)) > max_l:
            return True, f"体积 {vol_match.group(0)} (>{max_l*1000:.0f}ml)"

        ml_match = re.search(r'(\d+)\s*ml', text)
        if ml_match and int(ml_match.group(1)) > max_ml:
            return True, f"体积 {ml_match.group(0)} (>{max_ml}ml)"

    # Weight: "5kg", "500g"
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', text)
    if kg_match and float(kg_match.group(1)) > max_kg:
        return True, f"重量 {kg_match.group(0)} (>{max_kg*1000:.0f}g)"

    g_match = re.search(r'(\d+)\s*(?:g\b|grams?)', text)
    if g_match and int(g_match.group(1)) > CONFIG.get("max_weight_g", 300):
        return True, f"重量 {g_match.group(0)} (>{CONFIG.get('max_weight_g', 300)}g)"

    return False, None


def calc_profit(price_gbp, category="general"):
    """Calculate profit margin for a given price.
    
    Formula: VAT 16.7% + 佣金15% + 广告5% + 退货2% + FBA £1.46 + 采购£0.80
    """
    c = CONFIG["cost_structure"]
    comm_rate = c["commission_rate"]
    if "home" in category.lower() or "kitchen" in category.lower():
        comm_rate = c["commission_home"]
    elif "pet" in category.lower():
        comm_rate = c["commission_pets"]

    vat = price_gbp * c["vat_rate"]
    commission = price_gbp * comm_rate
    fba = c["fba_small_standard"]
    ads = price_gbp * c["ad_rate"]
    returns = price_gbp * c["return_rate"]
    sourcing = c.get("sourcing_cost", 0.80)

    total_cost = vat + commission + fba + ads + returns + sourcing
    net_profit = price_gbp - total_cost
    margin = net_profit / price_gbp if price_gbp > 0 else 0
    return {
        "net_profit": round(net_profit, 2),
        "margin": round(margin, 3),
        "breakdown": {
            "vat": round(vat, 2),
            "commission": round(commission, 2),
            "fba": fba,
            "ads": round(ads, 2),
            "returns": round(returns, 2),
            "sourcing": sourcing,
            "total_cost": round(total_cost, 2)
        }
    }


def get_review_tier(reviews):
    """Get review competition tier and bonus score. V3"""
    tiers = CONFIG.get("reviews", {}).get("tiers", {})
    for tier_name, tier in tiers.items():
        if tier["min"] <= reviews < tier["max"]:
            return tier_name, tier.get("bonus", 0), tier.get("label", "")
    return "unknown", 0, ""


def get_min_margin_for_price(price):
    """Get minimum profit margin based on price tier. V3"""
    margin_tiers = CONFIG.get("profit", {}).get("min_margin_by_price", {})
    for range_str, min_margin in margin_tiers.items():
        low, high = map(float, range_str.split("-"))
        if low <= price < high:
            return min_margin
    return CONFIG.get("profit", {}).get("default_min_margin", 0.22)


def load_feedback():
    """Load user feedback data. V3"""
    feedback_path = BASE / "data" / "feedback.json"
    if feedback_path.exists():
        try:
            return json.loads(feedback_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"rejected": [], "selected": {}, "outcomes": {}}


def save_feedback(feedback):
    """Save user feedback data. V3"""
    feedback_path = BASE / "data" / "feedback.json"
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text(json.dumps(feedback, indent=2, ensure_ascii=False))
