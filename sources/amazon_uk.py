#!/usr/bin/env python3
"""Amazon UK data fetcher v2 - New Releases + BSR with channel tagging"""
import json, subprocess, re, sys, random, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).parent.parent
CONFIG = json.loads((BASE / "config.json").read_text())

# Amazon UK URLs with channel type
AMAZON_URLS = {
    # === NEW RELEASES ===
    "Kitchen|new_releases": "https://www.amazon.co.uk/gp/new-releases/kitchen/",
    "Garden|new_releases": "https://www.amazon.co.uk/gp/new-releases/garden/",
    "DIY|new_releases": "https://www.amazon.co.uk/gp/new-releases/diy/",
    "Sports|new_releases": "https://www.amazon.co.uk/gp/new-releases/sports/",
    "Bathroom|new_releases": "https://www.amazon.co.uk/gp/new-releases/bathroom/",
    "Cleaning|new_releases": "https://www.amazon.co.uk/gp/new-releases/cleaning/",
    "Office|new_releases": "https://www.amazon.co.uk/gp/new-releases/stationery-office/",
    "Automotive|new_releases": "https://www.amazon.co.uk/gp/new-releases/automotive/",
    "Lighting|new_releases": "https://www.amazon.co.uk/gp/new-releases/lighting/",
    "Storage|new_releases": "https://www.amazon.co.uk/gp/new-releases/kitchen/storage-accessories/",
    "Crafts|new_releases": "https://www.amazon.co.uk/gp/new-releases/diy-craft-tools/",
    "Bedding|new_releases": "https://www.amazon.co.uk/gp/new-releases/bedding/",
    "Pets|new_releases": "https://www.amazon.co.uk/gp/new-releases/pet-supplies/",
    "Home|new_releases": "https://www.amazon.co.uk/gp/new-releases/home/",
    "Phone|new_releases": "https://www.amazon.co.uk/gp/new-releases/mobile-phone-accessories/",
    "Tech|new_releases": "https://www.amazon.co.uk/gp/new-releases/computers-accessories/",
    "Travel|new_releases": "https://www.amazon.co.uk/gp/new-releases/sport-leisure/travel-accessories/",
    "Party|new_releases": "https://www.amazon.co.uk/gp/new-releases/party-supplies-balloons/",
    # === BESTSELLERS (BSR) ===
    "Kitchen|bsr": "https://www.amazon.co.uk/gp/bestsellers/kitchen/",
    "Garden|bsr": "https://www.amazon.co.uk/gp/bestsellers/garden/",
    "DIY|bsr": "https://www.amazon.co.uk/gp/bestsellers/diy/",
    "Sports|bsr": "https://www.amazon.co.uk/gp/bestsellers/sports/",
    "Home|bsr": "https://www.amazon.co.uk/gp/bestsellers/home/",
    "Automotive|bsr": "https://www.amazon.co.uk/gp/bestsellers/automotive/",
    "Crafts|bsr": "https://www.amazon.co.uk/gp/bestsellers/diy-craft-tools/",
    "Office|bsr": "https://www.amazon.co.uk/gp/bestsellers/stationery-office/",
    "Bathroom|bsr": "https://www.amazon.co.uk/gp/bestsellers/bathroom/",
    "Cleaning|bsr": "https://www.amazon.co.uk/gp/bestsellers/cleaning/",
    "Lighting|bsr": "https://www.amazon.co.uk/gp/bestsellers/lighting/",
    "Bedding|bsr": "https://www.amazon.co.uk/gp/bestsellers/bedding/",
    "Pets|bsr": "https://www.amazon.co.uk/gp/bestsellers/pet-supplies/",
    "Phone|bsr": "https://www.amazon.co.uk/gp/bestsellers/mobile-phone-accessories/",
    "Tech|bsr": "https://www.amazon.co.uk/gp/bestsellers/computers-accessories/",
    # === MOST WISHED FOR (需求信号) ===
    "Kitchen|wished": "https://www.amazon.co.uk/gp/most-wished-for/kitchen/",
    "Garden|wished": "https://www.amazon.co.uk/gp/most-wished-for/garden/",
    "DIY|wished": "https://www.amazon.co.uk/gp/most-wished-for/diy/",
    "Sports|wished": "https://www.amazon.co.uk/gp/most-wished-for/sports/",
    "Home|wished": "https://www.amazon.co.uk/gp/most-wished-for/home/",
    "Automotive|wished": "https://www.amazon.co.uk/gp/most-wished-for/automotive/",
    "Pets|wished": "https://www.amazon.co.uk/gp/most-wished-for/pet-supplies/",
    "Office|wished": "https://www.amazon.co.uk/gp/most-wished-for/stationery-office/",
    "Phone|wished": "https://www.amazon.co.uk/gp/most-wished-for/mobile-phone-accessories/",
    # === GIFT IDEAS (送礼需求) ===
    "Kitchen|gifts": "https://www.amazon.co.uk/gp/gifts/kitchen/",
    "Garden|gifts": "https://www.amazon.co.uk/gp/gifts/garden/",
    "DIY|gifts": "https://www.amazon.co.uk/gp/gifts/diy/",
    "Home|gifts": "https://www.amazon.co.uk/gp/gifts/home/",
    # === MOVERS & SHAKERS (排名飙升) ===
    "Kitchen|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/kitchen/",
    "Garden|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/garden/",
    "DIY|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/diy/",
    "Sports|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/sports/",
    "Home|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/home/",
    "Automotive|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/automotive/",
    "Pets|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/pet-supplies/",
    "Office|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/stationery-office/",
    "Bathroom|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/bathroom/",
    "Lighting|movers_shakers": "https://www.amazon.co.uk/gp/movers-and-shakers/lighting/",
}

GBP_COOKIES = "lc-main=en_GB; i18n-prefs=GBP"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

CHANNEL_NAMES = {
    "new_releases": "Amazon新品榜",
    "bsr": "Amazon畅销榜",
    "wished": "Amazon心愿榜",
    "gifts": "Amazon送礼榜",
    "movers_shakers": "Amazon飙升榜",
}

# Category validation keywords — product name must contain at least one
CATEGORY_VALIDATORS = {
    "Kitchen": ["kitchen", "cooking", "baking", "utensil", "gadget", "spice", "mug", "cup", "pan", "pot", "chop", "peel", "slice", "grater", "measuring", "timer", "tray", "bowl", "plate", "coffee", "tea", "stove", "oven", "dish", "cutlery", "ladle", "whisk", "tongs", "colander", "sieve"],
    "Garden": ["garden", "outdoor", "plant", "flower", "patio", "bbq", "grill", "solar", "bird", "hose", "watering", "lawn", "hedge", "seed", "pot", "soil", "compost", "fence", "decking", "terrace", "planter", "trellis"],
    "DIY": ["diy", "tool", "drill", "screw", "nail", "hammer", "wrench", "pliers", "tape measure", "level", "saw", "clamp", "socket", "hex", "torx", "breaker", "spanner", "ratchet", "chisel", "sandpaper", "paint roller"],
    "Sports": ["sport", "fitness", "yoga", "gym", "exercise", "resistance", "mat", "dumbbell", "kettlebell", "band", "jump rope", "grip", "foam roller", "running", "cycling", "swimming", "camping", "hiking", "ball", "racket"],
    "Bathroom": ["bathroom", "shower", "toilet", "towel", "soap", "mirror", "bath", "shaver", "razor", "hook", "organiser", "dispenser", "toothbrush", "tumbler", "mat", "rail", "caddy"],
    "Cleaning": ["clean", "mop", "duster", "brush", "sponge", "vacuum", "cloth", "wipe", "stain", "lint", "scrub", "squeegee", "broom", "dustpan", "bucket"],
    "Office": ["desk", "office", "stationery", "pen", "notebook", "organiser", "laptop", "mouse", "keyboard", "monitor", "stand", "file", "folder", "stapler", "clip", "marker", "highlighter", "diary", "planner"],
    "Automotive": ["car", "vehicle", "dashboard", "phone holder", "motor", "tyre", "wheel", "wiper", "seat", "mat", "winch", "tow", "hitch", "socket", "ratchet", "wrench", "nut", "bolt", "fuse", "led", "light", "motorcycle", "bike", "engine", "oil", "brake", "bumper", "mudguard"],
    "Lighting": ["led", "light", "lamp", "night light", "strip", "fairy", "solar light", "bulb", "lantern", "chandelier", "spotlight", "dimmer"],
    "Storage": ["storage", "organiser", "box", "basket", "shelf", "drawer", "container", "bag", "pouch", "rack", "crate", "bin", "caddy"],
    "Crafts": ["craft", "art", "paint", "brush", "sticker", "tape", "sewing", "knit", "crochet", "needle", "thread", "fabric", "scissors", "bead", "ribbon", "washi", "vinyl", "resin", "mould"],
    "Bedding": ["bedding", "pillow", "blanket", "sheet", "duvet", "cushion", "throw", "mattress", "sleep", "quilt", "comforter"],
    "Pets": ["pet", "dog", "cat", "collar", "leash", "bed", "grooming", "litter", "feeder", "aquarium", "fish", "hamster", "rabbit", "puppy", "kitten", "paw", "chew", "scratch"],
    "Home": ["home", "decor", "wall", "candle", "vase", "frame", "mirror", "clock", "hook", "hanger", "doormat", "curtain", "blind", "rug", "carpet"],
    "Phone": ["phone", "mobile", "iphone", "samsung galaxy", "case", "screen protector", "tempered glass", "sim card", "earphone", "earbuds", "headphone", "pop socket", "magsafe"],
    "Tech": ["laptop", "computer", "tablet", "keyboard", "mouse", "webcam", "usb", "hub", "docking", "monitor", "ethernet", "wifi", "bluetooth", "speaker", "headset", "micro sd", "memory card", "cable", "adapter"],
    "Travel": ["travel", "luggage", "suitcase", "packing", "passport", "luggage tag", "neck pillow", "eye mask", "toiletry", "travel adapter", "compression", "organiser bag"],
    "Party": ["party", "balloon", "birthday", "banner", "confetti", "bunting", "decoration", "disposable", "plates", "napkin", "cupcake", "candle"],
}


SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")

def _is_valid_response(html):
    """Check if Amazon response contains real product data."""
    if not html:
        return False
    low = html.lower()
    if "captcha" in low or "api-services-support@amazon" in low:
        return False
    if "data-asin" not in html:
        return False
    return True

def _curl_fetch(url):
    """Fetch a page with curl, forcing GBP. Falls back to ScraperAPI if blocked."""
    # Try direct request first
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--compressed",
             "--connect-timeout", "10", "--max-time", "30",
             "-H", f"User-Agent: {USER_AGENT}",
             "-H", "Accept-Language: en-GB,en;q=0.9",
             "-b", GBP_COOKIES,
             url],
            capture_output=True, text=True, timeout=45
        )
        if _is_valid_response(result.stdout):
            return result.stdout
        print(f"  Direct request blocked/invalid (len={len(result.stdout)}), trying ScraperAPI...", file=sys.stderr)
    except Exception as e:
        print(f"  curl error: {e}, trying ScraperAPI...", file=sys.stderr)

    # Fallback: ScraperAPI
    if SCRAPER_API_KEY:
        try:
            proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
            result = subprocess.run(
                ["curl", "-s", "-L", "--compressed",
                 "--connect-timeout", "15", "--max-time", "45",
                 proxy_url],
                capture_output=True, text=True, timeout=60
            )
            if _is_valid_response(result.stdout):
                print(f"  ScraperAPI OK (len={len(result.stdout)})", file=sys.stderr)
                return result.stdout
            print(f"  ScraperAPI also failed (len={len(result.stdout)})", file=sys.stderr)
        except Exception as e:
            print(f"  ScraperAPI error: {e}", file=sys.stderr)
    else:
        print("  No SCRAPER_API_KEY set, skipping fallback", file=sys.stderr)

    # Fallback: CloakBrowser (stealth browser, passes all bot detection)
    try:
        from sources.browser_fetch import fetch_url
        print("  Trying CloakBrowser...", file=sys.stderr, end="")
        html = fetch_url(url, wait_for="[data-asin]")
        if html and _is_valid_response(html):
            print(f" OK (len={len(html)})", file=sys.stderr)
            return html
        print(f" failed", file=sys.stderr)
    except ImportError:
        pass  # CloakBrowser not installed
    except Exception as e:
        print(f" error: {e}", file=sys.stderr)

    return ""


def _parse_amazon_page(html, category, channel_type):
    """Parse Amazon page HTML for products."""
    products = []
    if not html or len(html) < 1000:
        return products

    import html as htmlmod

    # Split HTML by data-asin blocks for per-product extraction
    blocks = re.split(r'data-asin="([A-Z0-9]{10})"', html)

    seen_asins = set()
    for i in range(1, len(blocks) - 1, 2):
        asin = blocks[i]
        block = blocks[i + 1]

        if asin in seen_asins or not asin:
            continue
        seen_asins.add(asin)

        # Extract title from <img alt="..."> in this block
        title_match = re.search(r'<img[^>]*alt="([^"]{15,300})"', block)
        title = htmlmod.unescape(title_match.group(1)).strip() if title_match else ""
        title = re.sub(r'\s+', ' ', title).strip()

        # Extract image URL from <img src="...amazon.com/images/I/..."> in this block
        # Exclude .js files — they also contain /images/I/ in the path
        img_url = ""
        img_match = re.search(r'<img[^>]*src="(https?://[^"]*amazon\.com/images/I/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.I)
        if not img_match:
            img_match = re.search(r'<img[^>]*src="(https?://[^"]*amazon\.com/images/I/[^"]+_AC_[^"]*)"', block)
        if img_match:
            img_url = img_match.group(1)

        # Extract price in this block
        price_match = re.search(r'£(\d+\.\d{2})', block)
        price = float(price_match.group(1)) if price_match else 0

        # Extract review count in this block
        review_match = re.search(r'>(\d[\d,]*)</span>\s*</a>', block)
        if not review_match:
            review_match = re.search(r'(\d[\d,]+)\s*(?:ratings?|reviews?)', block, re.I)
        review_count = int(review_match.group(1).replace(",", "")) if review_match else 0

        # Extract rating in this block
        rating_match = re.search(r'(\d+\.?\d?)\s*out of\s*5', block)
        rating = float(rating_match.group(1)) if rating_match else 0

        if title and price > 0:
            # Validate category: skip products whose name doesn't match the page category
            title_lower = title.lower()
            validators = CATEGORY_VALIDATORS.get(category, [])
            if validators and not any(kw in title_lower for kw in validators):
                continue  # Skip cross-category contamination

            products.append({
                "asin": asin,
                "name": title[:120],
                "price": price,
                "reviews": review_count,
                "rating": rating,
                "rank": len(products) + 1,
                "category": category,
                "channel": channel_type,
                "channel_name": CHANNEL_NAMES.get(channel_type, channel_type),
                "review_info": f"{review_count} reviews, {rating}★" if rating else f"{review_count} reviews",
                "amazon_url": f"https://www.amazon.co.uk/dp/{asin}",
                "image_url": img_url,
            })

    return products


def fetch(max_per_channel_type=8):
    """Fetch Amazon UK data from New Releases and BSR."""
    all_products = []
    seen_asins = set()

    # Category rotation per channel type
    rotation_file = BASE / "data" / "last_categories_v2.json"
    last_cats = {}
    if rotation_file.exists():
        try:
            last_cats = json.loads(rotation_file.read_text())
        except Exception:
            pass

    # Group URLs by channel type
    by_channel = {}
    for key, url in AMAZON_URLS.items():
        cat, ch = key.split("|")
        by_channel.setdefault(ch, []).append((cat, url))

    selected_keys = []
    for channel_type, entries in by_channel.items():
        last = last_cats.get(channel_type, [])
        uncovered = [e for e in entries if e[0] not in last]
        if len(uncovered) >= max_per_channel_type:
            picked = random.sample(uncovered, max_per_channel_type)
        else:
            picked = uncovered[:]
            remaining = [e for e in entries if e[0] not in [p[0] for p in picked]]
            picked.extend(random.sample(remaining, min(max_per_channel_type - len(picked), len(remaining))))

        for cat, url in picked:
            selected_keys.append((cat, channel_type, url))
        last_cats[channel_type] = [p[0] for p in picked]

    # Save rotation
    rotation_file.parent.mkdir(parents=True, exist_ok=True)
    rotation_file.write_text(json.dumps(last_cats))

    # Fetch URLs in parallel (8 concurrent threads)
    def _fetch_one(item):
        category, channel_type, url = item
        html = _curl_fetch(url)
        if not html:
            print(f"  warn {category}/{channel_type}: empty", file=sys.stderr)
            return (category, channel_type, [])
        products = _parse_amazon_page(html, category, channel_type)
        new_count = len(products)
        print(f"  ok {category}/{channel_type}: {new_count} new", file=sys.stderr)
        return (category, channel_type, products)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, item): item for item in selected_keys}
        for future in as_completed(futures):
            category, channel_type, products = future.result()
            for p in products:
                if p["asin"] not in seen_asins:
                    seen_asins.add(p["asin"])
                    all_products.append(p)

    # Summary by channel
    for ch in CHANNEL_NAMES:
        count = sum(1 for p in all_products if p["channel"] == ch)
        print(f"  {CHANNEL_NAMES[ch]}: {count} products", file=sys.stderr)

    print(f"  Amazon UK total: {len(all_products)} products", file=sys.stderr)
    return all_products
