from pathlib import Path

from itaca_idoceo.core import AssignedStudent, Student, _build_class_result


def student(ordinal: int, nia: str, page: int = 1) -> Student:
    return Student(
        page=page,
        block=ordinal,
        ordinal=ordinal,
        nia=nia,
        full_name=f"COGNOM, NOM{ordinal}",
        surnames="COGNOM",
        given_names=f"NOM{ordinal}",
        row_x=float(ordinal),
        visual_y=float(ordinal),
    )


def assigned(
    ordinal: int,
    nia: str,
    group: str,
    course: str,
    course_section: int = 1,
) -> AssignedStudent:
    return AssignedStudent(
        student=student(ordinal, nia),
        group_raw=f"{group} - {group}",
        group_code=group,
        course=course,
        tutor=None,
        course_section=course_section,
    )


def test_orde_is_validated_per_group_not_per_pdf():
    source = Path("fp.pdf")
    first = _build_class_result(
        source,
        "FP1A",
        [assigned(1, "100", "FP1A", "PRIMER"), assigned(2, "101", "FP1A", "PRIMER")],
    )
    second = _build_class_result(
        source,
        "FP2A",
        [assigned(1, "200", "FP2A", "SEGON"), assigned(2, "201", "FP2A", "SEGON")],
    )
    assert first.issues == []
    assert second.issues == []


def test_batx_course_specialisation_with_orde_restart_is_valid():
    source = Path("batx.pdf")
    rows = [
        assigned(i, f"100{i}", "1BATXH", "PRIMER BATX", course_section=1)
        for i in range(1, 22)
    ] + [
        assigned(
            i,
            f"200{i}",
            "1BATXH",
            "PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS",
            course_section=2,
        )
        for i in range(1, 12)
    ]

    result = _build_class_result(source, "1BATXH", rows)

    assert len(result.students) == 32
    assert result.metadata.course == "PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS"
    assert result.course_values == (
        "PRIMER BATX",
        "PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS",
    )
    assert result.issues == []


def test_repeated_course_header_with_continuing_orde_is_not_a_new_run():
    source = Path("multi_page.pdf")
    rows = [
        assigned(1, "100", "G1", "TERCER", course_section=1),
        assigned(2, "101", "G1", "TERCER", course_section=1),
        assigned(3, "102", "G1", "TERCER", course_section=2),
        assigned(4, "103", "G1", "TERCER", course_section=2),
    ]

    result = _build_class_result(source, "G1", rows)
    assert result.issues == []


def test_orde_restart_without_new_course_header_is_reported():
    source = Path("broken.pdf")
    rows = [
        assigned(1, "100", "G1", "TERCER", course_section=1),
        assigned(2, "101", "G1", "TERCER", course_section=1),
        assigned(1, "102", "G1", "TERCER", course_section=1),
        assigned(2, "103", "G1", "TERCER", course_section=1),
    ]

    result = _build_class_result(source, "G1", rows)
    assert any("sin haberse detectado una nueva fila CURS" in issue for issue in result.issues)
