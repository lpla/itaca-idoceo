from pathlib import Path

import pymupdf

from itaca_idoceo.photo_roster import (
    MissingPhotoBlock,
    NameBlock,
    PhotoCandidate,
    PhotoRosterPageSummary,
    PhotoRosterResult,
    PhotoRosterStudent,
    _add_missing_photo_slots,
    _cluster_rows,
    _extract_group_metadata,
    _extract_missing_photo_blocks,
    _is_missing_photo_text,
    _pair_row,
    _parse_name_text,
    print_photo_roster_check,
)


def _photo(x0: float, y0: float, xref: int) -> PhotoCandidate:
    return PhotoCandidate(
        page=1,
        xref=xref,
        x0=x0,
        y0=y0,
        x1=x0 + 77,
        y1=y0 + 95,
        width_px=325,
        height_px=400,
    )


def test_parse_name_text_accepts_wrapped_name_content():
    assert _parse_name_text("García Pérez, Ana María") == (
        "García Pérez, Ana María",
        "García Pérez",
        "Ana María",
    )


def test_cluster_rows_tolerates_one_photo_with_different_vertical_geometry():
    photos = [
        *[_photo(25 + 94 * i, 301, i + 1) for i in range(6)],
        *[_photo(25 + 94 * i, 424 if i != 4 else 421, i + 7) for i in range(6)],
        *[_photo(25 + 94 * i, 547, i + 13) for i in range(3)],
    ]
    rows = _cluster_rows(photos)
    assert [len(row) for row in rows] == [6, 6, 3]


def test_pair_row_uses_name_block_directly_below_same_column():
    row = [_photo(25, 178, 1), _photo(119, 178, 2)]
    names = [
        NameBlock(10, 25, 280, 108, 286, "Uno, Ana", "Uno", "Ana", 1),
        NameBlock(11, 119, 280, 190, 293, "Dos, Bea", "Dos", "Bea", 2),
        NameBlock(3, 330, 144, 490, 153, "Tutor, Persona", "Tutor", "Persona", 1),
    ]
    pairs = _pair_row(row, names, next_row_y=301, used_blocks=set())
    assert [pair[1].full_name for pair in pairs if pair[1]] == ["Uno, Ana", "Dos, Bea"]


def test_missing_photo_text_is_accent_and_whitespace_insensitive():
    assert _is_missing_photo_text("Fotografía no\ndisponible")
    assert _is_missing_photo_text("FOTOGRAFIA   NO DISPONIBLE")


def test_extract_missing_photo_block_from_multiline_pdf_text():
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_textbox(
        pymupdf.Rect(122, 210, 193, 245),
        "Fotografia no\ndisponible",
        fontsize=6,
        align=1,
    )

    blocks = _extract_missing_photo_blocks(page)
    document.close()

    assert len(blocks) == 1


def test_missing_photo_block_becomes_slot_in_existing_grid_row():
    photos = [_photo(25, 178, 1), _photo(213, 178, 2)]
    missing = [MissingPhotoBlock(130, 215, 185, 240)]

    slots = _add_missing_photo_slots(photos, missing, page_number=1)
    row = _cluster_rows(slots)[0]

    assert len(row) == 3
    assert [slot.xref for slot in row] == [1, 0, 2]
    assert row[1].missing_photo is True


def test_photo_header_reuses_group_and_tutor_geometry():
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((25, 150), "GRUPO: 3ESO A - 3ESO A", fontsize=6)
    page.insert_text((285, 150), "TUTOR: Doe, Jane", fontsize=6)

    group_raw, group_code, tutor = _extract_group_metadata(page)
    document.close()

    assert group_raw == "3ESO A - 3ESO A"
    assert group_code == "3ESO A"
    assert tutor == "Doe, Jane"


def test_check_output_never_prints_student_names_or_source_path(capsys):
    secret = "Apellido Privado, Nombre Privado"
    result = PhotoRosterResult(
        source=Path("/home/usuario/centro/listado-real.pdf"),
        page_count=1,
        students=[
            PhotoRosterStudent(
                page=1,
                ordinal=1,
                row=1,
                column=1,
                full_name=secret,
                surnames="Apellido Privado",
                given_names="Nombre Privado",
                xref=0,
                image_x0=25,
                image_y0=178,
                image_x1=102,
                image_y1=273,
                name_lines=1,
            )
        ],
        pages=[PhotoRosterPageSummary(1, 0, 1, 1, 1, 0, 1)],
        issues=[],
        group_raw="GRUPO PRIVADO",
        group_code="GRUPO PRIVADO",
        tutor="Tutor Privado, Nombre",
    )

    print_photo_roster_check(result)
    output = capsys.readouterr().out
    assert secret not in output
    assert "Apellido Privado" not in output
    assert "listado-real.pdf" not in output
    assert "GRUPO PRIVADO" not in output
    assert "Tutor Privado" not in output
    assert "Alumnos emparejados: 1" in output
    assert "fotos=0 sin_foto=1 parejas=1" in output
