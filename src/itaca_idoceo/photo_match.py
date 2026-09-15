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


FUZZY_ACCEPT_SCORE = 0.90
FUZZY_REVIEW_SCORE = 0.84
FUZZY_MARGIN = 0.08
FUZZY_COMPONENT_MIN = 0.82


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


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if len(left) > len(right):
        left, right = right, left

    previous = list(range(len(left) + 1))
    for row_index, right_char in enumerate(right, start=1):
        current = [row_index]
        for column_index, left_char in enumerate(left, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column_index] + 1,
                    previous[column_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    longest = max(len(left), len(right))
    if longest == 0:
        return 1.0
    return 1.0 - (_levenshtein_distance(left, right) / longest)


def _fuzzy_score(
    photo: PhotoRosterStudent,
    reference: Student,
) -> tuple[float, float, float]:
    photo_surname, photo_given = _photo_key(photo, "folded")
    ref_surname, ref_given = _reference_key(reference, "folded")

    surname_score = _similarity(photo_surname, ref_surname)
    given_score = _similarity(photo_given, ref_given)
    full_score = _similarity(
        f"{photo_surname} {photo_given}",
        f"{ref_surname} {ref_given}",
    )
    score = 0.55 * surname_score + 0.35 * given_score + 0.10 * full_score
    return score, surname_score, given_score


def _fuzzy_pair_is_plausible(
    photo: PhotoRosterStudent,
    reference: Student,
    score: float,
    surname_score: float,
    given_score: float,
) -> bool:
    photo_surname, photo_given = _photo_key(photo, "folded")
    ref_surname, ref_given = _reference_key(reference, "folded")

    if not photo_surname or not photo_given or not ref_surname or not ref_given:
        return False
    if photo_surname[0] != ref_surname[0] or photo_given[0] != ref_given[0]:
        return False
    if score < FUZZY_ACCEPT_SCORE:
        return False

    one_component_exact = surname_score == 1.0 or given_score == 1.0
    if one_component_exact:
        return min(surname_score, given_score) >= FUZZY_COMPONENT_MIN

    return surname_score >= 0.90 and given_score >= 0.90


def _fuzzy_match_remaining(
    photo_students: list[PhotoRosterStudent],
    reference_students: list[Student],
    remaining_photo: set[int],
    remaining_reference: set[int],
) -> tuple[list[tuple[int, int]], set[int]]:
    """Devuelve parejas fuzzy seguras y fotos con candidatos cercanos ambiguos.

    Sólo se evalúan alumnos que han sobrevivido a todas las etapas deterministas.
    Una pareja se acepta si supera el umbral, es la mejor opción de ambos lados
    y queda separada del segundo candidato por un margen suficiente.
    """
    if not remaining_photo or not remaining_reference:
        return [], set()

    scores: dict[tuple[int, int], tuple[float, float, float]] = {}
    for photo_index in remaining_photo:
        for reference_index in remaining_reference:
            scores[(photo_index, reference_index)] = _fuzzy_score(
                photo_students[photo_index],
                reference_students[reference_index],
            )

    photo_ranked: dict[int, list[tuple[float, int]]] = {}
    for photo_index in remaining_photo:
        ranking = sorted(
            (
                (scores[(photo_index, reference_index)][0], reference_index)
                for reference_index in remaining_reference
            ),
            reverse=True,
        )
        photo_ranked[photo_index] = ranking

    reference_ranked: dict[int, list[tuple[float, int]]] = {}
    for reference_index in remaining_reference:
        ranking = sorted(
            (
                (scores[(photo_index, reference_index)][0], photo_index)
                for photo_index in remaining_photo
            ),
            reverse=True,
        )
        reference_ranked[reference_index] = ranking

    accepted: list[tuple[int, int]] = []
    ambiguous_photo_indexes: set[int] = set()

    for photo_index, ranking in photo_ranked.items():
        best_score, reference_index = ranking[0]
        score, surname_score, given_score = scores[(photo_index, reference_index)]

        if best_score >= FUZZY_REVIEW_SCORE:
            ambiguous_photo_indexes.add(photo_index)

        ref_ranking = reference_ranked[reference_index]
        if ref_ranking[0][1] != photo_index:
            continue

        photo_margin = (
            best_score - ranking[1][0]
            if len(ranking) > 1
            else 1.0
        )
        reference_margin = (
            best_score - ref_ranking[1][0]
            if len(ref_ranking) > 1
            else 1.0
        )

        if photo_margin < FUZZY_MARGIN or reference_margin < FUZZY_MARGIN:
            continue
        if not _fuzzy_pair_is_plausible(
            photo_students[photo_index],
            reference_students[reference_index],
            score,
            surname_score,
            given_score,
        ):
            continue

        accepted.append((photo_index, reference_index))
        ambiguous_photo_indexes.discard(photo_index)

    return accepted, ambiguous_photo_indexes


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

    fuzzy_pairs, fuzzy_ambiguous = _fuzzy_match_remaining(
        photo_students,
        reference_students,
        remaining_photo,
        remaining_reference,
    )
    for photo_index, reference_index in fuzzy_pairs:
        matched[photo_index] = (reference_index, "fuzzy")
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
        if candidates or index in fuzzy_ambiguous:
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
    print(f"Coincidencia fuzzy segura: {counts.get('fuzzy', 0)}")
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
