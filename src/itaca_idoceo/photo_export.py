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
from .photo_roster import PhotoRosterResult, detect_photo_roster


@dataclass(frozen=True)
class PhotoExportResult:
    output_dir: Path
    xlsx_path: Path
    photos_dir: Path
    guide_path: Path
    students: int
    photos: int
    missing_photos: int
    automatic_name_matches: int
    manual_name_matches: int


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


def _as_core_class(result: PhotoRosterResult) -> ClassResult:
    fallback_name = result.source.stem
    group_raw = result.group_raw or fallback_name
    group_code = result.group_code or group_raw
    students = [
        Student(
            page=student.page,
            block=-1,
            ordinal=student.ordinal,
            nia="",
            full_name=student.full_name,
            surnames=student.surnames,
            given_names=student.given_names,
            row_x=0.0,
            visual_y=float(student.ordinal),
        )
        for student in result.students
    ]
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
    automatic_name_matches: int,
    manual_name_matches: int,
    missing_photos: int,
) -> str:
    lines = [
        "ITACA → iDoceo | importación de listado con fotos",
        "",
        "1. Importa alumnado_idoceo.xlsx en iDoceo con el asistente de importación.",
        "   Asigna las columnas Apellidos y Nombre a los campos correspondientes.",
        "",
        "2. Abre la clase > Plano de asientos > Herramientas > Fotos > Importación masiva.",
        "   Selecciona Nombre como criterio del nombre de archivo y elige la carpeta fotos.",
        "",
        f"Fotos preparadas para coincidencia automática por nombre: {automatic_name_matches}",
        f"Fotos que requieren revisión manual por nombre duplicado: {manual_name_matches}",
        f"Alumnos sin fotografía disponible en el PDF: {missing_photos}",
        "",
        "Los alumnos sin fotografía se incluyen igualmente en el XLSX; simplemente",
        "no tienen un archivo correspondiente dentro de la carpeta fotos.",
        "",
        "Si alguna foto no se asigna automáticamente, iDoceo la deja disponible",
        "para asignarla manualmente desde el propio plano de asientos.",
        "",
        "Todos estos archivos se han generado localmente en tu equipo.",
    ]
    return "\n".join(lines) + "\n"


def export_photo_roster(
    pdf_path: Path,
    output_dir: Path | None = None,
) -> PhotoExportResult:
    """Exporta XLSX + fotos PNG para importar un listado fotográfico en iDoceo."""
    result = detect_photo_roster(pdf_path)
    if not result.is_valid:
        detail = "; ".join(result.issues) if result.issues else "formato no compatible"
        raise RuntimeError(f"No se puede exportar el listado con fotos: {detail}")

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

    xlsx_path = output_dir / "alumnado_idoceo.xlsx"
    guide_path = output_dir / "IMPORTAR_EN_IDOCEO.txt"

    write_idoceo_xlsx(_as_core_class(result), xlsx_path)

    photo_students = [student for student in result.students if student.has_photo]
    bases = [_photo_base_name(student.full_name) for student in photo_students]
    base_counts = Counter(base.casefold() for base in bases)
    occurrences: Counter[str] = Counter()
    automatic_name_matches = 0
    manual_name_matches = 0
    photo_count = 0

    document = pymupdf.open(pdf_path)
    try:
        for student, base in zip(photo_students, bases):
            key = base.casefold()
            occurrences[key] += 1

            if base_counts[key] > 1:
                filename = f"{base}__{occurrences[key]}.png"
                manual_name_matches += 1
            else:
                filename = f"{base}.png"
                automatic_name_matches += 1

            try:
                pixmap = pymupdf.Pixmap(document, student.xref)
                image_bytes = pixmap.tobytes("png")
            except Exception as exc:
                raise RuntimeError(
                    f"No se ha podido extraer la foto número {student.ordinal}."
                ) from exc

            (photos_dir / filename).write_bytes(image_bytes)
            photo_count += 1
    finally:
        document.close()

    missing_photos = len(result.students) - photo_count
    guide_path.write_text(
        _build_import_guide(
            automatic_name_matches,
            manual_name_matches,
            missing_photos,
        ),
        encoding="utf-8",
    )

    return PhotoExportResult(
        output_dir=output_dir,
        xlsx_path=xlsx_path,
        photos_dir=photos_dir,
        guide_path=guide_path,
        students=len(result.students),
        photos=photo_count,
        missing_photos=missing_photos,
        automatic_name_matches=automatic_name_matches,
        manual_name_matches=manual_name_matches,
    )


def print_photo_export_result(result: PhotoExportResult) -> None:
    """Resumen seguro para terminal: no muestra nombres ni rutas locales."""
    print("Exportación de listado con fotos: OK")
    print(f"Alumnos: {result.students}")
    print(f"Fotos extraídas: {result.photos}")
    print(f"Sin fotografía en el PDF: {result.missing_photos}")
    print(
        "Coincidencia automática por nombre: "
        f"{result.automatic_name_matches}"
    )
    print(
        "Revisión manual por nombres duplicados: "
        f"{result.manual_name_matches}"
    )
    print("Generado: alumnado_idoceo.xlsx")
    print("Generado: fotos/")
    print("Generado: IMPORTAR_EN_IDOCEO.txt")


def export_photo_roster_cli(
    pdf_path: Path,
    output_dir: Path | None = None,
) -> int:
    try:
        result = export_photo_roster(pdf_path, output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print_photo_export_result(result)
    return 0
