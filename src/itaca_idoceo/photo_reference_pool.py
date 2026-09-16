from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from .core import ClassResult, PageMetadata, Student, process_pdf
from .photo_match import (
    FUZZY_ACCEPT_SCORE,
    FUZZY_MARGIN,
    FUZZY_REVIEW_SCORE,
    PhotoRosterReferenceMatch,
    PhotoStudentLink,
    _fuzzy_pair_is_plausible,
    _fuzzy_score,
    _group_key,
    _photo_key,
    _reference_key,
    match_photo_result_to_class,
)
from .photo_roster import PhotoRosterResult, PhotoRosterStudent, detect_photo_roster, print_photo_roster_check


@dataclass(frozen=True)
class UnresolvedDiagnostic:
    ordinal: int
    row: int
    column: int
    has_photo: bool
    best_score: float | None
    surname_score: float | None
    given_score: float | None
    photo_margin: float | None
    reference_margin: float | None
    initials_match: bool | None
    mutual_best: bool | None
    plausible_pair: bool | None
    same_surnames: bool | None
    photo_given_tokens: int | None
    reference_given_tokens: int | None
    given_token_subsequence: bool | None


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

    @property
    def unresolved_diagnostics(self) -> list[UnresolvedDiagnostic]:
        """Diagnóstico anónimo del mejor candidato de cada alumno pendiente.

        No expone nombres, NIA, grupos ni rutas. Sólo usa la posición del alumno
        en la cuadrícula y métricas de similitud para distinguir una ausencia real
        de una diferencia de escritura que haya quedado justo bajo los umbrales.
        """
        reference_class = self.match.reference_class
        if reference_class is None:
            return [
                UnresolvedDiagnostic(
                    ordinal=ordinal,
                    row=row,
                    column=column,
                    has_photo=has_photo,
                    best_score=None,
                    surname_score=None,
                    given_score=None,
                    photo_margin=None,
                    reference_margin=None,
                    initials_match=None,
                    mutual_best=None,
                    plausible_pair=None,
                    same_surnames=None,
                    photo_given_tokens=None,
                    reference_given_tokens=None,
                    given_token_subsequence=None,
                )
                for ordinal, row, column, has_photo in self.unresolved_positions
            ]

        matched_photo_ordinals = {link.photo.ordinal for link in self.match.links}
        matched_reference_ids = {id(link.reference) for link in self.match.links}
        remaining_photos = [
            student
            for student in self.photo_result.students
            if student.ordinal not in matched_photo_ordinals
        ]
        remaining_references = [
            student
            for student in reference_class.students
            if id(student) not in matched_reference_ids
        ]

        if not remaining_references:
            return [
                UnresolvedDiagnostic(
                    ordinal=student.ordinal,
                    row=student.row,
                    column=student.column,
                    has_photo=student.has_photo,
                    best_score=None,
                    surname_score=None,
                    given_score=None,
                    photo_margin=None,
                    reference_margin=None,
                    initials_match=None,
                    mutual_best=None,
                    plausible_pair=None,
                    same_surnames=None,
                    photo_given_tokens=None,
                    reference_given_tokens=None,
                    given_token_subsequence=None,
                )
                for student in remaining_photos
            ]

        scores: dict[tuple[int, int], tuple[float, float, float]] = {}
        for photo_index, photo in enumerate(remaining_photos):
            for reference_index, reference in enumerate(remaining_references):
                scores[(photo_index, reference_index)] = _fuzzy_score(photo, reference)

        diagnostics: list[UnresolvedDiagnostic] = []
        for photo_index, photo in enumerate(remaining_photos):
            ranking = sorted(
                (
                    (scores[(photo_index, reference_index)][0], reference_index)
                    for reference_index in range(len(remaining_references))
                ),
                reverse=True,
            )
            best_score, reference_index = ranking[0]
            score, surname_score, given_score = scores[(photo_index, reference_index)]
            reference = remaining_references[reference_index]

            photo_margin = (
                best_score - ranking[1][0]
                if len(ranking) > 1
                else 1.0
            )
            reference_ranking = sorted(
                (
                    (scores[(other_photo_index, reference_index)][0], other_photo_index)
                    for other_photo_index in range(len(remaining_photos))
                ),
                reverse=True,
            )
            mutual_best = reference_ranking[0][1] == photo_index
            reference_margin = (
                best_score - reference_ranking[1][0]
                if len(reference_ranking) > 1
                else 1.0
            )

            photo_surname, photo_given = _photo_key(photo, "folded")
            ref_surname, ref_given = _reference_key(reference, "folded")
            initials_match = bool(
                photo_surname
                and photo_given
                and ref_surname
                and ref_given
                and photo_surname[0] == ref_surname[0]
                and photo_given[0] == ref_given[0]
            )
            plausible_pair = _fuzzy_pair_is_plausible(
                photo,
                reference,
                score,
                surname_score,
                given_score,
            )
            photo_tokens = _folded_tokens(photo.given_names)
            reference_tokens = _folded_tokens(reference.given_names)

            diagnostics.append(
                UnresolvedDiagnostic(
                    ordinal=photo.ordinal,
                    row=photo.row,
                    column=photo.column,
                    has_photo=photo.has_photo,
                    best_score=best_score,
                    surname_score=surname_score,
                    given_score=given_score,
                    photo_margin=photo_margin,
                    reference_margin=reference_margin,
                    initials_match=initials_match,
                    mutual_best=mutual_best,
                    plausible_pair=plausible_pair,
                    same_surnames=photo_surname == ref_surname,
                    photo_given_tokens=len(photo_tokens),
                    reference_given_tokens=len(reference_tokens),
                    given_token_subsequence=_different_length_subsequence(
                        photo_tokens,
                        reference_tokens,
                    ),
                )
            )

        return diagnostics

    def reference_by_photo_ordinal(self) -> dict[int, Student]:
        return self.match.reference_by_photo_ordinal()


def _folded_tokens(text: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFKD", text)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return tuple(token for token in value.split() if token)


def _is_subsequence(shorter: tuple[str, ...], longer: tuple[str, ...]) -> bool:
    if not shorter or len(shorter) > len(longer):
        return False
    position = 0
    for token in longer:
        if token == shorter[position]:
            position += 1
            if position == len(shorter):
                return True
    return False


def _different_length_subsequence(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> bool:
    if not first or not second or len(first) == len(second):
        return False
    shorter, longer = (first, second) if len(first) < len(second) else (second, first)
    return _is_subsequence(shorter, longer)


def _given_name_token_candidate(
    photo: PhotoRosterStudent,
    reference: Student,
) -> bool:
    photo_surname, _photo_given = _photo_key(photo, "folded")
    reference_surname, _reference_given = _reference_key(reference, "folded")
    if not photo_surname or photo_surname != reference_surname:
        return False

    photo_tokens = _folded_tokens(photo.given_names)
    reference_tokens = _folded_tokens(reference.given_names)
    return _different_length_subsequence(photo_tokens, reference_tokens)


def _rescue_partial_given_names(
    photo_result: PhotoRosterResult,
    match: PhotoRosterReferenceMatch,
) -> PhotoRosterReferenceMatch:
    """Rescata nombres compuestos parciales cuando los apellidos son idénticos.

    Es una etapa deliberadamente más estricta que fuzzy: sólo acepta que uno de
    los nombres de pila sea una subsecuencia de palabras completas del otro,
    exige apellidos idénticos tras normalizar diacríticos/signos y exige una
    relación 1:1 en ambos sentidos entre todo lo que sigue sin emparejar.
    """
    reference_class = match.reference_class
    if reference_class is None:
        return match

    matched_photo_ordinals = {link.photo.ordinal for link in match.links}
    matched_reference_ids = {id(link.reference) for link in match.links}
    remaining_photos = [
        student
        for student in photo_result.students
        if student.ordinal not in matched_photo_ordinals
    ]
    remaining_references = [
        student
        for student in reference_class.students
        if id(student) not in matched_reference_ids
    ]
    if not remaining_photos or not remaining_references:
        return match

    photo_candidates: dict[int, list[int]] = defaultdict(list)
    reference_candidates: dict[int, list[int]] = defaultdict(list)
    for photo_index, photo in enumerate(remaining_photos):
        for reference_index, reference in enumerate(remaining_references):
            if _given_name_token_candidate(photo, reference):
                photo_candidates[photo_index].append(reference_index)
                reference_candidates[reference_index].append(photo_index)

    rescued: list[PhotoStudentLink] = []
    rescued_photo_indexes: set[int] = set()
    for photo_index, candidates in photo_candidates.items():
        if len(candidates) != 1:
            continue
        reference_index = candidates[0]
        if len(reference_candidates[reference_index]) != 1:
            continue
        rescued_photo_indexes.add(photo_index)
        rescued.append(
            PhotoStudentLink(
                photo=remaining_photos[photo_index],
                reference=remaining_references[reference_index],
                method="given_tokens",
            )
        )

    if not rescued:
        return match

    remaining_after = [
        photo
        for index, photo in enumerate(remaining_photos)
        if index not in rescued_photo_indexes
    ]
    rescued_reference_ids = {id(link.reference) for link in rescued}
    references_after = [
        reference
        for reference in remaining_references
        if id(reference) not in rescued_reference_ids
    ]

    ambiguous = 0
    unmatched = 0
    for photo in remaining_after:
        compact_key = _photo_key(photo, "compact")
        compact_candidates = [
            reference
            for reference in references_after
            if _reference_key(reference, "compact") == compact_key
        ]
        if compact_candidates:
            ambiguous += 1
            continue
        if references_after:
            best_score = max(_fuzzy_score(photo, reference)[0] for reference in references_after)
            if best_score >= FUZZY_REVIEW_SCORE:
                ambiguous += 1
                continue
        unmatched += 1

    links = sorted(
        [*match.links, *rescued],
        key=lambda link: link.photo.ordinal,
    )
    issues: list[str] = []
    if unmatched or ambiguous or len(links) != len(photo_result.students):
        issues.append(
            "No se ha podido cruzar todo el alumnado del listado con fotos "
            "de forma inequívoca"
        )

    return PhotoRosterReferenceMatch(
        photo_result=photo_result,
        reference_class=reference_class,
        links=links,
        unmatched_photos=unmatched,
        ambiguous_photos=ambiguous,
        issues=issues,
    )


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
    match = _rescue_partial_given_names(photo_result, match)
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


def _format_optional_score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


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
    print(f"Coincidencia por nombre de pila parcial: {counts.get('given_tokens', 0)}")
    print(f"Coincidencia fuzzy segura: {counts.get('fuzzy', 0)}")
    print(f"Sin coincidencia: {match.unmatched_photos}")
    print(f"Coincidencias ambiguas: {match.ambiguous_photos}")

    diagnostics = result.unresolved_diagnostics
    if diagnostics:
        print("Diagnóstico anónimo de pendientes:")
        for item in diagnostics:
            location = (
                f"#{item.ordinal} (fila {item.row}, columna {item.column}, "
                + ("con foto" if item.has_photo else "sin foto")
                + ")"
            )
            if item.best_score is None:
                print(f"  {location}: sin candidatos libres en las referencias")
                continue

            flags: list[str] = []
            if item.initials_match is False:
                flags.append("iniciales distintas")
            if item.best_score < FUZZY_ACCEPT_SCORE:
                flags.append(f"score<{FUZZY_ACCEPT_SCORE:.2f}")
            if item.photo_margin is not None and item.photo_margin < FUZZY_MARGIN:
                flags.append(f"margen alumno<{FUZZY_MARGIN:.2f}")
            if item.mutual_best is False:
                flags.append("el candidato prefiere otro alumno")
            if item.reference_margin is not None and item.reference_margin < FUZZY_MARGIN:
                flags.append(f"margen referencia<{FUZZY_MARGIN:.2f}")
            if item.plausible_pair is False and not flags:
                flags.append("componentes bajo el umbral seguro")

            reason = ", ".join(flags) if flags else "candidato cercano no aceptado"
            extra = ""
            if item.same_surnames is not None:
                extra = (
                    f" apellidos_iguales={'sí' if item.same_surnames else 'no'}"
                    f" tokens_nombre={item.photo_given_tokens}/{item.reference_given_tokens}"
                    f" subsecuencia={'sí' if item.given_token_subsequence else 'no'}"
                )
            print(
                f"  {location}: score={_format_optional_score(item.best_score)} "
                f"apellidos={_format_optional_score(item.surname_score)} "
                f"nombre={_format_optional_score(item.given_score)} "
                f"margen_alumno={_format_optional_score(item.photo_margin)} "
                f"margen_referencia={_format_optional_score(item.reference_margin)}"
                f"{extra} -> {reason}"
            )

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
