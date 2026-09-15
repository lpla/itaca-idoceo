from __future__ import annotations

import base64

import pymupdf

from itaca_idoceo.photo_layout_debug import build_photo_layout_report


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z5QAAAABJRU5ErkJggg=="
)


def test_photo_layout_report_masks_names_and_lists_image_geometry(tmp_path):
    pdf_path = tmp_path / "private-roster.pdf"

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 40), "GRUP: 3ESO A")
    page.insert_image(pymupdf.Rect(40, 90, 120, 190), stream=PNG_1X1)
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
