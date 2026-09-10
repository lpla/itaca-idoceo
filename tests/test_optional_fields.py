from pathlib import Path

from openpyxl import load_workbook

from itaca_idoceo import core
from itaca_idoceo.core import ClassResult, PageMetadata, Student, TextLine, Word


def line(text: str, number: int) -> TextLine:
    words = [
        Word(token, 0.0, 0.0, 1.0, 1.0, 1, number, index)
        for index, token in enumerate(text.split())
    ]
    return TextLine(block=1, line=number, words=words)


def test_optional_student_fields_are_taken_from_columns(monkeypatch):
    orde = line("1", 0)
    nia = line("12345678", 1)
    repetix = line("R", 2)
    name = line("PÉREZ, ANA", 3)
    materia_1 = line("MUS VAL", 4)
    materia_2 = line("OPT", 5)
    lines = [orde, nia, repetix, name, materia_1, materia_2]

    positions = {
        id(orde): (10.0, 20.0),
        id(nia): (30.0, 45.0),
        id(repetix): (55.0, 60.0),
        id(name): (70.0, 130.0),
        id(materia_1): (150.0, 200.0),
        id(materia_2): (210.0, 230.0),
    }
    monkeypatch.setattr(core, "visual_line_bounds", lambda _page, value: positions[id(value)])

    repeat_value, materia_value = core.extract_optional_student_fields(
        None, lines, orde, nia, name
    )

    assert repeat_value == "R"
    assert materia_value == "MUS VAL OPT"


def test_optional_student_fields_allow_empty_repetix(monkeypatch):
    orde = line("1", 0)
    nia = line("12345678", 1)
    name = line("PÉREZ, ANA", 3)
    materia = line("MUS", 4)
    lines = [orde, nia, name, materia]

    positions = {
        id(orde): (10.0, 20.0),
        id(nia): (30.0, 45.0),
        id(name): (70.0, 130.0),
        id(materia): (150.0, 200.0),
    }
    monkeypatch.setattr(core, "visual_line_bounds", lambda _page, value: positions[id(value)])

    repeat_value, materia_value = core.extract_optional_student_fields(
        None, lines, orde, nia, name
    )

    assert repeat_value == ""
    assert materia_value == "MUS"


def test_xlsx_optional_columns(tmp_path: Path):
    student = Student(
        page=1,
        block=1,
        ordinal=1,
        nia="12345678",
        full_name="PÉREZ, ANA",
        surnames="PÉREZ",
        given_names="ANA",
        row_x=1.0,
        visual_y=1.0,
        repetix="R",
        materia="MUS OPT",
    )
    result = ClassResult(
        source=Path("listado.pdf"),
        metadata=PageMetadata(group_code="G1"),
        students=[student],
        issues=[],
    )
    output = tmp_path / "out.xlsx"

    core.write_idoceo_xlsx(
        result,
        output,
        include_nia=True,
        include_repetix=True,
        include_materia=True,
    )

    sheet = load_workbook(output).active
    assert [cell.value for cell in sheet[1]] == [
        "Apellidos", "Nombre", "NIA", "REPETIX", "MATÈRIA"
    ]
    assert [cell.value for cell in sheet[2]] == [
        "PÉREZ", "ANA", "12345678", "R", "MUS OPT"
    ]


def positioned_line(text: str, number: int, y: float, x: float = 0.0) -> TextLine:
    words = [
        Word(token, x, y, x + 1.0, y + 1.0, 1, number, index)
        for index, token in enumerate(text.split())
    ]
    return TextLine(block=1, line=number, words=words)
