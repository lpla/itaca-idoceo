from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .core import (
    ClassResult,
    PageMetadata,
    Student,
    safe_filename_component,
    write_idoceo_xlsx,
)
from .photo_reference_pool import match_photo_result_to_references
from .photo_roster import PhotoRosterResult, detect_photo_roster


@dataclass(frozen=True)
class PhotoExportResult:
    output_dir: Path
    xlsx_path: Path
    photos_dir: Path
    manual_photos_dir: Path | None
    guide_path: Path
    students: int
    matched_students: int
    unmatched_students: int
    photos: int
    missing_photos: int
    match_field: str
    automatic_matches: int
    manual_matches: int


def _unique_directory(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.name}__{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def _photo_base_name(full_name: str) -> str:
    return safe_filename_component(full_name)


def _as_core_class(
    result: PhotoRosterResult,
    reference_by_ordinal: dict[int, Student] | None = None,
) -> ClassResult:
    fallback_name = result.source.stem
    group_raw = result.group_raw or fallback_name
    group_code = result.group_code or group_raw
    reference_by_ordinal = reference_by_ordinal or {}

    students: list[Student] = []
    for student in result.students:
        reference = reference_by_ordinal.get(student.ordinal)
        students.append(
            Student(
                page=student.page,
                block=-1,
                ordinal=student.ordinal,
                nia=reference.nia if reference else "",
                full_name=student.full_name,
                surnames=student.surnames,
                given_names=student.given_names,
                row_x=0.0,
                visual_y=float(student.ordinal),
                repetix=reference.repetix if reference else "",
                materia=reference.materia if reference else "",
            )
        )

    return ClassResult(
        source=result.source,
        metadata=PageMetadata(
            group_raw=group_raw,
            group_code=group_code,
            tutor=result.tutor,
        ),
        students=students,
        issues=[],
    )


def _build_import_guide(
    match_field: str,
    automatic_matches: int,
    manual_matches: int,
    missing_photos: int,
    matched_students: int,
    unmatched_students: int,
) -> str:
    lines = [
        "ITACA → iDoceo | importación de listado con fotos",
        "",
        "1. Importa alumnado_idoceo.xlsx en iDoceo con el asistente de importación.",
        "   Asigna las columnas Apellidos y Nombre a los campos correspondientes.",
    ]

    if match_field == "NIA":
        lines.extend(
            [
                "   Asigna también NIA al campo ID / Student ID.",
                "   Si alguna fila tiene NIA vacío, déjala sin ID: no se ha inventado ninguno.",
                "",
                "2. Abre la clase > Plano de asientos > Herramientas > Fotos > Importación masiva.",
                "   Selecciona ID como criterio del nombre de archivo y elige la carpeta fotos.",
            ]
        )
        if manual_matches:
            lines.extend(
                [
                    "",
                    "3. La carpeta fotos_revision_manual contiene fotografías de alumnos para",
                    "   los que no se ha encontrado un NIA inequívoco. Asígnalas manualmente.",
                ]
            )
    else:
        lines.extend(
            [
                "",
                "2. Abre la clase > Plano de asientos > Herramientas > Fotos > Importación masiva.",
                "   Selecciona Nombre como criterio del nombre de archivo y elige la carpeta fotos.",
                "   El emparejado por nombre puede fallar con normalizaciones de caracteres.",
                "   Para máxima precisión, repite la exportación aportando listados tabulares",
                "   de referencia para cruzar el alumnado y utilizar el NIA como ID.",
            ]
        )

    lines.extend(
        [
            "",
            f"Alumnos enriquecidos desde referencias tabulares: {matched_students}",
            f"Alumnos sin coincidencia inequívoca en las referencias: {unmatched_students}",
            f"Fotos preparadas para coincidencia automática por {match_field}: {automatic_matches}",
            f"Fotos que requieren revisión manual: {manual_matches}",
            f"Alumnos sin fotografía disponible en el PDF: {missing_photos}",
            "",
            "Los alumnos sin fotografía se incluyen igualmente en el XLSX; simplemente",
            "no tienen un archivo correspondiente dentro de las carpetas de fotos.",
            "",
            "Todos estos archivos se han generado localmente en tu equipo.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_student_photo(document, student, destination: Path) -> None:
    try:
        pixmap = pymupdf.Pixmap(document, student.xref)
        image_bytes = pixmap.tobytes("png")
    except Exception as exc:
        raise RuntimeError(
            f"No se ha podido extraer la foto número {student.ordinal}."
        ) from exc
    destination.write_bytes(image_bytes)


def export_photo_roster(
    pdf_path: Path,
    output_dir: Path | None = None,
    *,
    reference_pdfs: list[Path] | None = None,
    reference_pdf: Path | None = None,
    include_repetix: bool = False,
    include_materia: bool = False,
) -> PhotoExportResult:
    """Exporta XLSX + fotos PNG para importar un listado fotográfico en iDoceo.

    El listado con fotos determina siempre qué alumnado pertenece a la clase. Los
    PDF tabulares sólo enriquecen esos alumnos. Una matrícula nueva puede quedar
    sin NIA y seguir exportándose; una coincidencia ambigua, en cambio, detiene la
    exportación para no asignar un identificador incorrecto.
    """
    result = detect_photo_roster(pdf_path)
    if not result.is_valid:
        detail = "; ".join(result.issues) if result.issues else "formato no compatible"
        raise RuntimeError(f"No se puede exportar el listado con fotos: {detail}")

    references = list(reference_pdfs or [])
    if reference_pdf is not None and reference_pdf not in references:
        references.append(reference_pdf)

    reference_by_ordinal: dict[int, Student] = {}
    include_nia = False
    match_field = "Nombre"
    matched_students = 0
    unmatched_students = 0

    if references:
        pool_match = match_photo_result_to_references(result, references)
        if pool_match.usable_files == 0:
            raise RuntimeError(
                "No se ha encontrado ningún PDF tabular válido entre las referencias."
            )
        if pool_match.match.ambiguous_photos:
            raise RuntimeError(
                "No se puede exportar con NIA: quedan coincidencias ambiguas "
                f"({pool_match.match.ambiguous_photos})."
            )
        reference_by_ordinal = pool_match.reference_by_photo_ordinal()
        matched_students = len(reference_by_ordinal)
        unmatched_students = len(result.students) - matched_students
        include_nia = True
        match_field = "NIA"
    elif include_repetix or include_materia:
        raise RuntimeError(
            "REPETIX y MATÈRIA/MÒDUL sólo pueden añadirse al listado con fotos "
            "si se proporciona también al menos un PDF tabular de referencia."
        )

    if output_dir is None:
        base = safe_filename_component(pdf_path.stem) + "_idoceo"
        output_dir = _unique_directory(pdf_path.parent / base)
    elif output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(
            "La carpeta de salida ya existe y no está vacía; elige otra carpeta."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    photos_dir = output_dir / "fotos"
    photos_dir.mkdir(exist_ok=False)
    manual_photos_dir: Path | None = None

    xlsx_path = output_dir / "alumnado_idoceo.xlsx"
    guide_path = output_dir / "IMPORTAR_EN_IDOCEO.txt"

    write_idoceo_xlsx(
        _as_core_class(result, reference_by_ordinal),
        xlsx_path,
        include_nia=include_nia,
        include_repetix=include_repetix,
        include_materia=include_materia,
    )

    photo_students = [student for student in result.students if student.has_photo]
    automatic_matches = 0
    manual_matches = 0
    photo_count = 0

    document = pymupdf.open(pdf_path)
    try:
        if match_field == "NIA":
            automatic_students = []
            manual_students = []
            for student in photo_students:
                reference = reference_by_ordinal.get(student.ordinal)
                if reference is not None and reference.nia.strip():
                    automatic_students.append((student, reference.nia.strip()))
                else:
                    manual_students.append(student)

            nia_counts = Counter(
                safe_filename_component(nia).casefold()
                for _student, nia in automatic_students
            )
            if any(count > 1 for count in nia_counts.values()):
                raise RuntimeError(
                    "Las referencias contienen un NIA duplicado para fotografías distintas."
                )

            for student, nia in automatic_students:
                base = safe_filename_component(nia)
                _write_student_photo(document, student, photos_dir / f"{base}.png")
                automatic_matches += 1
                photo_count += 1

            if manual_students:
                manual_photos_dir = output_dir / "fotos_revision_manual"
                manual_photos_dir.mkdir(exist_ok=False)
                bases = [_photo_base_name(student.full_name) for student in manual_students]
                base_counts = Counter(base.casefold() for base in bases)
                occurrences: Counter[str] = Counter()
                for student, base in zip(manual_students, bases):
                    key = base.casefold()
                    occurrences[key] += 1
                    filename = (
                        f"{base}.png"
                        if base_counts[key] == 1
                        else f"{base}__{occurrences[key]}.png"
                    )
                    _write_student_photo(document, student, manual_photos_dir / filename)
                    manual_matches += 1
                    photo_count += 1
        else:
            bases = [_photo_base_name(student.full_name) for student in photo_students]
            base_counts = Counter(base.casefold() for base in bases)
            occurrences: Counter[str] = Counter()
            for student, base in zip(photo_students, bases):
                key = base.casefold()
                occurrences[key] += 1
                if base_counts[key] > 1:
                    filename = f"{base}__{occurrences[key]}.png"
                    manual_matches += 1
                else:
                    filename = f"{base}.png"
                    automatic_matches += 1
                _write_student_photo(document, student, photos_dir / filename)
                photo_count += 1
    finally:
        document.close()

    missing_photos = len(result.students) - photo_count
    guide_path.write_text(
        _build_import_guide(
            match_field,
            automatic_matches,
            manual_matches,
            missing_photos,
            matched_students,
            unmatched_students,
        ),
        encoding="utf-8",
    )

    return PhotoExportResult(
        output_dir=output_dir,
        xlsx_path=xlsx_path,
        photos_dir=photos_dir,
        manual_photos_dir=manual_photos_dir,
        guide_path=guide_path,
        students=len(result.students),
        matched_students=matched_students,
        unmatched_students=unmatched_students,
        photos=photo_count,
        missing_photos=missing_photos,
        match_field=match_field,
        automatic_matches=automatic_matches,
        manual_matches=manual_matches,
    )


def print_photo_export_result(result: PhotoExportResult) -> None:
    """Resumen seguro para terminal: no muestra nombres ni rutas locales."""
    print("Exportación de listado con fotos: OK")
    print(f"Alumnos: {result.students}")
    if result.match_field == "NIA":
        print(f"Alumnos con NIA cruzado: {result.matched_students}")
        print(f"Alumnos sin NIA en referencias: {result.unmatched_students}")
    print(f"Fotos extraídas: {result.photos}")
    print(f"Sin fotografía en el PDF: {result.missing_photos}")
    print(f"Criterio de importación de fotos: {result.match_field}")
    print(
        f"Coincidencia automática por {result.match_field}: "
        f"{result.automatic_matches}"
    )
    print(f"Revisión manual: {result.manual_matches}")
    print("Generado: alumnado_idoceo.xlsx")
    print("Generado: fotos/")
    if result.manual_photos_dir is not None:
        print("Generado: fotos_revision_manual/")
    print("Generado: IMPORTAR_EN_IDOCEO.txt")


def export_photo_roster_cli(
    pdf_path: Path,
    output_dir: Path | None = None,
    *,
    reference_pdfs: list[Path] | None = None,
    reference_pdf: Path | None = None,
    include_repetix: bool = False,
    include_materia: bool = False,
) -> int:
    try:
        result = export_photo_roster(
            pdf_path,
            output_dir,
            reference_pdfs=reference_pdfs,
            reference_pdf=reference_pdf,
            include_repetix=include_repetix,
            include_materia=include_materia,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print_photo_export_result(result)
    return 0
