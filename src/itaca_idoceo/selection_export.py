from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .core import (
    PdfResult,
    process_pdf,
    safe_filename_component,
    unique_output_path,
    write_idoceo_xlsx,
)
from .photo_export import PhotoExportResult, export_photo_roster
from .photo_roster import PhotoRosterResult, detect_photo_roster


STATUS_READY = "LISTO"
STATUS_MISSING_PHOTOS = "LISTO, FALTAN FOTOS"
STATUS_WARNING = "LISTO CON AVISOS"
STATUS_REVIEW = "REVISIÓN NECESARIA"


@dataclass
class SelectionAnalysis:
    pdfs: list[Path]
    references: dict[Path, PdfResult] = field(default_factory=dict)
    photo_rosters: dict[Path, PhotoRosterResult] = field(default_factory=dict)
    unsupported: dict[Path, str] = field(default_factory=dict)

    @property
    def mode(self) -> str:
        return "photo" if self.photo_rosters else "reference"


@dataclass(frozen=True)
class SelectionExportItem:
    source: Path
    kind: str
    status: str
    output: Path | None
    students: int
    matched_students: int = 0
    unmatched_students: int = 0
    photos: int = 0
    missing_photos: int = 0
    photos_by_nia: int = 0
    photos_by_name: int = 0
    message: str = ""


@dataclass
class SelectionExportSummary:
    output_dir: Path
    mode: str
    input_pdfs: int
    reference_pdfs: int
    photo_pdfs: int
    unsupported_pdfs: int
    items: list[SelectionExportItem]
    summary_path: Path

    @property
    def blocking_items(self) -> int:
        return sum(item.status == STATUS_REVIEW for item in self.items)

    @property
    def warning_items(self) -> int:
        return sum(item.status in {STATUS_WARNING, STATUS_MISSING_PHOTOS} for item in self.items)

    @property
    def ready_items(self) -> int:
        return sum(item.status != STATUS_REVIEW for item in self.items)

    @property
    def exit_code(self) -> int:
        return 2 if self.blocking_items else 0


def collect_pdf_paths(inputs: list[Path]) -> list[Path]:
    """Expande ficheros y carpetas en una única selección recursiva de PDF."""
    pdfs: set[Path] = set()
    for raw in inputs:
        path = raw.expanduser()
        if path.is_file() and path.suffix.casefold() == ".pdf":
            pdfs.add(path.resolve())
        elif path.is_dir():
            pdfs.update(
                candidate.resolve()
                for candidate in path.rglob("*.pdf")
                if candidate.is_file()
            )
    return sorted(pdfs, key=lambda path: str(path).casefold())


def analyze_selection(inputs: list[Path]) -> SelectionAnalysis:
    """Clasifica automáticamente PDF tabulares, listados con fotos y otros PDF."""
    pdfs = collect_pdf_paths(inputs)
    analysis = SelectionAnalysis(pdfs=pdfs)

    for pdf in pdfs:
        tabular_error: str | None = None
        try:
            tabular = process_pdf(pdf)
        except Exception as exc:
            tabular = None
            tabular_error = str(exc)

        if tabular is not None and tabular.report_signature and tabular.classes:
            analysis.references[pdf] = tabular
            continue

        try:
            photo = detect_photo_roster(pdf)
        except Exception as exc:
            detail = str(exc)
            if tabular_error:
                detail = f"{tabular_error}; {detail}"
            analysis.unsupported[pdf] = detail
            continue

        # Aunque haya incidencias, si se ha detectado alumnado lo conservamos
        # como listado fotográfico para poder mostrar "Revisión necesaria" en
        # vez de fingir que el formato es desconocido.
        if photo.students:
            analysis.photo_rosters[pdf] = photo
            continue

        detail = "; ".join(photo.issues)
        if tabular is not None and tabular.issues:
            detail = "; ".join([*tabular.issues, *photo.issues])
        analysis.unsupported[pdf] = detail or "Formato PDF no reconocido"

    return analysis


def _unique_directory(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.name}__{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def _photo_item(source: Path, result: PhotoExportResult) -> SelectionExportItem:
    if result.match_field == "NIA":
        photos_by_nia = result.automatic_matches
        photos_by_name = result.manual_matches
        if result.unmatched_students:
            status = STATUS_WARNING
            if photos_by_name:
                message = (
                    f"{result.unmatched_students} alumno(s) no aparecen en las referencias; "
                    f"{photos_by_name} foto(s) se han preparado por nombre y deben comprobarse."
                )
            else:
                message = (
                    f"{result.unmatched_students} alumno(s) no aparecen en las referencias y "
                    "se han conservado sin NIA."
                )
        elif result.missing_photos:
            status = STATUS_MISSING_PHOTOS
            message = f"{result.missing_photos} alumno(s) no tienen fotografía disponible."
        else:
            status = STATUS_READY
            message = "Todo el alumnado se ha identificado por NIA y tiene fotografía."
    else:
        photos_by_nia = 0
        photos_by_name = result.photos
        status = STATUS_WARNING
        message = (
            "No hay referencias tabulares con NIA: las fotografías se han preparado por "
            "nombre y deben comprobarse tras importarlas."
        )

    return SelectionExportItem(
        source=source,
        kind="photo",
        status=status,
        output=result.output_dir,
        students=result.students,
        matched_students=result.matched_students,
        unmatched_students=result.unmatched_students,
        photos=result.photos,
        missing_photos=result.missing_photos,
        photos_by_nia=photos_by_nia,
        photos_by_name=photos_by_name,
        message=message,
    )


def _write_local_summary(summary: SelectionExportSummary) -> None:
    lines = [
        "ITACA → iDoceo | resumen de exportación",
        "",
        "Modo: " + (
            "listados actuales de materia con fotos + referencias"
            if summary.mode == "photo"
            else "listados tabulares de referencia"
        ),
        f"PDF seleccionados: {summary.input_pdfs}",
        f"PDF de referencia: {summary.reference_pdfs}",
        f"PDF actuales con fotos: {summary.photo_pdfs}",
        f"PDF no utilizados: {summary.unsupported_pdfs}",
        "",
    ]

    if summary.mode == "photo":
        lines.extend(
            [
                "Cuando existen listados actuales con fotos, éstos determinan quién pertenece",
                "a cada clase. Los listados de referencia sólo se usan para recuperar NIA y",
                "otros metadatos; no añaden alumnado que ya no esté en el listado actual.",
                "",
            ]
        )

    for index, item in enumerate(summary.items, start=1):
        lines.append(f"Resultado {index}: {item.status}")
        lines.append(f"  Origen: {item.source.name}")
        lines.append(f"  Alumnos: {item.students}")
        if item.kind == "photo":
            lines.append(f"  Identificados por referencia: {item.matched_students}")
            lines.append(f"  Sin referencia inequívoca: {item.unmatched_students}")
            lines.append(f"  Fotos por NIA: {item.photos_by_nia}")
            lines.append(f"  Fotos por nombre para comprobar: {item.photos_by_name}")
            lines.append(f"  Sin foto: {item.missing_photos}")
        if item.output is not None:
            lines.append(f"  Salida: {item.output.name}")
        if item.message:
            lines.append(f"  Nota: {item.message}")
        lines.append("")

    summary.summary_path.write_text("\n".join(lines), encoding="utf-8")


def export_analyzed_selection(
    analysis: SelectionAnalysis,
    output_dir: Path,
    *,
    include_nia_for_reference: bool = True,
    include_repetix: bool = False,
    include_materia: bool = False,
) -> SelectionExportSummary:
    """Exporta toda una selección en una sola pasada.

    Si hay al menos un listado actual con fotos, sólo esos listados producen
    clases de salida y todos los PDF tabulares seleccionados actúan como una
    piscina común de referencias. Si no hay listados con fotos, se exportan los
    grupos de los PDF tabulares como hasta ahora.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    items: list[SelectionExportItem] = []

    if analysis.photo_rosters:
        references = list(analysis.references)
        for photo_pdf in sorted(analysis.photo_rosters, key=lambda path: str(path).casefold()):
            bundle = _unique_directory(
                output_dir / (safe_filename_component(photo_pdf.stem) + "_idoceo")
            )
            try:
                result = export_photo_roster(
                    photo_pdf,
                    bundle,
                    reference_pdfs=references,
                    include_repetix=include_repetix,
                    include_materia=include_materia,
                )
            except Exception as exc:
                items.append(
                    SelectionExportItem(
                        source=photo_pdf,
                        kind="photo",
                        status=STATUS_REVIEW,
                        output=None,
                        students=len(analysis.photo_rosters[photo_pdf].students),
                        message=str(exc),
                    )
                )
                continue
            items.append(_photo_item(photo_pdf, result))
    else:
        for pdf, result in analysis.references.items():
            for cls in result.classes:
                group = cls.metadata.group_code or pdf.stem
                output = unique_output_path(
                    output_dir,
                    safe_filename_component(group) + "_idoceo",
                )
                issues = [*result.issues, *cls.issues]
                try:
                    write_idoceo_xlsx(
                        cls,
                        output,
                        include_nia=include_nia_for_reference,
                        include_repetix=include_repetix,
                        include_materia=include_materia,
                    )
                except Exception as exc:
                    items.append(
                        SelectionExportItem(
                            source=pdf,
                            kind="reference",
                            status=STATUS_REVIEW,
                            output=None,
                            students=len(cls.students),
                            message=str(exc),
                        )
                    )
                    continue

                status = STATUS_WARNING if issues else STATUS_READY
                message = "; ".join(issues) if issues else "Listado preparado para importar."
                items.append(
                    SelectionExportItem(
                        source=pdf,
                        kind="reference",
                        status=status,
                        output=output,
                        students=len(cls.students),
                        matched_students=len(cls.students) if include_nia_for_reference else 0,
                        message=message,
                    )
                )

    summary_path = output_dir / "RESUMEN_EXPORTACION.txt"
    summary = SelectionExportSummary(
        output_dir=output_dir,
        mode=analysis.mode,
        input_pdfs=len(analysis.pdfs),
        reference_pdfs=len(analysis.references),
        photo_pdfs=len(analysis.photo_rosters),
        unsupported_pdfs=len(analysis.unsupported),
        items=items,
        summary_path=summary_path,
    )
    _write_local_summary(summary)
    return summary


def export_selection(
    inputs: list[Path],
    output_dir: Path,
    *,
    include_nia_for_reference: bool = True,
    include_repetix: bool = False,
    include_materia: bool = False,
) -> SelectionExportSummary:
    analysis = analyze_selection(inputs)
    return export_analyzed_selection(
        analysis,
        output_dir,
        include_nia_for_reference=include_nia_for_reference,
        include_repetix=include_repetix,
        include_materia=include_materia,
    )


def print_selection_export_summary(summary: SelectionExportSummary) -> None:
    """Resumen compartible: sólo contadores y estados, sin rutas ni nombres."""
    print("Exportación conjunta: " + ("CON INCIDENCIAS" if summary.blocking_items else "OK"))
    print(f"PDF seleccionados: {summary.input_pdfs}")
    print(f"PDF de referencia: {summary.reference_pdfs}")
    print(f"Listados actuales con fotos: {summary.photo_pdfs}")
    print(f"PDF no utilizados: {summary.unsupported_pdfs}")
    if summary.mode == "photo":
        print("Modo: los listados actuales con fotos determinan el alumnado final")
    else:
        print("Modo: exportación directa desde referencias tabulares")

    for index, item in enumerate(summary.items, start=1):
        parts = [f"Resultado {index}: {item.status}", f"alumnos={item.students}"]
        if item.kind == "photo":
            parts.extend(
                [
                    f"con_nia={item.matched_students}",
                    f"sin_nia={item.unmatched_students}",
                    f"fotos_nia={item.photos_by_nia}",
                    f"fotos_nombre={item.photos_by_name}",
                    f"sin_foto={item.missing_photos}",
                ]
            )
        print(" | ".join(parts))

    print(f"Resultados listos: {summary.ready_items}")
    print(f"Resultados con aviso: {summary.warning_items}")
    print(f"Resultados bloqueados: {summary.blocking_items}")
    print("Generado: RESUMEN_EXPORTACION.txt")
