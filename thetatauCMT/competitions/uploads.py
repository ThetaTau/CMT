"""Checks on the files chapters upload (NECCWI-6, S8; Gotchas 3).

A file must have an extension the item accepts, and its content must match that extension, so
a renamed program is refused. The content is checked from the file's own structure (its first
bytes, or the parts inside an Office zip) rather than with libmagic, whose answer for Office
files changes between versions: the same .pptx can come back as the presentation type,
``application/zip`` or ``application/octet-stream``.
"""

import os
import zipfile

from django.core.exceptions import ValidationError

from .models import SubmissionItem

MB = 1024 * 1024
FileType = SubmissionItem.FileType
EXTENSIONS = {
    FileType.PDF: (".pdf",),
    FileType.POWERPOINT: (".pptx", ".ppt"),
    FileType.WORD: (".docx", ".doc"),
    FileType.SPREADSHEET: (".xlsx", ".xls", ".csv"),
    FileType.IMAGE: (".jpg", ".jpeg", ".png"),
}
OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
# The folder holding the document inside each Office zip.
OOXML_FOLDERS = {".pptx": "ppt/", ".docx": "word/", ".xlsx": "xl/"}
OLD_OFFICE = {".ppt", ".doc", ".xls"}
BINARY_SIGNATURES = (b"MZ", b"PK\x03\x04", b"%PDF", OLE_SIGNATURE, b"\x7fELF", PNG_SIGNATURE, JPEG_SIGNATURE)
HEAD_BYTES = 8192


def allowed_extensions(file_types):
    """The extensions accepted for an item's file types, in a stable order."""
    extensions = []
    for file_type in file_types or ():
        extensions += [ext for ext in EXTENSIONS.get(file_type, ()) if ext not in extensions]
    return extensions


def accept_attribute(file_types):
    """For the upload box's ``accept`` attribute, so the browser offers the right files."""
    return ",".join(allowed_extensions(file_types))


def describe(file_types):
    """Such as ``PDF or PowerPoint (.pdf, .pptx, .ppt)``."""
    labels = [str(FileType(value).label) for value in file_types or () if value in FileType.values]
    if not labels:
        return "None"
    joined = labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} or {labels[-1]}"
    return f"{joined} ({', '.join(allowed_extensions(file_types))})"


def _head(upload):
    upload.seek(0)
    head = upload.read(HEAD_BYTES)
    upload.seek(0)
    return head


def _is_ooxml(upload, folder):
    upload.seek(0)
    try:
        with zipfile.ZipFile(upload) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError, ValueError):
        return False
    finally:
        upload.seek(0)
    return "[Content_Types].xml" in names and any(name.startswith(folder) for name in names)


def content_matches(upload, extension):
    """Whether the file's content is what its extension says."""
    head = _head(upload)
    if extension == ".pdf":
        return b"%PDF-" in head[:1024]
    if extension == ".png":
        return head.startswith(PNG_SIGNATURE)
    if extension in (".jpg", ".jpeg"):
        return head.startswith(JPEG_SIGNATURE)
    if extension in OLD_OFFICE:
        return head.startswith(OLE_SIGNATURE)
    if extension in OOXML_FOLDERS:
        return head.startswith(b"PK\x03\x04") and _is_ooxml(upload, OOXML_FOLDERS[extension])
    if extension == ".csv":
        return b"\x00" not in head and not head.startswith(BINARY_SIGNATURES)
    return False


def check_upload(upload, item):
    """Raise :class:`ValidationError` unless ``upload`` is a file ``item`` accepts."""
    name = os.path.basename(upload.name or "")
    extension = os.path.splitext(name)[1].lower()
    if extension not in allowed_extensions(item.file_types):
        kind = f"a {extension} file" if extension else "a file without an extension"
        raise ValidationError(f"{name or 'This file'} is {kind}. Upload {describe(item.file_types)}.", code="file_type")
    if not upload.size:
        raise ValidationError(f"{name} is empty.", code="empty")
    if upload.size > item.max_size_mb * MB:
        size = upload.size / MB
        raise ValidationError(
            f"{name} is {size:.1f} MB; the most is {item.max_size_mb} MB. For a video, upload it elsewhere "
            "and share a link instead.",
            code="too_large",
        )
    if not content_matches(upload, extension):
        raise ValidationError(
            f"{name} does not look like a real {extension} file. Open it and save it again as "
            f"{describe(item.file_types)}, then upload it.",
            code="content",
        )
