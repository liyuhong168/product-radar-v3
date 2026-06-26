#!/usr/bin/env python3
"""
Product Radar V3 - Browser Fetcher using CloakBrowser
Drop-in replacement for curl-based fetching.
Passes all bot detection tests (30/30).
"""
import sys, time, os
from pathlib import Path

# CloakBrowser instance (singleton)
_browser = None
_page = None

def get_browser(headless=True):
    """Get or create a CloakBrowser instance."""
    global _browser
    if _browser is None:
        try:
            from cloakbrowser import launch
            _browser = launch(
                headless=headless,
                humanize=True,
                args=["--disable-gpu", "--no-sandbox"]
            )
            print("  [CloakBrowser] Initialized (stealth mode)", file=sys.stderr)
        except ImportError:
            print("  [CloakBrowser] Not installed! Run: pip install cloakbrowser", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  [CloakBrowser] Init error: {e}", file=sys.stderr)
            return None
    return _browser


def get_page():
    """Get or create a page."""
    global _page
    browser = get_browser()
    if browser is None:
        return None
    if _page is None:
        _page = browser.new_page()
    return _page


def fetch_url(url, wait_for=None, timeout=30000):
    """
    Fetch a URL using CloakBrowser.
    Creates a new page per request (thread-safe).
    Returns HTML content as string, or None on failure.
    """
    browser = get_browser()
    if browser is None:
        return None

    page = None
    try:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        if wait_for:
            try:
                page.wait_for_selector(wait_for, timeout=10000)
            except Exception:
                pass

        time.sleep(1)
        html = page.content()

        if len(html) < 5000:
            return None

        lower = html.lower()
        if "captcha" in lower and "enter the characters" in lower:
            return None

        return html

    except Exception as e:
        print(f"  [CloakBrowser] Fetch error: {e}", file=sys.stderr)
        return None
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def fetch_amazon_category(url, category="unknown"):
    """
    Fetch an Amazon category page.
    Returns HTML content or None.
    """
    print(f"  [CloakBrowser] Fetching {category}...", file=sys.stderr, end="")
    html = fetch_url(url, wait_for="[data-asin]")

    if html and "data-asin" in html:
        # Count products
        import re
        asins = re.findall(r'data-asin="([A-Z0-9]{10})"', html)
        print(f" {len(asins)} products", file=sys.stderr)
        return html
    elif html:
        print(f" no ASINs found (len={len(html)})", file=sys.stderr)
        return html
    else:
        print(f" failed", file=sys.stderr)
        return None


def fetch_amazon_search(keyword):
    """
    Search Amazon UK for a keyword.
    Returns HTML content or None.
    """
    import urllib.parse
    encoded = urllib.parse.quote_plus(keyword)
    url = f"https://www.amazon.co.uk/s?k={encoded}&rh=p_36%3A559-1000"

    print(f"  [CloakBrowser] Searching: {keyword}...", file=sys.stderr, end="")
    html = fetch_url(url, wait_for="[data-asin]")

    if html and "data-asin" in html:
        import re
        asins = re.findall(r'data-asin="([A-Z0-9]{10})"', html)
        print(f" {len(asins)} results", file=sys.stderr)
        return html
    else:
        print(f" no results", file=sys.stderr)
        return None


def close():
    """Close the browser."""
    global _browser, _page
    if _page:
        try:
            _page.close()
        except Exception:
            pass
        _page = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    print("  [CloakBrowser] Closed", file=sys.stderr)


def is_available():
    """Check if CloakBrowser is installed and working."""
    try:
        from cloakbrowser import launch
        return True
    except ImportError:
        return False
