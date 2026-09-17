from itaca_idoceo import core
from itaca_idoceo.core import Student, TextLine, Word


HEIGHT = 842.0


def make_line(text: str, block: int, line_no: int, raw_y: float) -> TextLine:
    words = [
        Word(token, 0.0, raw_y, 1.0, raw_y + 1.0, block, line_no, i)
        for i, token in enumerate(text.split())
    ]
    return TextLine(block=block, line=line_no, words=words)


def student(block: int, ordinal: int, given_names: str, materia: str = "") -> Student:
    return Student(
        page=1,
        block=block,
        ordinal=ordinal,
        nia=f"1000000{ordinal}",
        full_name=f"PEREZ, {given_names}",
        surnames="PEREZ",
        given_names=given_names,
        row_x=0.0,
        visual_y=float(ordinal),
        materia=materia,
    )


def anchor_block(block: int, ordinal: int):
    return [
        make_line(str(ordinal), block, 0, 803.0),
        make_line("12345678", block, 1, 742.4),
        make_line("PEREZ, ANA", block, 2, 560.0),
    ]


def test_augments_materia_and_repetix_from_orphan_block(monkeypatch):
    s11 = student(22, 11, "ANA")
    s12 = student(23, 12, "BEA", materia="MUS1 MUS2")
    s13 = student(25, 13, "CARLA")

    continuation_materia = make_line("MUS3 MUS4", 24, 0, 120.0)
    continuation_r = make_line("R", 24, 1, 695.2)
    blocks = {
        22: anchor_block(22, 11),
        23: anchor_block(23, 12),
        24: [continuation_materia, continuation_r],
        25: anchor_block(25, 13),
    }
    visual = {
        id(continuation_materia): 325.2,
        id(continuation_r): 320.4,
    }
    monkeypatch.setattr(core, "visual_line_center_y", lambda _page, line: visual.get(id(line), 0.0))

    core._augment_wrapped_rows(
        None,
        blocks,
        [s11, s12, s13],
        {22: 304.9, 23: 320.4, 25: 339.4},
        HEIGHT,
    )

    assert s12.repetix == "R"
    assert s12.materia == "MUS1 MUS2 MUS3 MUS4"
    assert s11.materia == ""
    assert s13.materia == ""


def test_augments_long_name_plus_optional_fields(monkeypatch):
    s21 = student(31, 21, "ALBA")
    s22 = student(32, 22, "JUAN MARIA", materia="MAT1 MAT2")
    s23 = student(34, 23, "LUIS")

    name_cont = make_line("DEL VAL", 33, 0, 639.1)
    materia = make_line("MAT3 MAT4", 33, 1, 186.8)
    repetix = make_line("R", 33, 2, 695.2)
    blocks = {
        31: anchor_block(31, 21),
        32: anchor_block(32, 22),
        33: [name_cont, materia, repetix],
        34: anchor_block(34, 23),
    }
    visual = {id(name_cont): 438.2, id(materia): 433.4, id(repetix): 433.4}
    monkeypatch.setattr(core, "visual_line_center_y", lambda _page, line: visual.get(id(line), 0.0))

    core._augment_wrapped_rows(
        None,
        blocks,
        [s21, s22, s23],
        {31: 417.9, 32: 433.4, 34: 448.9},
        HEIGHT,
    )

    assert s22.given_names == "JUAN MARIA DEL VAL"
    assert s22.full_name == "PEREZ, JUAN MARIA DEL VAL"
    assert s22.repetix == "R"
    assert s22.materia == "MAT1 MAT2 MAT3 MAT4"


def test_never_crosses_an_unparsed_orde_nia_anchor(monkeypatch):
    """Una fila con ORDE+NIA que no sea Student sigue siendo una frontera."""
    s10 = student(20, 10, "ANA")
    s12 = student(23, 12, "CARLA")

    # 21 tiene ORDE+NIA pero simulamos que el detector estable no pudo crear
    # Student (p. ej. nombre no parseable). El bloque 22 no puede atribuirse a 10.
    skipped_anchor = [
        make_line("11", 21, 0, 803.0),
        make_line("12345678", 21, 1, 742.4),
    ]
    foreign_continuation = make_line("R", 22, 0, 695.2)
    blocks = {
        20: anchor_block(20, 10),
        21: skipped_anchor,
        22: [foreign_continuation],
        23: anchor_block(23, 12),
    }
    monkeypatch.setattr(core, "visual_line_center_y", lambda _page, _line: 105.0)

    core._augment_wrapped_rows(
        None,
        blocks,
        [s10, s12],
        {20: 100.0, 23: 130.0},
        HEIGHT,
    )

    assert s10.repetix == ""
    assert s12.repetix == ""


def test_wrapped_materia_in_name_raw_range_uses_visual_column(monkeypatch):
    """Regresión: un bloque de MATÈRIA no puede acabar añadido al nombre.

    En el PDF real que motivó este caso, el bloque huérfano tenía raw_f≈0.54,
    que cae en el rango histórico de nombre, pero visualmente empezaba en la
    misma X que MATÈRIA. La geometría de la fila ancla debe prevalecer.
    """
    s14 = student(31, 14, "ABCD", materia="MATBASE")
    s15 = student(33, 15, "EFGH")

    row14 = anchor_block(31, 14)
    name_line = row14[2]
    materia_anchor = make_line("MAT1 MAT2", 31, 3, 28.0)
    row14.append(materia_anchor)
    orphan = make_line("XYZ", 32, 0, 453.6)

    blocks = {
        31: row14,
        32: [orphan],
        33: anchor_block(33, 15),
    }

    visual_y = {id(orphan): 396.2}
    monkeypatch.setattr(
        core,
        "visual_line_center_y",
        lambda _page, line: visual_y.get(id(line), 0.0),
    )

    visual_bounds = {
        id(name_line): (164.0, 275.0),
        id(materia_anchor): (374.0, 814.0),
        id(orphan): (374.0, 388.0),
    }
    monkeypatch.setattr(
        core,
        "visual_line_bounds",
        lambda _page, line: visual_bounds.get(id(line), (0.0, 1.0)),
    )

    core._augment_wrapped_rows(
        object(),
        blocks,
        [s14, s15],
        {31: 391.4, 33: 406.9},
        HEIGHT,
    )

    assert s14.given_names == "ABCD"
    assert s14.full_name == "PEREZ, ABCD"
    assert s14.materia == "MATBASE XYZ"
