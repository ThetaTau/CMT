"""
Extract the text/html part from the newest email dump under email_tests/
and write it as a properly decoded HTML file you can open in a browser.

Run inside the app container:
    python manage.py runscript extract_email_preview

Writes /app/email_tests/_preview.html and prints the path.
"""

import email
import pathlib


def run():
    root = pathlib.Path("email_tests")
    logs = sorted(root.glob("*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        print("No .log files in email_tests/")
        return

    latest = logs[-1]
    msg = email.message_from_bytes(latest.read_bytes())

    html = None
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            break

    if html is None:
        print(f"No text/html part in {latest.name}")
        return

    out = root / "_preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({len(html)} chars) from {latest.name}")
