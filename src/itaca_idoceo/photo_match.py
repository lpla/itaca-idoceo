from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from .core import ClassResult, PdfResult, Student, clean_spaces, process_pdf
from .photo_roster import (
    PhotoRosterResult,
    PhotoRosterStudent,
    detect_photo_roster,
    print_photo_roster_check,
)


@dataclass(frozen=True)
class PhotoStudentLink:
    photo: PhotoRosterStudent
    reference: Student
    method: str


@dataclass
class PhotoRosterReferenceMatch:
    photo_result: PhotoRosterResult
    reference_class: ClassResult | None
    links: list[PhotoStudentLink]
    unmatched_photos: int
    ambiguous_photos: int
    issues: list[str]

    @property
    def matched_photos(self) -> int:
        return len(self.links)

    @property
    def reference_students(self) -> int:
        return len(self.reference_class.students) if self.reference_class else 0

    @property
    def is_valid(self) -> bool:
        return (
            self.photo_result.is_valid
            and not self.issues
            and self.matched_photos == len(self.photo_result.students)
            and self.unmatched_photos == 0
            and self.ambiguous_photos == 0
        )

    @property
    def method_counts(self) -> Counter[str]:
        return Counter(link.method for link in self.links)

    def reference_by_photo_ordinal(self) -> dict[int, Student]:
        return {link.photo.ordinal: link.reference for link in self.links}


def _basic_part(text: str) -> str:
    value = unicodedata.normalize("NFKC", clean_spaces(text)).casefold()
    return clean_spaces(value)


def _token_part(
    text: str,
    *,
    strip_diacritics: bool,
    compact: bool,
) -> str:
    value = unicodedata.normalize("NFKD" if strip_diacritics else "NFKC", text)
    if strip_diacritics:
        value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold()

    pieces: list[str] = []
    for char in value:
        if char.isalnum():
            pieces.append(char)
        elif not compact:
            pieces.append(" ")

    normalized = re.sub(r"\s+", " ", "".join(pieces)).strip()
    return normalized


def _name_key(
    surnames: str,
    given_names: str,
    method: str,
) -> tuple[str, str]:
    if method == "exact":
        return _basic_part(surnames), _basic_part(given_names)
    if method == "structural":
        return (
            _token_part(surnames, strip_diacritics=False, compact=False),
            _token_part(given_names, strip_diacritics=False, compact=False),
        )
    if method == "folded":
        return (
            _token_part(surnames, strip_diacritics=True, compact=False),
            _token_part(given_names, strip_diacritics=True, compact=False),
        )
    if method == "compact":
        return (
            _token_part(surnames, strip_diacritics=True, compact=True),
            _token_part(given_names, strip_diacritics=True, compact=True),
        )
    raise ValueError(f"Método de normalización desconocido: {method}")


def _photo_key(student: PhotoRosterStudent, method: str) -> tuple[str, str]:
    return _name_key(student.surnames, student.given_names, method)


def _reference_key(student: Student, method: str) -> tuple[str, str]:
    return _name_key(student.surnames, student.given_names, method)


def _group_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold()
    return "".join(char for char in normalized if char.isalnum())


def _select_reference_class(
    photo_result: PhotoRosterResult,
    reference_result: PdfResult,
) -> tuple[ClassResult | None, list[str]]:
    if reference_result.issues:
        return None, [
            "El PDF tabular de referencia no ha pasado la validación del formato soportado"
        ]

    valid_classes = [cls for cls in reference_result.classes if cls.is_valid]
    if not valid_classes:
        return None, [
            "El PDF tabular de referencia no contiene ningún grupo válido para cruzar"
        ]

    photo_group = _group_key(photo_result.group_code)
    if photo_group:
        same_group = [
            cls
            for cls in valid_classes
            if _group_key(cls.metadata.group_code) == photo_group
        ]
        if len(same_group) == 1:
            return same_group[0], []
        if len(same_group) > 1:
            return None, [
                "El PDF tabular contiene más de un grupo compatible con el listado con fotos"
            ]

        if len(valid_classes) == 1 and not _group_key(valid_classes[0].metadata.group_code):
            return valid_classes[0], []

        return None, [
            "El grupo del listado con fotos no coincide con ningún grupo válido del PDF tabular"
        ]

    if len(valid_classes) == 1:
        return valid_classes[0], []

    return None, [
        "No se puede elegir de forma inequívoca un grupo del PDF tabular de referencia"
    ]


def _match_students(
    photo_students: list[PhotoRosterStudent],
    reference_students: list[Student],
) -> tuple[list[PhotoStudentLink], int, int]:
    remaining_photo = set(range(len(photo_students)))
    remaining_reference = set(range(len(reference_students)))
    matched: dict[int, tuple[int, str]] = {}

    for method in ("exact", "structural", "folded", "compact"):
        photo_by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
        reference_by_key: dict[tuple[str, str], list[int]] = defaultdict(list)

        for index in remaining_photo:
            photo_by_key[_photo_key(photo_students[index], method)].append(index)
        for index in remaining_reference:
            reference_by_key[_reference_key(reference_students[index], method)].append(index)

        accepted: list[tuple[int, int]] = []
        for key, photo_indexes in photo_by_key.items():
            reference_indexes = reference_by_key.get(key, [])
            if len(photo_indexes) == 1 and len(reference_indexes) == 1:
                accepted.append((photo_indexes[0], reference_indexes[0]))

        for photo_index, reference_index in accepted:
            matched[photo_index] = (reference_index, method)
            remaining_photo.discard(photo_index)
            remaining_reference.discard(reference_index)

    ambiguous = 0
    unmatched = 0
    remaining_reference_by_compact: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index in remaining_reference:
        remaining_reference_by_compact[
            _reference_key(reference_students[index], "compact")
        ].append(index)

    for index in remaining_photo:
        candidates = remaining_reference_by_compact.get(
            _photo_key(photo_students[index], "compact"),
            [],
        )
        if candidates:
            ambiguous += 1
        else:
            unmatched += 1

    links = [
        PhotoStudentLink(
            photo=photo_students[photo_index],
            reference=reference_students[reference_index],
            method=method,
        )
        for photo_index, (reference_index, method) in sorted(matched.items())
    ]
    return links, unmatched, ambiguous


def match_photo_result_to_class(
    photo_result: PhotoRosterResult,
    reference_class: ClassResult,
) -> PhotoRosterReferenceMatch:
    if not photo_result.is_valid:
        return PhotoRosterReferenceMatch(
            photo_result=photo_result,
            reference_class=reference_class,
            links=[],
            unmatched_photos=len(photo_result.students),
            ambiguous_photos=0,
            issues=["El listado con fotos contiene incidencias y no se puede cruzar"],
        )

    if not reference_class.is_valid:
        return PhotoRosterReferenceMatch(
            photo_result=photo_result,
            reference_class=reference_class,
            links=[],
            unmatched_photos=len(photo_result.students),
            ambiguous_photos=0,
            issues=["El grupo del PDF tabular de referencia contiene incidencias"],
        )

    links, unmatched, ambiguous = _match_students(
        photo_result.students,
        reference_class.students,
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


def match_photo_result_to_reference(
    photo_result: PhotoRosterResult,
    reference_pdf: Path,
) -> PhotoRosterReferenceMatch:
    reference_result = process_pdf(reference_pdf)
    reference_class, selection_issues = _select_reference_class(
        photo_result,
        reference_result,
    )
    if reference_class is None:
        return PhotoRosterReferenceMatch(
            photo_result=photo_result,
            reference_class=None,
            links=[],
            unmatched_photos=len(photo_result.students),
            ambiguous_photos=0,
            issues=selection_issues,
        )

    result = match_photo_result_to_class(photo_result, reference_class)
    if selection_issues:
        result.issues[:0] = selection_issues
    return result


def print_reference_match(result: PhotoRosterReferenceMatch) -> None:
    counts = result.method_counts
    print(
        "Cruce con listado tabular: "
        + ("COMPATIBLE" if result.is_valid else "REVISAR")
    )
    print(f"Alumnos en listado con fotos: {len(result.photo_result.students)}")
    print(f"Alumnos en grupo de referencia: {result.reference_students}")
    print(f"Emparejados: {result.matched_photos}")
    print(f"Coincidencia exacta: {counts.get('exact', 0)}")
    print(f"Coincidencia tras normalizar signos/espacios: {counts.get('structural', 0)}")
    print(f"Coincidencia tras normalizar diacríticos: {counts.get('folded', 0)}")
    print(f"Coincidencia tras compactar separadores: {counts.get('compact', 0)}")
    print(f"Sin coincidencia: {result.unmatched_photos}")
    print(f"Coincidencias ambiguas: {result.ambiguous_photos}")
    for issue in result.issues:
        print(f"REVISAR: {issue}")


def check_photo_roster_with_reference(
    photo_pdf: Path,
    reference_pdf: Path,
) -> int:
    try:
        photo_result = detect_photo_roster(photo_pdf)
    except Exception as exc:
        print(f"ERROR: no se ha podido analizar el listado con fotos: {exc}")
        return 1

    print_photo_roster_check(photo_result)
    if not photo_result.is_valid:
        return 2

    try:
        match_result = match_photo_result_to_reference(photo_result, reference_pdf)
    except Exception as exc:
        print(f"ERROR: no se ha podido analizar el PDF tabular de referencia: {exc}")
        return 1

    print_reference_match(match_result)
    return 0 if match_result.is_valid else 2
