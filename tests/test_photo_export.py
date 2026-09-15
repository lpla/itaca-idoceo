from __future__ import annotations

import struct
import zlib

import pymupdf
from openpyxl import load_workbook

import itaca_idoceo.photo_export as photo_export
from itaca_idoceo.photo_roster import (
    PhotoRosterPageSummary,
    PhotoRosterResult,
    PhotoRosterStudent,
)


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


def _make_source_pdf(path) -> int:
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    xref = page.insert_image(
        pymupdf.Rect(25, 178, 102, 273),
        stream=_png_rgb(),
    )
    document.save(path)
    document.close()
    return xref


def _roster_result(pdf_path, xref: int) -> PhotoRosterResult:
    return PhotoRosterResult(
        source=pdf_path,
        page_count=1,
        students=[
            PhotoRosterStudent(
                page=1,
                ordinal=1,
                row=1,
                column=1,
                full_name="GARCIA LOPEZ, ANA",
                surnames="GARCIA LOPEZ",
                given_names="ANA",
                xref=xref,
                image_x0=25,
                image_y0=178,
                image_x1=102,
                image_y1=273,
                name_lines=1,
            ),
            PhotoRosterStudent(
                page=1,
                ordinal=2,
                row=1,
                column=2,
                full_name="PEREZ, BEA",
                surnames="PEREZ",
                given_names="BEA",
                xref=0,
                image_x0=119,
                image_y0=178,
                image_x1=196,
                image_y1=273,
                name_lines=1,
            ),
        ],
        pages=[PhotoRosterPageSummary(1, 1, 2, 1, 2, 0, 1)],
        issues=[],
        group_raw="3ESO A - 3ESO A",
        group_code="3ESO A",
        tutor="Doe, Jane",
    )


def test_export_photo_roster_keeps_student_without_available_photo(tmp_path, monkeypatch):
    pdf_path = tmp_path / "grupo_materia.pdf"
    output_dir = tmp_path / "salida"
    xref = _make_source_pdf(pdf_path)
    roster = _roster_result(pdf_path, xref)
    monkeypatch.setattr(photo_export, "detect_photo_roster", lambda _: roster)

    result = photo_export.export_photo_roster(pdf_path, output_dir)

    assert result.students == 2
    assert result.photos == 1
    assert result.missing_photos == 1
    assert result.automatic_name_matches == 1
    assert result.manual_name_matches == 0

    workbook = load_workbook(result.xlsx_path)
    sheet = workbook.active
    assert [cell.value for cell in sheet[1]] == ["Apellidos", "Nombre"]
    assert [sheet["A2"].value, sheet["B2"].value] == ["GARCIA LOPEZ", "ANA"]
    assert [sheet["A3"].value, sheet["B3"].value] == ["PEREZ", "BEA"]

    photos = sorted(path.name for path in result.photos_dir.glob("*.png"))
    assert photos == ["GARCIA LOPEZ, ANA.png"]
    assert (result.photos_dir / photos[0]).stat().st_size > 0

    guide = result.guide_path.read_text(encoding="utf-8")
    assert "Importación masiva" in guide
    assert "Nombre como criterio" in guide
    assert "sin fotografía disponible en el PDF: 1" in guide
