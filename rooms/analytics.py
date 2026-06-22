"""
Lightweight, dependency-free helpers for visit tracking: client IP
extraction (Render-proxy aware) and basic user-agent parsing.
"""


def get_client_ip(request) -> str | None:
    """
    Render (and most reverse proxies) forward the real client IP in
    X-Forwarded-For as the first entry in a comma-separated list.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def parse_user_agent(ua: str) -> dict:
    """Best-effort browser/OS/device detection from a User-Agent string."""
    if not ua:
        return {"browser": "Unknown", "os": "Unknown", "device": "Desktop"}

    ua_lower = ua.lower()

    if "edg/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower:
        browser = "Safari"
    else:
        browser = "Unknown"

    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        os_name = "macOS"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ios " in ua_lower:
        os_name = "iOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    else:
        os_name = "Unknown"

    is_mobile = any(token in ua_lower for token in ("mobile", "android", "iphone"))
    device = "Mobile" if is_mobile else "Desktop"

    return {"browser": browser, "os": os_name, "device": device}
