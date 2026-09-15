from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .core import ClassResult, PageMetadata, Student, process_pdf
from .photo_match import PhotoRosterReferenceMatch, _group_key, match_photo_result_to_class
from .photo_roster import PhotoRosterResult, detect_photo_roster, print_photo_roster_check


@dataclass
class ReferencePoolMatch:
    photo_result: PhotoRosterResult
    match: PhotoRosterReferenceMatch
    input_files: int
    usable_files: int
    skipped_files: int
    valid_classes: int
    unique_students: int
    same_group_students: int

    @property
    def is_valid(self) -> bool:
        return self.match.is_valid

    @property
    def unresolved_positions(self) -> list[tuple[int, int, int, bool]]:
        matched = {link.photo.ordinal for link in self.match.links}
        return [
            (student.ordinal, student.row, student.column, student.has_photo)
            for student in self.photo_result.students
            if student.ordinal not in matched
        ]

    def reference_by_photo_ordinal(self) -> dict[int, Student]:
        return self.match.reference_by_photo_ordinal()


def _fallback_student_key(student: Student) -> str:
    value = unicodedata.normalize(
        "NFKD",
        f"{student.surnames} {student.given_names}",
    )
    value = "".join(char for char in value if not unicodedata.combining(char))
    return "".join(char.casefold() for char in value if char.isalnum())


def _student_identity(student: Student) -> tuple[str, str]:
    nia = student.nia.strip()
    if nia:
        return "nia", nia
    return "name", _fallback_student_key(student)


def _build_reference_pool(
    photo_result: PhotoRosterResult,
    reference_pdfs: list[Path],
) -> tuple[ClassResult | None, dict[str, int]]:
    photo_group = _group_key(photo_result.group_code)
    candidates: list[tuple[bool, int, Student]] = []
    usable_files = 0
    valid_classes = 0
    same_group_ids: set[tuple[str, str]] = set()
    sequence = 0

    for pdf in reference_pdfs:
        try:
            result = process_pdf(pdf)
        except Exception:
            continue
        if not result.report_signature:
            continue

        file_used = False
        for cls in result.classes:
            if not cls.is_valid:
                continue
            file_used = True
            valid_classes += 1
            same_group = bool(
                photo_group
                and _group_key(cls.metadata.group_code) == photo_group
            )
            for student in cls.students:
                sequence += 1
                candidates.append((same_group, sequence, student))
                if same_group:
                    same_group_ids.add(_student_identity(student))

        if file_used:
            usable_files += 1

    if not candidates:
        return None, {
            "usable_files": usable_files,
            "valid_classes": valid_classes,
            "unique_students": 0,
            "same_group_students": len(same_group_ids),
        }

    # Damos prioridad a la ficha procedente del mismo grupo. Si el mismo NIA
    # aparece en varios PDF, se considera la misma persona y no crea una falsa
    # ambigüedad. Entre duplicados equivalentes preferimos el registro con más
    # campos opcionales disponibles.
    candidates.sort(
        key=lambda item: (
            not item[0],
            -(bool(item[2].repetix) + bool(item[2].materia)),
            item[1],
        )
    )
    unique: dict[tuple[str, str], Student] = {}
    for _same_group, _sequence, student in candidates:
        unique.setdefault(_student_identity(student), student)

    students = list(unique.values())
    pool = ClassResult(
        source=reference_pdfs[0],
        metadata=PageMetadata(
            group_raw=photo_result.group_raw,
            group_code=photo_result.group_code,
            tutor=photo_result.tutor,
        ),
        students=students,
        issues=[],
    )
    return pool, {
        "usable_files": usable_files,
        "valid_classes": valid_classes,
        "unique_students": len(students),
        "same_group_students": len(same_group_ids),
    }


def match_photo_result_to_references(
    photo_result: PhotoRosterResult,
    reference_pdfs: list[Path],
) -> ReferencePoolMatch:
    pool, stats = _build_reference_pool(photo_result, reference_pdfs)
    if pool is None:
        empty = PhotoRosterReferenceMatch(
            photo_result=photo_result,
            reference_class=None,
            links=[],
            unmatched_photos=len(photo_result.students),
            ambiguous_photos=0,
            issues=[
                "No se ha encontrado ningún listado tabular válido entre las referencias"
            ],
        )
        return ReferencePoolMatch(
            photo_result=photo_result,
            match=empty,
            input_files=len(reference_pdfs),
            usable_files=stats["usable_files"],
            skipped_files=len(reference_pdfs) - stats["usable_files"],
            valid_classes=stats["valid_classes"],
            unique_students=stats["unique_students"],
            same_group_students=stats["same_group_students"],
        )

    match = match_photo_result_to_class(photo_result, pool)
    return ReferencePoolMatch(
        photo_result=photo_result,
        match=match,
        input_files=len(reference_pdfs),
        usable_files=stats["usable_files"],
        skipped_files=len(reference_pdfs) - stats["usable_files"],
        valid_classes=stats["valid_classes"],
        unique_students=stats["unique_students"],
        same_group_students=stats["same_group_students"],
    )


def print_reference_pool_match(result: ReferencePoolMatch) -> None:
    match = result.match
    counts: Counter[str] = match.method_counts
    print(
        "Cruce con referencias tabulares: "
        + ("COMPATIBLE" if result.is_valid else "REVISAR")
    )
    print(f"PDF de referencia aportados: {result.input_files}")
    print(f"PDF tabulares válidos usados: {result.usable_files}")
    print(f"PDF omitidos por no ser referencias válidas: {result.skipped_files}")
    print(f"Grupos válidos reunidos: {result.valid_classes}")
    print(f"Alumnos únicos en referencias: {result.unique_students}")
    print(f"Alumnos únicos del mismo grupo: {result.same_group_students}")
    print(f"Alumnos en listado con fotos: {len(result.photo_result.students)}")
    print(f"Emparejados: {match.matched_photos}")
    print(f"Coincidencia exacta: {counts.get('exact', 0)}")
    print(f"Coincidencia tras normalizar signos/espacios: {counts.get('structural', 0)}")
    print(f"Coincidencia tras normalizar diacríticos: {counts.get('folded', 0)}")
    print(f"Coincidencia tras compactar separadores: {counts.get('compact', 0)}")
    print(f"Coincidencia fuzzy segura: {counts.get('fuzzy', 0)}")
    print(f"Sin coincidencia: {match.unmatched_photos}")
    print(f"Coincidencias ambiguas: {match.ambiguous_photos}")

    positions = result.unresolved_positions
    if positions:
        rendered = ", ".join(
            f"#{ordinal} (fila {row}, columna {column}, "
            + ("con foto" if has_photo else "sin foto")
            + ")"
            for ordinal, row, column, has_photo in positions
        )
        print("Pendientes de cruce por posición: " + rendered)

    for issue in match.issues:
        print(f"REVISAR: {issue}")


def check_photo_roster_with_references(
    photo_pdf: Path,
    reference_pdfs: list[Path],
) -> int:
    try:
        photo_result = detect_photo_roster(photo_pdf)
    except Exception as exc:
        print(f"ERROR: no se ha podido analizar el listado con fotos: {exc}")
        return 1

    print_photo_roster_check(photo_result)
    if not photo_result.is_valid:
        return 2

    result = match_photo_result_to_references(photo_result, reference_pdfs)
    print_reference_pool_match(result)
    return 0 if result.is_valid else 2
