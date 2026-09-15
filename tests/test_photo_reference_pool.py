from pathlib import Path

from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.photo_reference_pool import (
    match_photo_result_to_references,
    print_reference_pool_match,
)
from itaca_idoceo.photo_roster import (
    PhotoRosterPageSummary,
    PhotoRosterResult,
    PhotoRosterStudent,
)
import itaca_idoceo.photo_reference_pool as photo_reference_pool


def _photo_student(ordinal: int, surnames: str, given_names: str) -> PhotoRosterStudent:
    return PhotoRosterStudent(
        page=1,
        ordinal=ordinal,
        row=(ordinal - 1) // 6 + 1,
        column=(ordinal - 1) % 6 + 1,
        full_name=f"{surnames}, {given_names}",
        surnames=surnames,
        given_names=given_names,
        xref=ordinal,
        image_x0=0,
        image_y0=0,
        image_x1=10,
        image_y1=10,
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
        row_x=0,
        visual_y=float(ordinal),
    )


def _class(group: str, students: list[Student]) -> ClassResult:
    return ClassResult(
        source=Path(f"{group}.pdf"),
        metadata=PageMetadata(group_raw=group, group_code=group),
        students=students,
        issues=[],
    )


def _pdf(path: Path, classes: list[ClassResult]) -> PdfResult:
    return PdfResult(
        source=path,
        classes=classes,
        page_count=1,
        issues=[],
        report_signature=True,
        signature_pages=(1,),
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


def test_reference_pool_can_find_student_in_another_group(tmp_path, monkeypatch):
    photo = _photo_result(
        [
            _photo_student(1, "Garcia", "Ana"),
            _photo_student(2, "Perez", "Bea"),
        ]
    )
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    results = {
        first: _pdf(first, [_class("3ESO A", [_reference_student(1, "Garcia", "Ana", "1001")])]),
        second: _pdf(second, [_class("3ESO B", [_reference_student(1, "Perez", "Bea", "1002")])]),
    }
    monkeypatch.setattr(photo_reference_pool, "process_pdf", lambda path: results[path])

    result = match_photo_result_to_references(photo, [first, second])

    assert result.is_valid
    assert result.match.matched_photos == 2
    assert result.same_group_students == 1
    assert result.unique_students == 2
    assert [link.reference.nia for link in result.match.links] == ["1001", "1002"]


def test_reference_pool_deduplicates_same_nia_across_pdfs(tmp_path, monkeypatch):
    photo = _photo_result([_photo_student(1, "Garcia", "Ana")])
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    same = _reference_student(1, "Garcia", "Ana", "1001")
    results = {
        first: _pdf(first, [_class("3ESO A", [same])]),
        second: _pdf(second, [_class("3ESO B", [_reference_student(1, "Garcia", "Ana", "1001")])]),
    }
    monkeypatch.setattr(photo_reference_pool, "process_pdf", lambda path: results[path])

    result = match_photo_result_to_references(photo, [first, second])

    assert result.is_valid
    assert result.unique_students == 1
    assert result.match.ambiguous_photos == 0


def test_reference_pool_reports_unresolved_grid_position(tmp_path, monkeypatch):
    photo = _photo_result(
        [
            _photo_student(1, "Garcia", "Ana"),
            _photo_student(2, "Nuevo", "Alumno"),
        ]
    )
    first = tmp_path / "a.pdf"
    results = {
        first: _pdf(first, [_class("3ESO A", [_reference_student(1, "Garcia", "Ana", "1001")])]),
    }
    monkeypatch.setattr(photo_reference_pool, "process_pdf", lambda path: results[path])

    result = match_photo_result_to_references(photo, [first])

    assert not result.is_valid
    assert result.match.matched_photos == 1
    assert result.unresolved_positions == [(2, 1, 2, True)]
    diagnostic = result.unresolved_diagnostics[0]
    assert diagnostic.ordinal == 2
    assert diagnostic.best_score is None


def test_reference_pool_reports_anonymous_similarity_for_unresolved(tmp_path, monkeypatch, capsys):
    photo = _photo_result(
        [
            _photo_student(1, "Garcia", "Ana"),
            _photo_student(2, "Martinez", "Alejandro"),
            _photo_student(3, "Alumno Nuevo", "Sin Referencia"),
        ]
    )
    first = tmp_path / "a.pdf"
    results = {
        first: _pdf(
            first,
            [
                _class(
                    "3ESO A",
                    [
                        _reference_student(1, "Garcia", "Ana", "1001"),
                        # Similar, pero suficientemente distinto para no cruzarse automáticamente.
                        _reference_student(2, "Martines", "Alexandro", "1002"),
                        _reference_student(3, "Persona Distinta", "Otra", "1003"),
                    ],
                )
            ],
        ),
    }
    monkeypatch.setattr(photo_reference_pool, "process_pdf", lambda path: results[path])

    result = match_photo_result_to_references(photo, [first])

    assert not result.is_valid
    assert result.match.matched_photos == 1
    diagnostics = result.unresolved_diagnostics
    assert [item.ordinal for item in diagnostics] == [2, 3]
    assert diagnostics[0].best_score is not None
    assert diagnostics[0].best_score > diagnostics[1].best_score

    print_reference_pool_match(result)
    output = capsys.readouterr().out
    assert "Diagnóstico anónimo de pendientes:" in output
    assert "#2 (fila 1, columna 2" in output
    assert "score=" in output
    # El diagnóstico compartible no debe filtrar PII de ninguno de los dos PDF.
    assert "Martinez" not in output
    assert "Martines" not in output
    assert "1002" not in output
