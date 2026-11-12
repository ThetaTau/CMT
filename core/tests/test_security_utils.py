"""Unit tests for the security helpers added in the production-readiness pass.

Covered:
- ``core.sanitize.sanitize_html`` — stored-XSS mitigation for CKEditor rich text.
- ``core.csv_utils.escape_csv_value`` / ``escape_csv_row`` — CSV formula-injection
  hardening for data exports.

These are pure functions, so no database is required.
"""

from core.csv_utils import escape_csv_row, escape_csv_value
from core.sanitize import link_images, sanitize_html


class TestSanitizeHtml:
    def test_strips_script_tag(self):
        assert "<script>" not in sanitize_html("<p>hi</p><script>alert(1)</script>")
        assert "alert(1)" not in sanitize_html("<p>hi</p><script>alert(1)</script>")

    def test_strips_event_handler_attribute(self):
        cleaned = sanitize_html('<p onclick="alert(1)">x</p>')
        assert "onclick" not in cleaned
        assert "alert(1)" not in cleaned

    def test_strips_onerror_image_payload(self):
        cleaned = sanitize_html('<img src=x onerror="alert(1)">')
        assert "onerror" not in cleaned

    def test_strips_javascript_url(self):
        cleaned = sanitize_html('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in cleaned

    def test_strips_style_attribute(self):
        cleaned = sanitize_html('<p style="position:fixed">x</p>')
        assert "style" not in cleaned

    def test_preserves_allowed_formatting(self):
        cleaned = sanitize_html("<p><strong>bold</strong> and <em>italic</em></p>")
        assert "<strong>bold</strong>" in cleaned
        assert "<em>italic</em>" in cleaned

    def test_link_gets_rel_noopener(self):
        cleaned = sanitize_html('<a href="https://example.com">x</a>')
        assert 'href="https://example.com"' in cleaned
        assert "noopener" in cleaned

    def test_plain_text_unchanged(self):
        assert sanitize_html("just some text") == "just some text"

    def test_empty_and_none(self):
        assert sanitize_html("") == ""
        assert sanitize_html(None) is None


class TestLinkImages:
    def test_wraps_an_image_in_a_link_to_its_full_size_file(self):
        assert link_images('<p><img src="/media/team.png" alt="Team"></p>') == (
            '<p><a href="/media/team.png" target="_blank" rel="noopener noreferrer">'
            '<img src="/media/team.png" alt="Team"></a></p>'
        )

    def test_leaves_an_image_that_is_already_a_link(self):
        html = '<a href="https://example.com" rel="noopener noreferrer nofollow"><img src="/media/team.png"></a>'
        assert link_images(html) == html

    def test_escapes_the_link_address(self):
        linked = link_images('<img src="/media/team.png?a=1&amp;b=&quot;2&quot;">')
        assert linked.startswith('<a href="/media/team.png?a=1&amp;b=&quot;2&quot;" ')

    def test_keeps_text_entities_and_other_tags_unchanged(self):
        html = '<h2>Tom &amp; Jerry</h2><p>&#169; 2026 <strong>bold</strong><br>next</p><img alt="no source">'
        assert link_images(html) == html

    def test_links_sanitized_ckeditor_output(self):
        cleaned = sanitize_html('<figure class="image" style="width:40%"><img src="https://x.test/a.png"></figure>')
        assert link_images(cleaned) == (
            '<figure class="image"><a href="https://x.test/a.png" target="_blank" rel="noopener noreferrer">'
            '<img src="https://x.test/a.png"></a></figure>'
        )

    def test_empty_and_none(self):
        assert link_images("") == ""
        assert link_images(None) is None


class TestEscapeCsvValue:
    def test_escapes_formula_prefixes(self):
        for payload in ("=1+1", "+1+1", "@SUM(A1)", "\t=cmd", "\r=cmd", "-1+1"):
            assert escape_csv_value(payload).startswith("'"), payload

    def test_escapes_classic_injection_payload(self):
        assert escape_csv_value("=cmd|'/c calc'!A1").startswith("'")

    def test_preserves_negative_and_positive_numbers(self):
        assert escape_csv_value("-5") == "-5"
        assert escape_csv_value("+3.14") == "+3.14"
        assert escape_csv_value("-0.5") == "-0.5"

    def test_normal_text_unchanged(self):
        assert escape_csv_value("Regent") == "Regent"
        assert escape_csv_value("a@b.com") == "a@b.com"  # '@' not leading

    def test_none_becomes_empty(self):
        assert escape_csv_value(None) == ""

    def test_non_string_coerced(self):
        assert escape_csv_value(42) == "42"

    def test_escape_row_maps_cells(self):
        assert escape_csv_row(["=bad", "ok", "-5"]) == ["'=bad", "ok", "-5"]
