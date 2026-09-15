from __future__ import annotations

import struct
import zlib

import pymupdf
from openpyxl import load_workbook

from itaca_idoceo.photo_export import export_photo_roster
from itaca_idoceo.photo_roster import detect_photo_roster


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

    page.insert_text((25, 150), "GRUPO: 3ESO A - 3ESO A", fontsize=6)
    page.insert_text((285, 150), "TUTOR: Doe, Jane", fontsize=6)

    page.insert_image(
        pymupdf.Rect(25, 178, 102, 273),
        stream=_png_rgb(),
    )
    missing_rect = pymupdf.Rect(119, 178, 196, 273)
    page.draw_rect(missing_rect)
    page.insert_textbox(
        pymupdf.Rect(122, 210, 193, 245),
        "Fotografia no\ndisponible",
        fontsize=6,
        align=1,
    )
    page.insert_image(
        pymupdf.Rect(213, 178, 290, 273),
        stream=_png_rgb(),
    )

    page.insert_text((25, 285), "GARCIA LOPEZ, ANA", fontsize=6)
    page.insert_text((119, 285), "PEREZ, BEA", fontsize=6)
    page.insert_text((213, 285), "RUIZ, CARLA", fontsize=6)

    doc.save(path)
    doc.close()


def test_detect_photo_roster_keeps_student_without_photo_and_header_metadata(tmp_path):
    pdf_path = tmp_path / "grupo_materia.pdf"
    _make_photo_roster(pdf_path)

    result = detect_photo_roster(pdf_path)

    assert result.is_valid
    assert len(result.students) == 3
    assert sum(student.has_photo for student in result.students) == 2
    assert result.pages[0].candidate_photos == 2
    assert result.pages[0].missing_photos == 1
    assert result.pages[0].paired_students == 3
    assert result.group_code == "3ESO A"
    assert result.tutor == "Doe, Jane"


def test_export_photo_roster_creates_xlsx_only_for_available_photos(tmp_path):
    pdf_path = tmp_path / "grupo_materia.pdf"
    output_dir = tmp_path / "salida"
    _make_photo_roster(pdf_path)

    result = export_photo_roster(pdf_path, output_dir)

    assert result.students == 3
    assert result.photos == 2
    assert result.missing_photos == 1
    assert result.automatic_name_matches == 2
    assert result.manual_name_matches == 0

    workbook = load_workbook(result.xlsx_path)
    sheet = workbook.active
    assert [cell.value for cell in sheet[1]] == ["Apellidos", "Nombre"]
    assert [sheet["A2"].value, sheet["B2"].value] == ["GARCIA LOPEZ", "ANA"]
    assert [sheet["A3"].value, sheet["B3"].value] == ["PEREZ", "BEA"]
    assert [sheet["A4"].value, sheet["B4"].value] == ["RUIZ", "CARLA"]

    photos = sorted(path.name for path in result.photos_dir.glob("*.png"))
    assert photos == ["GARCIA LOPEZ, ANA.png", "RUIZ, CARLA.png"]
    assert all((result.photos_dir / name).stat().st_size > 0 for name in photos)

    guide = result.guide_path.read_text(encoding="utf-8")
    assert "Importación masiva" in guide
    assert "Nombre como criterio" in guide
    assert "sin fotografía disponible en el PDF: 1" in guide
