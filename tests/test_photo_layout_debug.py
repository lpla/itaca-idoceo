from __future__ import annotations

import struct
import zlib

import pymupdf

from itaca_idoceo.photo_layout_debug import build_photo_layout_report


def _png_rgb(width: int = 2, height: int = 2) -> bytes:
    """PNG RGB mínimo generado sólo con la biblioteca estándar."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\xff\xff\xff" * width)
    pixels = row * height
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def test_photo_layout_report_masks_names_and_lists_image_geometry(tmp_path):
    pdf_path = tmp_path / "private-roster.pdf"

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 40), "GRUP: 3ESO A")
    page.insert_image(pymupdf.Rect(40, 90, 120, 190), stream=_png_rgb())
    page.insert_text((40, 215), "GARCÍA LÓPEZ, ANA")
    doc.save(pdf_path)
    doc.close()

    report = build_photo_layout_report(pdf_path)

    assert "private-roster" not in report
    assert "GARCÍA" not in report
    assert "LÓPEZ" not in report
    assert "ANA" not in report
    assert "GRUP" in report
    assert "IMAGE 1" in report
    assert "images=1" in report
    assert "name_like=yes" in report
