#!/usr/bin/env python3
"""
Product Radar V3 - Multi-factor scoring engine
Key changes from V2:
- Weights loaded from config.json
- Review tier system (blue_ocean → red_ocean)
- BSR trend bonus
- User feedback integration (rejected/selected)
- Discovery→Radar association bonus
- Low LQS (Listing Quality Score) bonus
"""
import json, sys, re
from pathlib import Path

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "config.json").read_text())

# Load weights from config
W = CONFIG.get("scoring", {}).get("weights", {})
P = CONFIG.get("scoring", {}).get("penalties", {})
SV = CONFIG.get("scoring", {}).get("signal_voting", {})

# Category keyword map for validation
CATEGORY_KEYWORDS = {
    "kitchen": ["kitchen", "cooking", "baking", "utensil", "gadget", "spice", "mug", "cup", "pan", "pot", "chop", "peel", "slice", "grater", "measuring", "timer", "tray", "bowl", "plate"],
    "garden": ["garden", "outdoor", "plant", "flower", "patio", "bbq", "grill", "solar", "bird", "hose", "watering", "lawn", "hedge", "seed", "pot"],
    "diy": ["diy", "tool", "drill", "screw", "nail", "hammer", "wrench", "pliers", "tape measure", "level", "saw", "clamp", "socket", "hex", "torx", "breaker"],
    "sports": ["sport", "fitness", "yoga", "gym", "exercise", "resistance", "mat", "dumbbell", "kettlebell", "band", "jump rope", "grip", "foam roller"],
    "bathroom": ["bathroom", "shower", "toilet", "towel", "soap", "mirror", "bath", "shaver", "razor", "hook", "organiser", "dispenser"],
    "cleaning": ["clean", "mop", "duster", "brush", "sponge", "vacuum", "cloth", "wipe", "stain", "lint", "lint roller"],
    "office": ["desk", "office", "stationery", "pen", "notebook", "organiser", "laptop", "mouse", "keyboard", "monitor", "stand", "file", "folder", "stapler", "clip"],
    "automotive": ["car", "vehicle", "dashboard", "phone holder", "motor", "tyre", "wheel", "wiper", "seat", "mat", "tint", "winch", "tow", "hitch", "socket", "ratchet", "wrench", "nut", "bolt", "fuse", "led", "light", "flag", "motorcycle", "bike"],
    "lighting": ["led", "light", "lamp", "night light", "strip", "fairy", "solar light", "bulb", "lantern"],
    "storage": ["storage", "organiser", "box", "basket", "shelf", "drawer", "container", "bag", "pouch", "rack"],
    "crafts": ["craft", "art", "paint", "brush", "stickers", "tape", "sewing", "knit", "crochet", "needle", "thread", "fabric", "scissors"],
    "bedding": ["bedding", "pillow", "blanket", "sheet", "duvet", "cushion", "throw", "mattress", "sleep"],
    "pets": ["pet", "dog", "cat", "collar", "leash", "bed", "grooming", "litter", "feeder", "aquarium", "fish", "hamster", "rabbit"],
    "home": ["home", "decor", "wall", "candle", "vase", "frame", "mirror", "clock", "hook", "hanger", "doormat"],
}


def _validate_category(product):
    """Check if product name actually relates to its assigned category."""
    name_lower = product.get("name", "").lower()
    category = product.get("category", "").lower()

    if not category or category == "general":
        return True, 0.5

    matched_cat = None
    for cat_key, keywords in CATEGORY_KEYWORDS.items():
        if cat_key in category:
            matched_cat = cat_key
            break

    if not matched_cat:
        return True, 0.3

    keywords = CATEGORY_KEYWORDS[matched_cat]
    hits = sum(1 for kw in keywords if kw in name_lower)

    if hits >= 2:
        return True, 1.0
    elif hits == 1:
        return True, 0.7
    else:
        best_cat = None
        best_hits = 0
        for cat_key, cat_kws in CATEGORY_KEYWORDS.items():
            cat_hits = sum(1 for kw in cat_kws if kw in name_lower)
            if cat_hits > best_hits:
                best_hits = cat_hits
                best_cat = cat_key

        if best_cat and best_hits >= 2:
            old_cat = product.get("category", "")
            product["category"] = best_cat.capitalize()
            product["category_corrected"] = True
            product["category_original"] = old_cat
            return True, 0.8

        return False, 0.0


def _classify_signal_sources(product):
    """Classify product signals into internal (Amazon) and external."""
    sources = [x.lower() for x in product.get("sources", [])]
    sources_str = " ".join(sources)
    channel = product.get("channel", "")

    internal = []
    external = []

    if "new_releases" in channel: internal.append("新品榜")
    if "bsr" in channel: internal.append("畅销榜")
    if "wished" in channel: internal.append("心愿榜")
    if "gifts" in channel: internal.append("送礼榜")
    if "movers_shakers" in channel: internal.append("飙升榜")

    if "tiktok" in sources_str: external.append("TikTok")
    if product.get("google_trend") == "rising": external.append("Google")
    if "hotukdeals" in sources_str: external.append("HotUKDeals")
    if "temu" in sources_str: external.append("Temu")
    if "etsy" in sources_str: external.append("Etsy")
    if "youtube" in sources_str: external.append("YouTube")
    if "reddit" in sources_str: external.append("Reddit")

    return internal, external, len(set(external))


def _get_signal_confidence(internal, external_count):
    """Return signal confidence level and scoring impact."""
    cfg = SV
    if external_count >= cfg.get("strong", {}).get("min_external", 3):
        c = cfg.get("strong", {})
        return "strong", c.get("label", "🔴 强信号"), c.get("bonus", 20)
    elif external_count >= cfg.get("medium", {}).get("min_external", 2):
        c = cfg.get("medium", {})
        return "medium", c.get("label", "🟠 中信号"), c.get("bonus", 10)
    elif external_count >= cfg.get("weak", {}).get("min_external", 1):
        c = cfg.get("weak", {})
        return "weak", c.get("label", "🟡 弱信号"), c.get("bonus", 0)
    else:
        c = cfg.get("none", {})
        if internal:
            return "none", c.get("label", "⚪ 仅Amazon"), c.get("bonus", -10)
        else:
            return "none", "⚪ 无信号", -15


def _has_demand_signal(product):
    """Check if product has at least one external demand signal."""
    _, _, ext_count = _classify_signal_sources(product)
    return ext_count >= 1


def _get_review_tier(reviews):
    """Get review competition tier. V3"""
    tiers = CONFIG.get("reviews", {}).get("tiers", {})
    for tier_name, tier in tiers.items():
        if tier["min"] <= reviews < tier["max"]:
            return tier_name, tier.get("bonus", 0), tier.get("label", "")
    return "unknown", 0, ""


def _load_feedback():
    """Load user feedback. V3"""
    feedback_path = BASE / "data" / "feedback.json"
    if feedback_path.exists():
        try:
            return json.loads(feedback_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"rejected": [], "selected": {}, "outcomes": {}}


def score_product(product, trend_data=None, history=None, feedback=None):
    """Calculate multi-factor weighted score. V3"""
    breakdown = {}
    total = CONFIG.get("scoring", {}).get("base", 30)

    name = product.get("name", "").lower()
    sources = [x.lower() for x in product.get("sources", [])]
    sources_str = " ".join(sources)
    reviews = product.get("reviews", 0)
    rating = product.get("rating", 0)
    margin = product.get("profit_margin", 0)
    channel = product.get("channel", "")
    asin = product.get("asin", "")

    # === User Feedback (V3) ===
    if feedback:
        if asin in feedback.get("rejected", []):
            pts = P.get("user_rejected", -30)
            total += pts; breakdown["❌ 用户已拒"] = pts
        if asin in feedback.get("selected", {}):
            pts = W.get("user_selected", 10)
            total += pts; breakdown["✅ 用户已选"] = pts

    # === Source Signals (Internal: Amazon platform) ===
    if "new_releases" in channel:
        pts = W.get("new_releases", 20)
        total += pts; breakdown["🆕 新品榜"] = pts

    if "wished" in channel:
        pts = W.get("wished", 15)
        total += pts; breakdown["💝 心愿榜"] = pts

    if "gifts" in channel:
        pts = W.get("gifts", 10)
        total += pts; breakdown["🎁 送礼榜"] = pts

    if "movers_shakers" in channel:
        pts = W.get("movers_shakers", 18)
        total += pts; breakdown["🚀 飙升榜"] = pts

    # === External Signals ===
    if "tiktok" in sources_str:
        pts = W.get("tiktok", 20)
        total += pts; breakdown["🎵 TikTok"] = pts

    if product.get("google_trend") == "rising":
        pts = W.get("google_rising", 15)
        total += pts; breakdown["📊 Google↑"] = pts

    if "reddit" in sources_str:
        pts = W.get("reddit", 5)
        total += pts; breakdown["💬 Reddit"] = pts

    if any("hotukdeals" in s for s in sources):
        pts = W.get("hotukdeals", 12)
        total += pts; breakdown["🔥 HotUKDeals"] = pts

    if any("temu" in s for s in sources):
        pts = W.get("temu", 8)
        total += pts; breakdown["🛒 Temu"] = pts

    if any("etsy" in s for s in sources):
        pts = W.get("etsy", 6)
        total += pts; breakdown["🎨 Etsy"] = pts

    if any("youtube" in s for s in sources):
        pts = W.get("youtube", 10)
        total += pts; breakdown["▶️ YouTube"] = pts

    # === Signal Voting ===
    internal, external_list, external_count = _classify_signal_sources(product)
    sig_level, sig_label, sig_pts = _get_signal_confidence(internal, external_count)
    product["signal_level"] = sig_level
    product["signal_label"] = sig_label
    product["external_sources"] = external_list
    product["internal_sources"] = internal
    if sig_pts != 0:
        total += sig_pts; breakdown[sig_label] = sig_pts

    # === AnySearch Trend Signals ===
    if trend_data:
        cat_scores = trend_data.get("category_scores", {})
        cat_evidence = trend_data.get("category_evidence", {})
        cross_validated = trend_data.get("cross_validated", {})
        category = product.get("category", "").lower()

        for cat, tscore in cat_scores.items():
            if cat in category or any(kw in name for kw in cat_evidence.get(cat, [])):
                if tscore >= 70:
                    label = "🔥 多源热门" if cat in cross_validated else "🔥 热门品类"
                    pts = W.get("hot_category", 15)
                    if cat in cross_validated:
                        pts += min(cross_validated[cat] * 2, 8)
                    total += pts; breakdown[label + f"({cat})"] = pts
                elif tscore >= 40:
                    pts = W.get("trend_category", 8)
                    total += pts; breakdown[f"📈 趋势({cat})"] = pts
                break

        for kw in trend_data.get("demand_keywords", []):
            if kw in name:
                pts = W.get("demand_keyword", 6)
                total += pts; breakdown["✨ 热词"] = pts
                break

    # === Competition (V3: Review Tier System) ===
    tier_name, tier_bonus, tier_label = _get_review_tier(reviews)
    if reviews == 0:
        if "new_releases" not in channel:
            pts = P.get("zero_review", -15)
            total += pts; breakdown["⚠️ 零评论(非新品)"] = pts
        else:
            pts = P.get("unverified", -8)
            total += pts; breakdown["⏳ 待验证"] = pts
    elif reviews < 5:
        pts = P.get("unverified", -8)
        total += pts; breakdown["⏳ 评论偏少"] = pts
    elif tier_bonus != 0:
        total += tier_bonus; breakdown[tier_label] = tier_bonus
    elif tier_name == "medium":
        pass  # No bonus or penalty

    if rating and rating >= 4.5:
        pts = W.get("high_rating", 5)
        total += pts; breakdown["⭐ 高评分"] = pts

    # === BSR Trend (V3) ===
    bsr = product.get("rank", 0)
    if bsr and bsr > 0:
        if bsr <= 50:
            pts = W.get("bsr_top50", 10)
            total += pts; breakdown["🏆 BSR Top50"] = pts
        elif bsr <= 100:
            pts = W.get("bsr_top100", 5)
            total += pts; breakdown["🏆 BSR Top100"] = pts

    # BSR trend from history
    if history:
        key = asin or product.get("name", "").lower().strip()
        if key in history and len(history[key]) >= 2:
            recent_bsr = history[key][-1].get("rank")
            older_bsr = history[key][-2].get("rank")
            if recent_bsr and older_bsr and recent_bsr < older_bsr:
                improvement = (older_bsr - recent_bsr) / older_bsr
                if improvement > 0.2:  # >20% improvement
                    pts = W.get("bsr_rising", 15)
                    total += pts; breakdown["📈 BSR上升"] = pts

    # === Profit ===
    if margin >= 0.35:
        pts = W.get("ultra_margin", 12)
        total += pts; breakdown["💰 超高利润"] = pts
    elif margin >= 0.30:
        pts = W.get("high_margin", 8)
        total += pts; breakdown["💰 高利润"] = pts
    elif margin >= 0.25:
        pts = W.get("good_margin", 4)
        total += pts; breakdown["💰 较好利润"] = pts

    # === Category Validation ===
    cat_valid, cat_confidence = _validate_category(product)
    if not cat_valid:
        pts = P.get("category_mismatch", -10)
        total += pts; breakdown["❓ 品类不符"] = pts
    elif cat_confidence < 0.5:
        pts = P.get("category_mismatch", -10) // 2
        total += pts; breakdown["❓ 品类存疑"] = pts

    # === Demand Signal Check ===
    if not _has_demand_signal(product):
        pts = P.get("no_demand_signal", -15)
        total += pts; breakdown["📉 无需求信号"] = pts

    # === Seasonal ===
    from datetime import datetime
    month = datetime.now().month
    season = "summer" if month in (6,7,8) else "winter" if month in (12,1,2) else "spring" if month in (3,4,5) else "autumn"
    seasonal_cfg = CONFIG.get("seasonal_categories", {})
    hot_kw = set(kw.lower() for kw in seasonal_cfg.get(f"{season}_hot", []))

    name_for_season = product.get("name", "").lower() + " " + product.get("category", "").lower()
    is_seasonal_hot = any(kw in name_for_season for kw in hot_kw)
    is_off_season = product.get("off_season", False)

    if is_seasonal_hot and not is_off_season:
        pts = W.get("seasonal_hot", 10)
        total += pts; breakdown[f"🌴 当季({season})"] = pts

    if is_off_season:
        pts = P.get("off_season", -20)
        total += pts; breakdown["❄️ 过季降权"] = pts

    # === Supply-Demand Index ===
    sd_score = product.get("sd_score", 0)
    sd_label = product.get("sd_label", "")
    if sd_score != 0:
        total += sd_score
        breakdown[sd_label] = sd_score

    # === Trend Divergence ===
    div_score = product.get("div_score", 0)
    div_label = product.get("div_label", "")
    if div_score != 0:
        total += div_score
        breakdown[div_label] = div_score

    # === History ===
    if history:
        key = asin or product.get("name", "").lower().strip()
        if key in history:
            hist = history[key]
            if len(hist) >= 2:
                recent = hist[-1].get("rank")
                older = hist[-2].get("rank")
                if recent and older and recent < older:
                    pts = W.get("rank_improving", 10)
                    total += pts; breakdown["📈 排名上升"] = pts
                if len(hist) >= 3:
                    scores = [h.get("score", 0) for h in hist[-3:]]
                    if all(scores[i] <= scores[i+1] for i in range(len(scores)-1)):
                        pts = W.get("consistent_growth", 8)
                        total += pts; breakdown["📊 持续上升"] = pts

    # === Discovery Verification (V3) ===
    if product.get("discovery_verified"):
        pts = W.get("discovery_verified", 15)
        total += pts; breakdown["🔍 发现验证"] = pts

    return max(total, 0), breakdown


def score_all_products(products, trend_data=None, history=None):
    """Score all products and add score fields. V3"""
    from collections import Counter

    feedback = _load_feedback()
    cat_counts = Counter(p.get("category", "unknown") for p in products)

    EVENT_KEYWORDS = {
        'world cup', 'euro', 'olympic', 'olympics', 'jubilee', 'coronation',
        'christmas', 'halloween', 'easter', 'valentine'
    }

    for p in products:
        score, breakdown = score_product(p, trend_data, history, feedback)

        # Category diversity penalty
        category = p.get("category", "unknown")
        cat_count = cat_counts.get(category, 0)
        if cat_count >= 8:
            pts = P.get("category_overflow", -10)
            score += pts; breakdown["⚠️ 品类过密"] = pts
        elif cat_count >= 5:
            pts = P.get("category_overflow", -10) // 2
            score += pts; breakdown["⚠️ 品类较多"] = pts

        # Event overflow penalty
        name_lower = p.get("name", "").lower()
        is_event = any(kw in name_lower for kw in EVENT_KEYWORDS)
        if is_event:
            event_in_cat = sum(1 for pp in products
                              if pp.get("category") == category
                              and any(kw in pp.get("name", "").lower() for kw in EVENT_KEYWORDS))
            if event_in_cat >= 4:
                pts = P.get("event_overflow", -8)
                score += pts; breakdown["🎯 事件过密"] = pts

        # Freshness bonus
        asin = p.get("asin", "")
        if history and asin not in history:
            pts = W.get("first_seen", 10)
            score += pts; breakdown["✨ 新发现"] = pts

        p["score"] = score
        p["score_breakdown"] = breakdown

        # Stars (V3: adjusted thresholds)
        if score >= 160:
            p["stars"] = 5
        elif score >= 120:
            p["stars"] = 4
        elif score >= 80:
            p["stars"] = 3
        elif score >= 50:
            p["stars"] = 2
        else:
            p["stars"] = 1

    products.sort(key=lambda x: -x.get("score", 0))
    return products


def get_score_label(score):
    if score >= 160: return "🔥 强烈推荐", "#FF2D55"
    elif score >= 120: return "⭐ 值得关注", "#FF9500"
    elif score >= 80: return "👍 可以考虑", "#007AFF"
    elif score >= 50: return "👀 待观察", "#8e8e93"
    else: return "💤 优先级低", "#c7c7cc"
