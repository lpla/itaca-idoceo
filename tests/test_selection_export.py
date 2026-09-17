from pathlib import Path

from openpyxl import load_workbook

import itaca_idoceo.selection_export as selection_export
from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.photo_export import PhotoExportResult
from itaca_idoceo.photo_roster import PhotoRosterPageSummary, PhotoRosterResult, PhotoRosterStudent


def _student(ordinal: int, nia: str = "1001") -> Student:
    return Student(
        page=1,
        block=ordinal,
        ordinal=ordinal,
        nia=nia,
        full_name="GARCIA, ANA",
        surnames="GARCIA",
        given_names="ANA",
        row_x=0.0,
        visual_y=float(ordinal),
    )


def _reference(path: Path) -> PdfResult:
    cls = ClassResult(
        source=path,
        metadata=PageMetadata(group_raw="3ESO A", group_code="3ESO A", course="3ESO"),
        students=[_student(1)],
        issues=[],
    )
    return PdfResult(
        source=path,
        classes=[cls],
        page_count=1,
        issues=[],
        report_signature=True,
        signature_pages=(1,),
    )


def _photo(path: Path) -> PhotoRosterResult:
    student = PhotoRosterStudent(
        page=1,
        ordinal=1,
        row=1,
        column=1,
        full_name="GARCIA, ANA",
        surnames="GARCIA",
        given_names="ANA",
        xref=1,
        image_x0=0,
        image_y0=0,
        image_x1=10,
        image_y1=10,
        name_lines=1,
    )
    return PhotoRosterResult(
        source=path,
        page_count=1,
        students=[student],
        pages=[PhotoRosterPageSummary(1, 1, 1, 1, 1, 0, 0)],
        issues=[],
        group_raw="3ESO A",
        group_code="3ESO A",
    )


def test_mixed_selection_uses_all_references_but_only_exports_photo_rosters(tmp_path, monkeypatch):
    ref_a = tmp_path / "ref_a.pdf"
    ref_b = tmp_path / "ref_b.pdf"
    photo = tmp_path / "materia.pdf"
    output = tmp_path / "out"
    analysis = selection_export.SelectionAnalysis(
        pdfs=[ref_a, ref_b, photo],
        references={ref_a: _reference(ref_a), ref_b: _reference(ref_b)},
        photo_rosters={photo: _photo(photo)},
    )

    calls = []

    def fake_export(pdf_path, output_dir, *, reference_pdfs, include_repetix, include_materia):
        calls.append((pdf_path, tuple(reference_pdfs)))
        output_dir.mkdir(parents=True)
        xlsx = output_dir / "alumnado_idoceo.xlsx"
        xlsx.write_bytes(b"xlsx")
        photos = output_dir / "fotos_por_nia"
        photos.mkdir()
        guide = output_dir / "IMPORTAR_EN_IDOCEO.txt"
        guide.write_text("ok", encoding="utf-8")
        return PhotoExportResult(
            output_dir=output_dir,
            xlsx_path=xlsx,
            photos_dir=photos,
            manual_photos_dir=None,
            guide_path=guide,
            students=1,
            matched_students=1,
            unmatched_students=0,
            photos=1,
            missing_photos=0,
            match_field="NIA",
            automatic_matches=1,
            manual_matches=0,
        )

    monkeypatch.setattr(selection_export, "export_photo_roster", fake_export)

    summary = selection_export.export_analyzed_selection(analysis, output)

    assert calls == [(photo, (ref_a, ref_b))]
    assert summary.mode == "photo"
    assert len(summary.items) == 1
    assert summary.items[0].status == selection_export.STATUS_READY
    assert summary.items[0].photos_by_nia == 1
    assert not list(output.glob("*.xlsx"))
    assert summary.summary_path.is_file()


def test_photo_selection_with_unmatched_student_is_warning_not_blocking(tmp_path, monkeypatch):
    ref = tmp_path / "ref.pdf"
    photo = tmp_path / "materia.pdf"
    output = tmp_path / "out"
    analysis = selection_export.SelectionAnalysis(
        pdfs=[ref, photo],
        references={ref: _reference(ref)},
        photo_rosters={photo: _photo(photo)},
    )

    def fake_export(pdf_path, output_dir, *, reference_pdfs, include_repetix, include_materia):
        output_dir.mkdir(parents=True)
        xlsx = output_dir / "alumnado_idoceo.xlsx"
        xlsx.write_bytes(b"xlsx")
        photos = output_dir / "fotos_por_nia"
        photos.mkdir()
        by_name = output_dir / "fotos_por_nombre"
        by_name.mkdir()
        guide = output_dir / "IMPORTAR_EN_IDOCEO.txt"
        guide.write_text("ok", encoding="utf-8")
        return PhotoExportResult(
            output_dir=output_dir,
            xlsx_path=xlsx,
            photos_dir=photos,
            manual_photos_dir=by_name,
            guide_path=guide,
            students=2,
            matched_students=1,
            unmatched_students=1,
            photos=2,
            missing_photos=0,
            match_field="NIA",
            automatic_matches=1,
            manual_matches=1,
        )

    monkeypatch.setattr(selection_export, "export_photo_roster", fake_export)

    summary = selection_export.export_analyzed_selection(analysis, output)

    assert summary.exit_code == 0
    assert summary.warning_items == 1
    assert summary.blocking_items == 0
    assert summary.items[0].status == selection_export.STATUS_WARNING
    assert summary.items[0].photos_by_name == 1


def test_reference_only_selection_exports_xlsx_with_nia_by_default(tmp_path):
    ref = tmp_path / "ref.pdf"
    output = tmp_path / "out"
    analysis = selection_export.SelectionAnalysis(
        pdfs=[ref],
        references={ref: _reference(ref)},
    )

    summary = selection_export.export_analyzed_selection(analysis, output)

    assert summary.mode == "reference"
    assert summary.exit_code == 0
    assert len(summary.items) == 1
    workbook = load_workbook(summary.items[0].output)
    assert [cell.value for cell in workbook.active[1]] == ["Apellidos", "Nombre", "NIA"]
    assert workbook.active["C2"].value == "1001"
