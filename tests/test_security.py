"""Security tests — validates sanitization, URL allowlist, and .ics output safety."""

import json
from pathlib import Path

import pytest

from security.sanitizer import (
    sanitize_text,
    validate_url,
    sanitize_event,
    ALLOWED_DOMAINS,
    MAX_SUMMARY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
)
from security.validator import validate_ics


ICS_FILE = Path(__file__).parent.parent / "docs" / "fifa-worldcup-2026.ics"


class TestSanitizeText:
    def test_removes_crlf(self):
        assert "\r\n" not in sanitize_text("Hello\r\nWorld")
        assert "\r" not in sanitize_text("Hello\rWorld")

    def test_removes_control_chars(self):
        result = sanitize_text("Hello\x00\x01\x02World")
        assert "\x00" not in result
        assert "HelloWorld" in result

    def test_preserves_normal_text(self):
        text = "🇧🇷 BRASIL vs Marrocos 🇲🇦 — Grupo C"
        assert sanitize_text(text) == text

    def test_preserves_newlines_in_descriptions(self):
        text = "Line 1\nLine 2"
        assert sanitize_text(text) == "Line 1\nLine 2"

    def test_strips_whitespace(self):
        assert sanitize_text("  hello  ") == "hello"


class TestValidateUrl:
    def test_valid_youtube_url(self):
        url = "https://www.youtube.com/@CasimiroMiguel"
        assert validate_url(url) == url

    def test_valid_globo_url(self):
        url = "https://globoplay.globo.com/live"
        assert validate_url(url) == url

    def test_empty_string_returns_empty(self):
        assert validate_url("") == ""
        assert validate_url("  ") == ""

    def test_rejects_javascript_scheme(self):
        assert validate_url("javascript:alert(1)") is None

    def test_rejects_data_scheme(self):
        assert validate_url("data:text/html,<script>") is None

    def test_rejects_file_scheme(self):
        assert validate_url("file:///etc/passwd") is None

    def test_rejects_http_non_secure(self):
        assert validate_url("http://youtube.com/watch") is None

    def test_rejects_unknown_domain(self):
        assert validate_url("https://malicious-site.com/payload") is None
        assert validate_url("https://evil.com/calendar.ics") is None

    def test_rejects_lookalike_domains(self):
        assert validate_url("https://youtube.com.evil.com/watch") is None
        assert validate_url("https://fakeyoutube.com/watch") is None

    def test_accepts_subdomain_of_allowed(self):
        assert validate_url("https://www.youtube.com/watch") is not None
        assert validate_url("https://m.youtube.com/watch") is not None


class TestSanitizeEvent:
    def test_clean_event_passes(self):
        result = sanitize_event(
            title="🇧🇷 BRASIL vs Marrocos 🇲🇦 — Grupo C",
            description="FIFA World Cup 2026\nJogo #7\n🕐 18:00 (ET)",
            location="MetLife Stadium, East Rutherford, EUA",
            url_fields=["https://www.youtube.com/@CasimiroMiguel"]
        )
        assert result["issues"] == []
        assert "BRASIL" in result["title"]

    def test_truncates_long_title(self):
        long_title = "A" * 300
        result = sanitize_event(long_title, "desc", "loc", [])
        assert len(result["title"]) == MAX_SUMMARY_LENGTH
        assert any("truncated" in i for i in result["issues"])

    def test_truncates_long_description(self):
        long_desc = "B" * 600
        result = sanitize_event("title", long_desc, "loc", [])
        assert len(result["description"]) == MAX_DESCRIPTION_LENGTH

    def test_rejects_malicious_url(self):
        result = sanitize_event(
            title="Match",
            description="Desc",
            location="Loc",
            url_fields=["https://malicious.com/steal-cookies"]
        )
        assert result["urls"] == [""]
        assert any("rejected" in i for i in result["issues"])

    def test_raises_on_ics_property_injection(self):
        with pytest.raises(ValueError, match="Security violation"):
            sanitize_event(
                title="Normal\nVALARM:something",
                description="desc",
                location="loc",
                url_fields=[]
            )

    def test_raises_on_attach_injection(self):
        with pytest.raises(ValueError, match="Security violation"):
            sanitize_event(
                title="title",
                description="See ATTACH:https://evil.com/malware.exe",
                location="loc",
                url_fields=[]
            )

    def test_crlf_with_property_injection_is_blocked(self):
        """CRLF injection attempting to inject ATTENDEE property is fully blocked."""
        with pytest.raises(ValueError, match="Security violation"):
            sanitize_event(
                title="Match\r\nATTENDEE:mailto:victim@email.com",
                description="Normal",
                location="Normal",
                url_fields=[]
            )

    def test_crlf_without_property_is_stripped(self):
        """CRLF without forbidden properties is cleaned (not blocked)."""
        result = sanitize_event(
            title="Match\r\nsome extra text",
            description="Normal",
            location="Normal",
            url_fields=[]
        )
        assert "\r\n" not in result["title"]
        assert "Match some extra text" == result["title"]

    def test_multiple_urls_validated_independently(self):
        result = sanitize_event(
            title="Match", description="Desc", location="Loc",
            url_fields=[
                "https://www.youtube.com/watch",
                "https://evil.com/phish",
                "https://globoplay.globo.com/live",
            ]
        )
        assert result["urls"][0] == "https://www.youtube.com/watch"
        assert result["urls"][1] == ""
        assert result["urls"][2] == "https://globoplay.globo.com/live"


class TestValidatorOnGeneratedIcs:
    """Run the full validator against the actual generated .ics file."""

    def test_generated_ics_passes_security_validation(self):
        assert ICS_FILE.exists(), f".ics file not found at {ICS_FILE}"
        errors = validate_ics(ICS_FILE)
        assert not errors, f"Security issues found:\n" + "\n".join(str(e) for e in errors)

    def test_no_valarm_in_ics(self):
        content = ICS_FILE.read_text()
        assert "VALARM" not in content
        assert "BEGIN:VALARM" not in content

    def test_no_attach_in_ics(self):
        content = ICS_FILE.read_text()
        assert "ATTACH:" not in content
        assert "ATTACH;" not in content

    def test_no_attendee_in_ics(self):
        content = ICS_FILE.read_text()
        assert "ATTENDEE:" not in content
        assert "ATTENDEE;" not in content

    def test_no_tzurl_in_ics(self):
        content = ICS_FILE.read_text()
        assert "TZURL:" not in content

    def test_no_organizer_in_ics(self):
        content = ICS_FILE.read_text()
        assert "ORGANIZER:" not in content

    def test_all_urls_are_https(self):
        content = ICS_FILE.read_text()
        import re
        urls = re.findall(r"http://[^\s\\]+", content)
        assert not urls, f"Non-HTTPS URLs found: {urls}"


class TestAllowedDomains:
    def test_allowlist_file_is_valid_json(self):
        path = Path(__file__).parent.parent / "security" / "allowed_domains.json"
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_youtube_is_allowed(self):
        assert "youtube.com" in ALLOWED_DOMAINS

    def test_no_wildcard_domains(self):
        for domain in ALLOWED_DOMAINS:
            assert "*" not in domain
            assert domain.startswith(".") is False


class TestMatchesJsonSecurity:
    """Scan matches.json for potential injection vectors."""

    def test_no_urls_outside_expected_fields(self):
        path = Path(__file__).parent.parent / "matches.json"
        matches = json.loads(path.read_text())
        url_fields = ("tv", "streaming")
        for m in matches:
            for key, value in m.items():
                if key in url_fields:
                    continue
                if isinstance(value, str) and "http" in value.lower():
                    pytest.fail(f"Match #{m['match_number']}: URL found in '{key}' field: {value}")

    def test_no_script_tags_in_any_field(self):
        path = Path(__file__).parent.parent / "matches.json"
        content = path.read_text()
        assert "<script" not in content.lower()
        assert "javascript:" not in content.lower()

    def test_no_crlf_in_any_field(self):
        path = Path(__file__).parent.parent / "matches.json"
        content = path.read_text()
        assert "\r\n" not in content
