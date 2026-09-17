from pathlib import Path

import itaca_idoceo.selection_export as selection_export
from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.photo_export import PhotoExportResult
from itaca_idoceo.photo_roster import PhotoRosterPageSummary, PhotoRosterResult, PhotoRosterStudent


def _student() -> Student:
    return Student(
        page=1,
        block=1,
        ordinal=1,
        nia="1001",
        full_name="GARCIA, ANA",
        surnames="GARCIA",
        given_names="ANA",
        row_x=0.0,
        visual_y=1.0,
    )


def _reference(path: Path, group: str) -> PdfResult:
    cls = ClassResult(
        source=path,
        metadata=PageMetadata(group_raw=group, group_code=group, course="3ESO"),
        students=[_student()],
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


def _photo(path: Path, group: str) -> PhotoRosterResult:
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
        group_raw=group,
        group_code=group,
    )


def test_mixed_export_folder_uses_group_inside_photo_pdf(tmp_path, monkeypatch):
    photo_pdf = tmp_path / "verReport_1234567890.pdf"
    reference_pdf = tmp_path / "referencia.pdf"
    output = tmp_path / "out"
    photo = _photo(photo_pdf, "3ESO A")
    analysis = selection_export.SelectionAnalysis(
        pdfs=[reference_pdf, photo_pdf],
        references={reference_pdf: _reference(reference_pdf, "3ESO A")},
        photo_rosters={photo_pdf: photo},
    )

    captured = {}

    def fake_export(pdf_path, output_dir, **kwargs):
        captured["output_dir"] = output_dir
        output_dir.mkdir(parents=True)
        photos = output_dir / "fotos_por_nia"
        photos.mkdir()
        xlsx = output_dir / "alumnado_idoceo.xlsx"
        xlsx.write_bytes(b"xlsx")
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

    assert captured["output_dir"].name == "3ESO A_idoceo"
    assert summary.items[0].output.name == "3ESO A_idoceo"
    assert "verReport_1234567890_idoceo" not in summary.summary_path.read_text(encoding="utf-8")


def test_reference_only_export_keeps_group_based_xlsx_name(tmp_path):
    reference_pdf = tmp_path / "verReport_9876543210.pdf"
    output = tmp_path / "out"
    analysis = selection_export.SelectionAnalysis(
        pdfs=[reference_pdf],
        references={reference_pdf: _reference(reference_pdf, "3ESO B")},
    )

    summary = selection_export.export_analyzed_selection(analysis, output)

    assert summary.mode == "reference"
    assert summary.items[0].output is not None
    assert summary.items[0].output.name == "3ESO B_idoceo.xlsx"
