from itaca_idoceo.core import TextLine, Word, canonical_group_code, parse_person_name


def make_line(text: str) -> TextLine:
    words = []
    for i, token in enumerate(text.split()):
        words.append(
            Word(
                text=token,
                x0=float(i), y0=500.0, x1=float(i + 1), y1=510.0,
                block=1, line=1, number=i,
            )
        )
    return TextLine(block=1, line=1, words=words)


def test_person_name_simple():
    assert parse_person_name(make_line("PÉREZ GARCÍA, JUAN")) == (
        "PÉREZ GARCÍA, JUAN", "PÉREZ GARCÍA", "JUAN"
    )


def test_person_name_with_particles_and_multiple_words():
    assert parse_person_name(make_line("DE LA FUENTE PÉREZ, JUAN DEL VAL")) == (
        "DE LA FUENTE PÉREZ, JUAN DEL VAL",
        "DE LA FUENTE PÉREZ",
        "JUAN DEL VAL",
    )


def test_comma_must_be_attached_to_last_surname():
    assert parse_person_name(make_line("PÉREZ GARCÍA , JUAN")) is None


def test_group_code():
    assert canonical_group_code("4ESOF - 4ESOF") == "4ESOF"


def test_person_name_one_surname_many_given_name_words():
    assert parse_person_name(make_line("PÉREZ, JUAN DEL VAL")) == (
        "PÉREZ, JUAN DEL VAL", "PÉREZ", "JUAN DEL VAL"
    )


def test_person_name_without_comma_rejected():
    assert parse_person_name(make_line("PÉREZ GARCÍA JUAN")) is None
