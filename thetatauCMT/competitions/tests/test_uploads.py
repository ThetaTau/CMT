"""NECCWI-6: the checks on uploaded files (S8; Gotchas 3)."""

import io
import zipfile

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from .. import uploads
from ..models import SubmissionItem

OLE = bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 600


def office_zip(folder, extra=()):
    """An Office file as PowerPoint, Word, Excel and Google Slides write them: a zip of XML parts."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("docProps/app.xml", "<Properties/>")
        for name in (f"{folder}presentation.xml", f"{folder}slides/slide1.xml", *extra):
            archive.writestr(name, "<x/>")
    return buffer.getvalue()


def upload(name, content):
    return SimpleUploadedFile(name, content)


@pytest.fixture
def item():
    return SubmissionItem(label="Proposal", file_types=["pdf", "powerpoint"], max_size_mb=1)


@pytest.mark.parametrize(
    "name, content",
    [
        ("deck.pdf", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj"),  # PowerPoint's Save as PDF
        ("deck.pdf", b"%PDF-1.4\n1 0 obj"),  # Google Slides' Download as PDF
        ("deck.PDF", b"\xef\xbb\xbf\r\n%PDF-1.5\n"),  # a few bytes before the header
        ("deck.pptx", office_zip("ppt/")),
        ("Our Deck (final).pptx", office_zip("ppt/", ["ppt/media/image1.png"])),
        ("deck.ppt", OLE),
    ],
    ids=["powerpoint-pdf", "google-slides-pdf", "pdf-with-preamble", "pptx", "pptx-with-media", "ppt"],
)
def test_real_files_are_accepted(item, name, content):
    uploads.check_upload(upload(name, content), item)


@pytest.mark.parametrize(
    "name, content, code",
    [
        ("deck.pdf", b"MZ\x90\x00" + b"\x00" * 100, "content"),  # a renamed program
        ("deck.pptx", b"MZ\x90\x00" + b"\x00" * 100, "content"),
        ("deck.pptx", office_zip("word/"), "content"),  # a Word file renamed
        ("deck.pptx", b"PK\x03\x04 not really a zip", "content"),
        ("deck.ppt", b"%PDF-1.4", "content"),
        ("deck.docx", office_zip("word/"), "file_type"),  # Word is not accepted here
        ("deck", b"%PDF-1.4", "file_type"),
        ("deck.exe", b"MZ", "file_type"),
        ("deck.pdf", b"", "empty"),
    ],
    ids=[
        "program-as-pdf",
        "program-as-pptx",
        "word-as-pptx",
        "broken-zip",
        "pdf-as-ppt",
        "word-not-accepted",
        "no-extension",
        "exe",
        "empty",
    ],
)
def test_wrong_files_are_refused(item, name, content, code):
    with pytest.raises(ValidationError) as caught:
        uploads.check_upload(upload(name, content), item)
    assert caught.value.code == code


def test_files_over_the_limit_are_refused(item):
    with pytest.raises(ValidationError) as caught:
        uploads.check_upload(upload("deck.pdf", b"%PDF-1.4" + b"0" * uploads.MB), item)
    assert caught.value.code == "too_large"
    assert "the most is 1 MB" in caught.value.message


def test_other_kinds_of_file():
    item = SubmissionItem(label="Budget", file_types=["spreadsheet", "image", "word"], max_size_mb=5)
    for name, content in [
        ("budget.csv", b"item,amount\nSolar panel,120.00\n"),
        ("budget.xlsx", office_zip("xl/")),
        ("budget.xls", OLE),
        ("photo.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF"),
        ("photo.png", b"\x89PNG\r\n\x1a\n\x00\x00"),
        ("report.docx", office_zip("word/")),
    ]:
        uploads.check_upload(upload(name, content), item)
    with pytest.raises(ValidationError):
        uploads.check_upload(upload("budget.csv", b"MZ\x00\x00binary"), item)


def test_descriptions_for_the_form():
    assert uploads.describe(["pdf", "powerpoint"]) == "PDF or PowerPoint (.pdf, .pptx, .ppt)"
    assert uploads.accept_attribute(["pdf", "powerpoint"]) == ".pdf,.pptx,.ppt"
    assert uploads.describe([]) == "None"


def test_the_file_is_left_ready_to_save(item):
    content = office_zip("ppt/")
    uploaded = upload("deck.pptx", content)
    uploads.check_upload(uploaded, item)
    assert uploaded.read() == content
