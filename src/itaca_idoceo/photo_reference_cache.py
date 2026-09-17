from __future__ import annotations

from .core import ClassResult, PageMetadata, PdfResult, Student
from .photo_match import _group_key, match_photo_result_to_class
from .photo_reference_pool import (
    ReferencePoolMatch,
    _rescue_partial_given_names,
    _student_identity,
)
from .photo_roster import PhotoRosterResult


def match_photo_result_to_parsed_references(
    photo_result: PhotoRosterResult,
    reference_results: list[PdfResult],
) -> ReferencePoolMatch:
    """Cruza un listado con fotos reutilizando referencias ya parseadas.

    El algoritmo de identidad es el mismo que en ``photo_reference_pool``; la
    diferencia es que no vuelve a abrir ni parsear cada PDF para cada materia.
    Esto permite analizar una carpeta de referencias una sola vez y reutilizarla
    para todos los listados actuales del profesor.
    """
    photo_group = _group_key(photo_result.group_code)
    candidates: list[tuple[bool, int, Student]] = []
    usable_files = 0
    valid_classes = 0
    same_group_ids: set[tuple[str, str]] = set()
    sequence = 0

    for result in reference_results:
        if not result.report_signature:
            continue
        file_used = False
        for cls in result.classes:
            if not cls.is_valid:
                continue
            file_used = True
            valid_classes += 1
            same_group = bool(
                photo_group and _group_key(cls.metadata.group_code) == photo_group
            )
            for student in cls.students:
                sequence += 1
                candidates.append((same_group, sequence, student))
                if same_group:
                    same_group_ids.add(_student_identity(student))
        if file_used:
            usable_files += 1

    if not candidates:
        from .photo_match import PhotoRosterReferenceMatch

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
            input_files=len(reference_results),
            usable_files=usable_files,
            skipped_files=len(reference_results) - usable_files,
            valid_classes=valid_classes,
            unique_students=0,
            same_group_students=len(same_group_ids),
        )

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
    source = reference_results[0].source
    pool = ClassResult(
        source=source,
        metadata=PageMetadata(
            group_raw=photo_result.group_raw,
            group_code=photo_result.group_code,
            tutor=photo_result.tutor,
        ),
        students=students,
        issues=[],
    )
    match = match_photo_result_to_class(photo_result, pool)
    match = _rescue_partial_given_names(photo_result, match)
    return ReferencePoolMatch(
        photo_result=photo_result,
        match=match,
        input_files=len(reference_results),
        usable_files=usable_files,
        skipped_files=len(reference_results) - usable_files,
        valid_classes=valid_classes,
        unique_students=len(students),
        same_group_students=len(same_group_ids),
    )
