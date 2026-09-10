from pathlib import Path

from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.diagnostics import build_anonymized_diagnostic


def test_anonymized_diagnostic_does_not_leak_metadata_or_student_data():
    secret_name = "CENTRO-SECRETO - Pérez, Ana.pdf"
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
    )
    cls = ClassResult(
        source=Path(secret_name),
        metadata=PageMetadata(
            group_raw="1BATXA - 1BATXA",
            group_code="1BATXA",
            course="PRIMER BATX. SECRET",
            tutor="TUTOR SECRETO",
        ),
        students=[student],
        issues=[],
        course_values=("PRIMER BATX", "PRIMER BATX. SECRET"),
    )
    result = PdfResult(
        source=Path(secret_name),
        classes=[cls],
        page_count=2,
        issues=[],
        report_signature=True,
        signature_pages=(1, 2),
    )

    text = build_anonymized_diagnostic(
        [result],
        environment={"Sistema": "Darwin", "Python": "3.14.0"},
    )

    for secret in (
        secret_name,
        "PÉREZ",
        "ANA",
        "12345678",
        "1BATXA",
        "SECRET",
        "TUTOR SECRETO",
    ):
        assert secret not in text

    assert "Alumnos detectados: 1" in text
    assert "Secciones CURS detectadas: 2" in text
    assert "Firma ITACA 3: detectada" in text


def test_unknown_issue_detail_is_hidden():
    result = PdfResult(
        source=Path("x.pdf"),
        classes=[],
        page_count=1,
        issues=["Fallo inesperado con ALUMNO-SECRETO"],
    )
    text = build_anonymized_diagnostic([result])
    assert "ALUMNO-SECRETO" not in text
    assert "detalle omitido por privacidad" in text
