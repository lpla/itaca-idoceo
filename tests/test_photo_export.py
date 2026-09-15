from __future__ import annotations

import struct
import zlib

import pymupdf
from openpyxl import load_workbook

from itaca_idoceo.photo_export import export_photo_roster


def _png_rgb(width: int = 2, height: int = 2) -> bytes:
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
    return (
        signature
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _make_photo_roster(path):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    page.insert_image(
        pymupdf.Rect(25, 178, 102, 273),
        stream=_png_rgb(),
    )
    page.insert_text((25, 285), "GARCIA LOPEZ, ANA", fontsize=6)

    doc.save(path)
    doc.close()


def test_export_photo_roster_creates_xlsx_photo_and_guide(tmp_path):
    pdf_path = tmp_path / "grupo_materia.pdf"
    output_dir = tmp_path / "salida"
    _make_photo_roster(pdf_path)

    result = export_photo_roster(pdf_path, output_dir)

    assert result.students == 1
    assert result.photos == 1
    assert result.automatic_name_matches == 1
    assert result.manual_name_matches == 0

    workbook = load_workbook(result.xlsx_path)
    sheet = workbook.active
    assert [cell.value for cell in sheet[1]] == ["Apellidos", "Nombre"]
    assert [sheet["A2"].value, sheet["B2"].value] == ["GARCIA LOPEZ", "ANA"]

    photos = sorted(path.name for path in result.photos_dir.glob("*.png"))
    assert photos == ["GARCIA LOPEZ, ANA.png"]
    assert (result.photos_dir / photos[0]).stat().st_size > 0

    guide = result.guide_path.read_text(encoding="utf-8")
    assert "Importación masiva" in guide
    assert "Nombre como criterio" in guide
