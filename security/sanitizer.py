"""
Input sanitization for .ics event generation.

Called by generate_calendar.py before adding each event.
Ensures no malicious content reaches the final .ics file.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_DOMAINS_FILE = Path(__file__).parent / "allowed_domains.json"
ALLOWED_DOMAINS: list[str] = json.loads(ALLOWED_DOMAINS_FILE.read_text())

MAX_SUMMARY_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 500
MAX_LOCATION_LENGTH = 200

FORBIDDEN_SCHEMES = ("javascript", "data", "file", "ftp", "vbscript")
FORBIDDEN_ICS_PROPERTIES = ("VALARM", "ATTACH", "ATTENDEE", "TZURL", "ORGANIZER")


def sanitize_text(text: str) -> str:
    """Remove CRLF injection attempts and control characters from text fields."""
    text = text.replace("\r\n", " ")
    text = text.replace("\r", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()


def validate_url(url: str) -> str | None:
    """Validate URL against allowlist. Returns cleaned URL or None if rejected."""
    if not url or not url.strip():
        return ""

    url = url.strip()

    for scheme in FORBIDDEN_SCHEMES:
        if url.lower().startswith(f"{scheme}:"):
            return None

    if not url.startswith("https://"):
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    domain = parsed.hostname
    if not domain:
        return None

    if not any(domain == allowed or domain.endswith(f".{allowed}") for allowed in ALLOWED_DOMAINS):
        return None

    return url


def sanitize_event(title: str, description: str, location: str, url_fields: list[str]) -> dict:
    """
    Sanitize all event fields before .ics generation.

    Returns dict with sanitized values and a list of rejected items.
    Raises ValueError if critical fields are compromised.
    """
    issues = []

    clean_title = sanitize_text(title)
    if len(clean_title) > MAX_SUMMARY_LENGTH:
        clean_title = clean_title[:MAX_SUMMARY_LENGTH]
        issues.append(f"Title truncated to {MAX_SUMMARY_LENGTH} chars")

    clean_description = sanitize_text(description)
    if len(clean_description) > MAX_DESCRIPTION_LENGTH:
        clean_description = clean_description[:MAX_DESCRIPTION_LENGTH]
        issues.append(f"Description truncated to {MAX_DESCRIPTION_LENGTH} chars")

    clean_location = sanitize_text(location)
    if len(clean_location) > MAX_LOCATION_LENGTH:
        clean_location = clean_location[:MAX_LOCATION_LENGTH]
        issues.append(f"Location truncated to {MAX_LOCATION_LENGTH} chars")

    clean_urls = []
    for url in url_fields:
        validated = validate_url(url)
        if validated is None:
            issues.append(f"URL rejected (not in allowlist or invalid scheme): {url}")
            clean_urls.append("")
        else:
            clean_urls.append(validated)

    for prop in FORBIDDEN_ICS_PROPERTIES:
        for field in (clean_title, clean_description, clean_location):
            if prop in field.upper():
                issues.append(f"Suspicious ICS property '{prop}' found in text field")
                raise ValueError(f"Security violation: '{prop}' detected in event field")

    return {
        "title": clean_title,
        "description": clean_description,
        "location": clean_location,
        "urls": clean_urls,
        "issues": issues,
    }
