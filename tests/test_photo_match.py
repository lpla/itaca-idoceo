from pathlib import Path

from itaca_idoceo.core import ClassResult, PageMetadata, Student
from itaca_idoceo.photo_match import match_photo_result_to_class
from itaca_idoceo.photo_roster import (
    PhotoRosterPageSummary,
    PhotoRosterResult,
    PhotoRosterStudent,
)


def _photo_student(
    ordinal: int,
    surnames: str,
    given_names: str,
) -> PhotoRosterStudent:
    return PhotoRosterStudent(
        page=1,
        ordinal=ordinal,
        row=1,
        column=ordinal,
        full_name=f"{surnames}, {given_names}",
        surnames=surnames,
        given_names=given_names,
        xref=ordinal,
        image_x0=float(ordinal * 10),
        image_y0=100.0,
        image_x1=float(ordinal * 10 + 8),
        image_y1=120.0,
        name_lines=1,
    )


def _reference_student(
    ordinal: int,
    surnames: str,
    given_names: str,
    nia: str,
) -> Student:
    return Student(
        page=1,
        block=ordinal,
        ordinal=ordinal,
        nia=nia,
        full_name=f"{surnames}, {given_names}",
        surnames=surnames,
        given_names=given_names,
        row_x=0.0,
        visual_y=float(ordinal),
        repetix="R" if ordinal == 1 else "",
        materia="MÚSICA",
    )


def _photo_result(students: list[PhotoRosterStudent]) -> PhotoRosterResult:
    return PhotoRosterResult(
        source=Path("fotos.pdf"),
        page_count=1,
        students=students,
        pages=[
            PhotoRosterPageSummary(
                page=1,
                candidate_photos=len(students),
                paired_students=len(students),
                rows=1,
                max_columns=len(students),
                wrapped_names=0,
                missing_photos=0,
            )
        ],
        issues=[],
        group_raw="3ESO A - 3ESO A",
        group_code="3ESO A",
        tutor="Tutor, Persona",
    )


def _reference_class(students: list[Student]) -> ClassResult:
    return ClassResult(
        source=Path("tabular.pdf"),
        metadata=PageMetadata(
            group_raw="3ESO A - 3ESO A",
            group_code="3ESO A",
            course="3 ESO",
            tutor="Tutor, Persona",
        ),
        students=students,
        issues=[],
    )


def test_name_crosscheck_uses_conservative_normalization_stages():
    photo_students = [
        _photo_student(1, "García-López", "Ana María"),
        _photo_student(2, "D’Angelo", "Joan"),
        _photo_student(3, "Muñoz", "Óscar"),
        _photo_student(4, "L·Lorca", "Núria"),
    ]
    reference_students = [
        _reference_student(1, "García-López", "Ana María", "1001"),
        _reference_student(2, "D'Angelo", "Joan", "1002"),
        _reference_student(3, "Munoz", "Oscar", "1003"),
        _reference_student(4, "Llorca", "Nuria", "1004"),
        _reference_student(5, "Alumno Extra", "No Cursa", "1005"),
    ]

    result = match_photo_result_to_class(
        _photo_result(photo_students),
        _reference_class(reference_students),
    )

    assert result.is_valid
    assert result.matched_photos == 4
    assert result.reference_students == 5
    assert result.unmatched_photos == 0
    assert result.ambiguous_photos == 0
    assert result.method_counts == {
        "exact": 1,
        "structural": 1,
        "folded": 1,
        "compact": 1,
    }
    assert [
        link.reference.nia for link in result.links
    ] == ["1001", "1002", "1003", "1004"]


def test_name_crosscheck_refuses_ambiguous_normalized_name():
    photo_students = [_photo_student(1, "Garcìa", "Ana")]
    reference_students = [
        _reference_student(1, "Garcia", "Ana", "1001"),
        _reference_student(2, "García", "Ana", "1002"),
    ]

    result = match_photo_result_to_class(
        _photo_result(photo_students),
        _reference_class(reference_students),
    )

    assert not result.is_valid
    assert result.matched_photos == 0
    assert result.unmatched_photos == 0
    assert result.ambiguous_photos == 1


def test_name_crosscheck_refuses_unmatched_student_instead_of_guessing():
    photo_students = [_photo_student(1, "Completamente Distinto", "Alumne")]
    reference_students = [
        _reference_student(1, "Garcia", "Ana", "1001"),
        _reference_student(2, "Perez", "Bea", "1002"),
    ]

    result = match_photo_result_to_class(
        _photo_result(photo_students),
        _reference_class(reference_students),
    )

    assert not result.is_valid
    assert result.matched_photos == 0
    assert result.unmatched_photos == 1
    assert result.ambiguous_photos == 0
