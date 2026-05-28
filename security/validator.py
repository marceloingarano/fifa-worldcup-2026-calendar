#!/usr/bin/env python3
"""
Post-generation validator for the .ics file.

Scans the generated calendar for security issues. Run after generate_calendar.py
to verify the output is safe before publishing.

Usage:
    python -m security.validator                    # Validate docs/fifa-worldcup-2026.ics
    python -m security.validator path/to/file.ics   # Validate specific file
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_DOMAINS_FILE = Path(__file__).parent / "allowed_domains.json"
ALLOWED_DOMAINS: list[str] = json.loads(ALLOWED_DOMAINS_FILE.read_text())

DEFAULT_ICS = Path(__file__).parent.parent / "docs" / "fifa-worldcup-2026.ics"

FORBIDDEN_PROPERTIES = [
    "VALARM",
    "ATTACH",
    "ATTENDEE",
    "TZURL",
    "ORGANIZER",
    "FREEBUSY",
    "REQUEST-STATUS",
]

FORBIDDEN_SCHEMES = ["javascript:", "data:", "file:", "ftp:", "vbscript:"]


class ValidationError:
    def __init__(self, line_num: int, category: str, message: str):
        self.line_num = line_num
        self.category = category
        self.message = message

    def __str__(self):
        return f"  L{self.line_num} [{self.category}] {self.message}"


def validate_ics(filepath: Path) -> list[ValidationError]:
    """Validate a .ics file for security issues. Returns list of errors."""
    errors = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        line_upper = line.upper().strip()

        # Check forbidden properties
        for prop in FORBIDDEN_PROPERTIES:
            if line_upper.startswith(f"{prop}:") or line_upper.startswith(f"{prop};"):
                errors.append(ValidationError(i, "FORBIDDEN_PROPERTY",
                              f"Forbidden ICS property: {prop}"))

        # Check for URL fields
        if "http" in line.lower():
            urls = re.findall(r"https?://[^\s\\,\"']+", line)
            for url in urls:
                url_clean = url.rstrip("\\")
                # Check scheme
                for scheme in FORBIDDEN_SCHEMES:
                    if scheme in url_clean.lower():
                        errors.append(ValidationError(i, "FORBIDDEN_SCHEME",
                                      f"Forbidden URL scheme: {url_clean}"))
                # Check domain allowlist
                try:
                    parsed = urlparse(url_clean)
                    domain = parsed.hostname
                    if domain and not any(domain == a or domain.endswith(f".{a}")
                                         for a in ALLOWED_DOMAINS):
                        # github.com is allowed for UIDs and prodid
                        if domain not in ("github.com",):
                            errors.append(ValidationError(i, "DOMAIN_NOT_ALLOWED",
                                          f"Domain not in allowlist: {domain} ({url_clean})"))
                except Exception:
                    errors.append(ValidationError(i, "INVALID_URL",
                                  f"Could not parse URL: {url_clean}"))

        # Check CRLF injection (bare \r not followed by \n in iCalendar context)
        if "\r" in line and "\r\n" not in line + "\n":
            errors.append(ValidationError(i, "CRLF_INJECTION",
                          "Suspicious bare CR character detected"))

        # Check field length (unfolded)
        if line_upper.startswith("SUMMARY:"):
            value = line.split(":", 1)[1] if ":" in line else ""
            if len(value) > 200:
                errors.append(ValidationError(i, "FIELD_TOO_LONG",
                              f"SUMMARY exceeds 200 chars ({len(value)})"))

        if line_upper.startswith("DESCRIPTION:"):
            value = line.split(":", 1)[1] if ":" in line else ""
            if len(value) > 500:
                errors.append(ValidationError(i, "FIELD_TOO_LONG",
                              f"DESCRIPTION exceeds 500 chars ({len(value)})"))

    # Global checks
    if "BEGIN:VALARM" in content:
        errors.append(ValidationError(0, "FORBIDDEN_COMPONENT", "VALARM component detected"))
    if "BEGIN:VTODO" in content:
        errors.append(ValidationError(0, "FORBIDDEN_COMPONENT", "VTODO component detected"))

    return errors


def main():
    filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ICS

    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    print(f"Validating: {filepath}")
    errors = validate_ics(filepath)

    if errors:
        print(f"\nFAILED — {len(errors)} security issue(s) found:\n")
        for error in errors:
            print(error)
        sys.exit(1)
    else:
        print("PASSED — No security issues found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
