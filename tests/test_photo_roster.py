from pathlib import Path

from itaca_idoceo.photo_roster import (
    NameBlock,
    PhotoCandidate,
    PhotoRosterPageSummary,
    PhotoRosterResult,
    PhotoRosterStudent,
    _cluster_rows,
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
                xref=6,
                image_x0=25,
                image_y0=178,
                image_x1=102,
                image_y1=273,
                name_lines=1,
            )
        ],
        pages=[PhotoRosterPageSummary(1, 1, 1, 1, 1, 0)],
        issues=[],
    )

    print_photo_roster_check(result)
    output = capsys.readouterr().out
    assert secret not in output
    assert "Apellido Privado" not in output
    assert "listado-real.pdf" not in output
    assert "Alumnos emparejados: 1" in output
