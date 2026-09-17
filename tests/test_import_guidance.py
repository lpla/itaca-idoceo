from pathlib import Path

from openpyxl import load_workbook

import itaca_idoceo.selection_export as selection_export
from itaca_idoceo.core import ClassResult, PageMetadata, PdfResult, Student
from itaca_idoceo.idoceo_instructions import build_import_instructions


def _reference_with_uppercase_name(path: Path) -> PdfResult:
    student = Student(
        page=1,
        block=1,
        ordinal=1,
        nia="1001",
        full_name="GARCÍA DE LA FUENTE, MARÍA-JOSÉ",
        surnames="GARCÍA DE LA FUENTE",
        given_names="MARÍA-JOSÉ",
        row_x=0.0,
        visual_y=1.0,
    )
    cls = ClassResult(
        source=path,
        metadata=PageMetadata(group_raw="3ESO A", group_code="3ESO A", course="3ESO"),
        students=[student],
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


def test_import_guide_contains_current_new_existing_and_photo_flows():
    text = build_import_instructions(has_photos=True, normalize_names=True)

    assert "pulsa + en la esquina inferior derecha" in text
    assert "Elige Clase" in text
    assert "Herramientas" in text
    assert "Importar fichero CSV/XLS" in text
    assert "ACTUALIZAR UNA CLASE EXISTENTE SIN PERDER LA EVALUACIÓN" in text
    assert "añade los alumnos nuevos" in text
    assert "Plano" in text
    assert "botón del martillo" in text
    assert "Importación masiva" in text
    assert "Número de identificación" in text
    assert "Apellidos, Nombre" in text
    assert "misma opción" in text


def test_reference_only_export_can_normalize_names_and_writes_import_guide(tmp_path):
    ref = tmp_path / "referencia.pdf"
    output = tmp_path / "out"
    analysis = selection_export.SelectionAnalysis(
        pdfs=[ref],
        references={ref: _reference_with_uppercase_name(ref)},
    )

    summary = selection_export.export_analyzed_selection(
        analysis,
        output,
        normalize_names=True,
    )

    workbook = load_workbook(summary.items[0].output)
    sheet = workbook.active
    assert sheet["A2"].value == "García de la Fuente"
    assert sheet["B2"].value == "María-José"
    assert sheet["C2"].value == "1001"
    assert summary.import_guide_path.is_file()
    assert "ACTUALIZAR UNA CLASE EXISTENTE" in summary.import_guide_path.read_text(
        encoding="utf-8"
    )
    assert summary.normalize_names is True
