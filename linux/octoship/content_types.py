"""Bounded file-signature checks for safe, useful upload previews."""

from pathlib import Path


_SIGNATURES = (
    ("PNG", b"\x89PNG\r\n\x1a\n"),
    ("JPEG", b"\xff\xd8\xff"),
    ("GIF", (b"GIF87a", b"GIF89a")),
    ("Bitmap", b"BM"),
    ("TIFF", (b"II*\x00", b"MM\x00*")),
    ("PDF", b"%PDF-"),
)

_EXTENSIONS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".gif": "GIF",
    ".bmp": "Bitmap",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".pdf": "PDF",
}


def detect_content_kind(prefix: bytes) -> str:
    for name, signature in _SIGNATURES:
        alternatives = signature if isinstance(signature, tuple) else (signature,)
        if any(prefix.startswith(value) for value in alternatives):
            return name
    return "Text" if b"\0" not in prefix else "Unknown binary"


def extension_mismatch(filename: str, kind: str) -> str | None:
    claimed = _EXTENSIONS.get(Path(filename).suffix.casefold())
    if claimed and claimed != kind:
        return f"Filename extension suggests {claimed}, but file content looks like {kind}."
    return None


def is_known_binary(kind: str) -> bool:
    return kind in {"PNG", "JPEG", "GIF", "Bitmap", "TIFF", "PDF", "Unknown binary"}
