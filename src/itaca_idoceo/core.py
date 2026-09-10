#!/usr/bin/env python3
"""Núcleo de conversión local ITACA → iDoceo."""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf


SCRIPT_VERSION = "0.6.0a8"


# ===========================================================================
# Modelos
# ===========================================================================

@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block: int
    line: int
    number: int


@dataclass
class VisualWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class TextLine:
    block: int
    line: int
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(
            word.text for word in sorted(self.words, key=lambda word: word.number)
        )

    @property
    def x0(self) -> float:
        return min(word.x0 for word in self.words)

    @property
    def y0(self) -> float:
        return min(word.y0 for word in self.words)


@dataclass
class Student:
    page: int
    block: int
    ordinal: int
    nia: str
    full_name: str
    surnames: str
    given_names: str
    row_x: float
    visual_y: float


@dataclass
class PageMetadata:
    group_raw: str | None = None
    group_code: str | None = None
    course: str | None = None
    tutor: str | None = None


@dataclass
class GroupAnchor:
    page: int
    y: float
    group_raw: str | None
    group_code: str | None
    tutor: str | None


@dataclass
class CourseAnchor:
    page: int
    y: float
    value: str
    decorated: bool = False


@dataclass
class AssignedStudent:
    student: Student
    group_raw: str | None
    group_code: str | None
    course: str | None
    tutor: str | None
    # Identifica la ocurrencia concreta de la cabecera CURS que estaba
    # activa cuando se leyó la fila. Sirve para distinguir subsecciones
    # dentro del mismo GRUP (p. ej. Bachillerato) sin convertirlas en
    # clases independientes para iDoceo.
    course_section: int | None = None


@dataclass
class ClassResult:
    """Una clase/grupo detectado, aunque comparta PDF con otros grupos."""

    source: Path
    metadata: PageMetadata
    students: list[Student]
    issues: list[str]
    # Valores CURS distintos observados dentro del grupo, en orden.
    # Son metadatos locales; no se exportan al XLSX.
    course_values: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues


@dataclass
class PdfResult:
    source: Path
    classes: list[ClassResult]
    page_count: int
    issues: list[str]
    report_signature: bool = False
    signature_pages: tuple[int, ...] = ()

    @property
    def students(self) -> list[Student]:
        return [student for cls in self.classes for student in cls.students]

    @property
    def metadata(self) -> PageMetadata:
        # Compatibilidad útil para código externo que trataba un PDF como una clase.
        if len(self.classes) == 1:
            return self.classes[0].metadata
        return PageMetadata()

    @property
    def is_valid(self) -> bool:
        return not self.issues and all(cls.is_valid for cls in self.classes)


# ===========================================================================
# Texto
# ===========================================================================

def clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_numeric(text: str) -> bool:
    return text.strip().isdigit()


def is_name_component(text: str) -> bool:
    if not text:
        return False
    return all(char.isalpha() or char in "-'’" for char in text)


def parse_person_name(line: TextLine) -> tuple[str, str, str] | None:
    """Reconoce ``APELLIDOS, NOMBRE`` sin limitar palabras a ambos lados."""
    tokens = [
        word.text.strip()
        for word in sorted(line.words, key=lambda word: word.number)
        if word.text.strip()
    ]

    if len(tokens) < 2:
        return None

    comma_positions = [index for index, token in enumerate(tokens) if "," in token]
    if len(comma_positions) != 1:
        return None

    comma_index = comma_positions[0]
    comma_token = tokens[comma_index]

    if not comma_token.endswith(",") or comma_token.count(",") != 1:
        return None
    if comma_index == len(tokens) - 1:
        return None

    surname_tokens = tokens[: comma_index + 1]
    given_name_tokens = tokens[comma_index + 1 :]

    if any("," in token for token in surname_tokens[:-1]):
        return None

    last_surname = surname_tokens[-1][:-1]
    if not last_surname:
        return None

    surname_components = surname_tokens[:-1] + [last_surname]
    if not all(is_name_component(token) for token in surname_components):
        return None
    if not all(is_name_component(token) for token in given_name_tokens):
        return None

    surnames = " ".join(surname_components)
    given_names = " ".join(given_name_tokens)
    return f"{surnames}, {given_names}", surnames, given_names


def label_key(text: str) -> str:
    return "".join(char for char in text.upper() if char.isalpha())


def canonical_group_code(group_raw: str | None) -> str | None:
    if not group_raw:
        return None

    value = clean_spaces(group_raw)
    parts = re.split(r"\s+-\s+", value, maxsplit=1)
    if len(parts) == 2 and parts[0].strip():
        return parts[0].strip()
    return value


def normalize_course(text: str) -> str:
    """Normalización sólo para comparar cursos genéricos/específicos."""
    value = unicodedata.normalize("NFKD", text)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return clean_spaces(value)


def courses_compatible(first: str, second: str) -> bool:
    """
    Considera compatibles una etiqueta general y otra que la especializa.

    Ej.: ``PRIMER BATX`` y ``PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS``.
    """
    a = normalize_course(first)
    b = normalize_course(second)
    if not a or not b:
        return True
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def resolve_course_values(values: list[str]) -> tuple[str | None, bool]:
    """Devuelve el curso más específico y si todos los valores son compatibles."""
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_course(value)
        if key and key not in seen:
            seen.add(key)
            unique.append(clean_spaces(value))

    if not unique:
        return None, True

    compatible = all(
        courses_compatible(first, second)
        for i, first in enumerate(unique)
        for second in unique[i + 1 :]
    )

    # La variante más larga suele ser la modalidad/especialización de BATX.
    selected = max(unique, key=lambda value: len(normalize_course(value)))
    return selected, compatible


# ===========================================================================
# Alumnado
# ===========================================================================

def extract_lines(page) -> dict[int, list[TextLine]]:
    grouped = defaultdict(lambda: defaultdict(list))

    for item in page.get_text("words", sort=False):
        x0, y0, x1, y1, text, block, line, word_no = item[:8]
        grouped[block][line].append(
            Word(text, x0, y0, x1, y1, block, line, word_no)
        )

    return {
        block: [
            TextLine(block=block, line=line, words=words)
            for line, words in block_lines.items()
        ]
        for block, block_lines in grouped.items()
    }


def raw_page_height(page) -> float:
    return page.cropbox.height


def find_numeric_line(
    lines: list[TextLine],
    min_fraction: float,
    max_fraction: float,
    height: float,
) -> TextLine | None:
    candidates = []
    for line in lines:
        if len(line.words) != 1 or not is_numeric(line.text):
            continue
        fraction = line.y0 / height
        if min_fraction <= fraction <= max_fraction:
            candidates.append(line)
    return max(candidates, key=lambda line: line.y0) if candidates else None


def find_name_line(
    lines: list[TextLine],
    height: float,
) -> tuple[TextLine, str, str, str] | None:
    candidates = []
    for line in lines:
        fraction = line.y0 / height
        if not 0.45 <= fraction <= 0.80:
            continue
        parsed = parse_person_name(line)
        if parsed is not None:
            full_name, surnames, given_names = parsed
            candidates.append((line, full_name, surnames, given_names))

    return max(candidates, key=lambda item: item[0].y0) if candidates else None


def get_visual_y(page, row_x: float) -> float:
    rotation = page.rotation % 360
    if rotation == 90:
        return row_x
    if rotation == 270:
        return page.cropbox.width - row_x
    return row_x


def detect_students(page, page_number: int) -> list[Student]:
    height = raw_page_height(page)
    blocks = extract_lines(page)
    students: list[Student] = []

    for block, lines in blocks.items():
        ordinal_line = find_numeric_line(lines, 0.92, 0.99, height)
        nia_line = find_numeric_line(lines, 0.84, 0.92, height)
        name_result = find_name_line(lines, height)

        if ordinal_line is None or nia_line is None or name_result is None:
            continue

        name_line, full_name, surnames, given_names = name_result
        try:
            ordinal = int(ordinal_line.text)
        except ValueError:
            continue

        row_x = name_line.x0
        students.append(
            Student(
                page=page_number,
                block=block,
                ordinal=ordinal,
                nia=nia_line.text.strip(),
                full_name=full_name,
                surnames=surnames,
                given_names=given_names,
                row_x=row_x,
                visual_y=get_visual_y(page, row_x),
            )
        )

    students.sort(key=lambda student: student.visual_y)
    return students


# ===========================================================================
# Metadatos visuales: todas las ocurrencias, no una sola por página
# ===========================================================================

def extract_visual_words(page) -> list[VisualWord]:
    result = []
    for item in page.get_text("words", sort=False):
        x0, y0, x1, y1, text = item[:5]
        rect = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
        result.append(VisualWord(text, rect.x0, rect.y0, rect.x1, rect.y1))
    return result


def same_visual_row(
    first: VisualWord,
    second: VisualWord,
    tolerance: float = 7.0,
) -> bool:
    dynamic = max(
        tolerance,
        min(max(first.height, second.height), 14.0) * 0.75,
    )
    return abs(first.cy - second.cy) <= dynamic


REPORT_SIGNATURE_HEADERS = (
    "ORDE",
    "NIA",
    "REPETIX",
    "COGNOMS I NOM",
    "MATÈRIA",
)


def normalize_header_token(text: str) -> str:
    """Normaliza un token de cabecera para compararlo sin acentos/puntuación."""
    value = unicodedata.normalize("NFKD", text)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return "".join(char for char in value.upper() if char.isalnum())


def has_itaca3_report_signature(words: list[VisualWord]) -> bool:
    """Detecta la fila de cinco cabeceras del listado soportado de ITACA 3."""
    for orde in words:
        if normalize_header_token(orde.text) != "ORDE":
            continue

        row = [
            word
            for word in words
            if same_visual_row(word, orde, tolerance=9.0)
        ]
        row.sort(key=lambda word: word.x0)
        tokens = [normalize_header_token(word.text) for word in row]
        token_set = set(tokens)
        compact = "".join(tokens)

        if not {"ORDE", "NIA", "REPETIX", "MATERIA"}.issubset(token_set):
            continue
        if "COGNOMSINOM" not in compact:
            continue
        return True

    return False


def detect_itaca3_report_signature(document) -> tuple[bool, tuple[int, ...]]:
    """Devuelve si el PDF presenta la firma conocida y en qué páginas aparece."""
    pages: list[int] = []
    for page_number, page in enumerate(document, start=1):
        if has_itaca3_report_signature(extract_visual_words(page)):
            pages.append(page_number)
    return bool(pages), tuple(pages)


def find_label_words(words: list[VisualWord], label: str) -> list[VisualWord]:
    target = label.upper()
    return [word for word in words if label_key(word.text) == target]


def clean_header_value_tokens(tokens: list[str]) -> str | None:
    cleaned = []
    for token in tokens:
        token = token.strip()
        if not token or token in {":", "***"}:
            continue
        token = token.lstrip(":").strip()
        if token:
            cleaned.append(token)
    value = clean_spaces(" ".join(cleaned))
    return value or None


def find_group_tutor_pairs(
    words: list[VisualWord],
) -> list[tuple[VisualWord, VisualWord]]:
    """Localiza todas las parejas visuales GRUP ... TUTOR de una página."""
    group_labels = find_label_words(words, "GRUP")
    tutor_labels = find_label_words(words, "TUTOR")
    result: list[tuple[VisualWord, VisualWord]] = []

    for group_label in group_labels:
        compatible = [
            tutor_label
            for tutor_label in tutor_labels
            if tutor_label.cx > group_label.cx
            and same_visual_row(group_label, tutor_label, tolerance=9.0)
        ]
        if not compatible:
            continue
        tutor_label = min(
            compatible,
            key=lambda word: (
                abs(word.cy - group_label.cy),
                word.cx - group_label.cx,
            ),
        )
        result.append((group_label, tutor_label))

    result.sort(key=lambda pair: pair[0].cy)
    return result


def _words_between_on_row(
    words: list[VisualWord],
    row_word: VisualWord,
    left_x: float,
    right_x: float,
) -> list[VisualWord]:
    selected = [
        word
        for word in words
        if word is not row_word
        and same_visual_row(word, row_word, tolerance=9.0)
        and left_x < word.cx < right_x
    ]
    selected.sort(key=lambda word: word.x0)
    return selected


def extract_group_anchors(page, page_number: int) -> list[GroupAnchor]:
    words = extract_visual_words(page)
    anchors: list[GroupAnchor] = []

    for group_label, tutor_label in find_group_tutor_pairs(words):
        group_words = _words_between_on_row(
            words,
            group_label,
            group_label.cx,
            tutor_label.cx,
        )
        group_words = [
            word for word in group_words
            if label_key(word.text) not in {"GRUP", "TUTOR"}
        ]
        group_raw = clean_header_value_tokens([word.text for word in group_words])

        tutor_words = [
            word
            for word in words
            if word is not tutor_label
            and same_visual_row(word, tutor_label, tolerance=9.0)
            and word.cx > tutor_label.cx
            and label_key(word.text) not in {"GRUP", "TUTOR"}
        ]
        tutor_words.sort(key=lambda word: word.x0)
        tutor = clean_header_value_tokens([word.text for word in tutor_words])

        anchors.append(
            GroupAnchor(
                page=page_number,
                y=group_label.cy,
                group_raw=group_raw,
                group_code=canonical_group_code(group_raw),
                tutor=tutor,
            )
        )

    return anchors


def _course_label_is_decorated(
    words: list[VisualWord],
    label: VisualWord,
) -> bool:
    if "*" in label.text:
        return True
    for word in words:
        if not same_visual_row(word, label, tolerance=9.0):
            continue
        if word.cx >= label.cx:
            continue
        if label.x0 - word.x1 > 30:
            continue
        if word.text.strip() and set(word.text.strip()) <= {"*"}:
            return True
    return False


def extract_course_anchors(page, page_number: int) -> list[CourseAnchor]:
    """Extrae todas las líneas CURS, incluyendo el texto completo a la derecha."""
    words = extract_visual_words(page)
    course_labels = find_label_words(words, "CURS")
    anchors: list[CourseAnchor] = []

    stop_labels = {
        "GRUP", "TUTOR", "ORDE", "NIA", "REPETIX", "COGNOMS",
        "MATÈRIA", "MATERIA", "CURS",
    }

    for label in course_labels:
        row_words = [
            word
            for word in words
            if word is not label
            and same_visual_row(word, label, tolerance=9.0)
            and word.cx > label.cx
        ]
        row_words.sort(key=lambda word: word.x0)

        value_words: list[VisualWord] = []
        for word in row_words:
            if label_key(word.text) in stop_labels:
                break
            if word.text.strip() in {":", "***"}:
                continue
            value_words.append(word)

        value = clean_header_value_tokens([word.text for word in value_words])
        if value:
            anchors.append(
                CourseAnchor(
                    page=page_number,
                    y=label.cy,
                    value=value.strip("* "),
                    decorated=_course_label_is_decorated(words, label),
                )
            )

    anchors.sort(key=lambda anchor: anchor.y)
    return anchors


def extract_page_metadata(page) -> PageMetadata:
    """Vista resumida compatible: usa las últimas ocurrencias de la página."""
    group_anchors = extract_group_anchors(page, 0)
    course_anchors = extract_course_anchors(page, 0)
    group = group_anchors[-1] if group_anchors else None
    course, _ = resolve_course_values([anchor.value for anchor in course_anchors])
    return PageMetadata(
        group_raw=group.group_raw if group else None,
        group_code=group.group_code if group else None,
        course=course,
        tutor=group.tutor if group else None,
    )


# ===========================================================================
# Segmentación de un PDF en clases
# ===========================================================================

def assign_students_to_metadata(document) -> list[AssignedStudent]:
    """
    Recorre el PDF en orden visual manteniendo el CURS y GRUP activos.

    Esto permite que un mismo PDF contenga varios grupos (caso FP) e incluso
    varios grupos en una misma página. Además, cada aparición de CURS recibe
    un identificador de sección propio: un mismo GRUP puede contener varias
    subsecciones CURS con ORDE reiniciado en 1 (caso Bachillerato).
    """
    assigned: list[AssignedStudent] = []
    active_group: GroupAnchor | None = None
    active_course: CourseAnchor | None = None
    active_course_section: int | None = None
    next_course_section = 0

    for page_index, page in enumerate(document, start=1):
        students = detect_students(page, page_index)
        groups = extract_group_anchors(page, page_index)
        courses = extract_course_anchors(page, page_index)

        # Orden visual vertical. Cabeceras se procesan antes que una fila de
        # alumno si sus coordenadas prácticamente coinciden.
        events: list[tuple[float, int, object]] = []
        events.extend((anchor.y, 0, anchor) for anchor in courses)
        events.extend((anchor.y, 1, anchor) for anchor in groups)
        events.extend((student.visual_y, 2, student) for student in students)
        events.sort(key=lambda item: (item[0], item[1]))

        for _, event_type, item in events:
            if event_type == 0:
                active_course = item  # type: ignore[assignment]
                next_course_section += 1
                active_course_section = next_course_section
            elif event_type == 1:
                active_group = item  # type: ignore[assignment]
            else:
                student = item  # type: ignore[assignment]
                assigned.append(
                    AssignedStudent(
                        student=student,
                        group_raw=active_group.group_raw if active_group else None,
                        group_code=active_group.group_code if active_group else None,
                        course=active_course.value if active_course else None,
                        tutor=active_group.tutor if active_group else None,
                        course_section=active_course_section,
                    )
                )

    return assigned


def _most_common_nonempty(values: list[str | None]) -> str | None:
    filtered = [clean_spaces(value) for value in values if value and clean_spaces(value)]
    if not filtered:
        return None
    counts = Counter(filtered)
    first_index = {value: filtered.index(value) for value in counts}
    return max(counts, key=lambda value: (counts[value], -first_index[value]))


def _unique_course_values(rows: list[AssignedStudent]) -> list[str]:
    """Valores CURS distintos, preservando el orden de aparición."""
    values: list[str] = []
    seen: set[str] = set()

    for row in rows:
        if not row.course:
            continue
        key = normalize_course(row.course)
        if key and key not in seen:
            seen.add(key)
            values.append(clean_spaces(row.course))

    return values


def _split_ordinal_runs(rows: list[AssignedStudent]) -> list[list[AssignedStudent]]:
    """
    Divide las filas de un GRUP en secuencias lógicas de ORDE.

    Un ORDE=1 posterior al primer alumno inicia una nueva secuencia. En los
    listados de Bachillerato esto coincide con una nueva fila CURS. Si una
    cabecera CURS se repite por paginación y ORDE continúa (p. ej. 21, 22,
    23), no se fuerza una nueva secuencia.
    """
    if not rows:
        return []

    runs: list[list[AssignedStudent]] = [[rows[0]]]

    for row in rows[1:]:
        if row.student.ordinal == 1:
            runs.append([row])
        else:
            runs[-1].append(row)

    return runs


def _validate_ordinal_runs(rows: list[AssignedStudent]) -> list[str]:
    """
    Valida ORDE por subsecuencia, no globalmente por GRUP.

    Cuando ORDE se reinicia en 1, exigimos además que haya cambiado la
    sección CURS. Así un reinicio accidental dentro de la misma sección no
    queda oculto por el particionado.
    """
    issues: list[str] = []
    runs = _split_ordinal_runs(rows)

    for run_index, run in enumerate(runs, start=1):
        ordinals = [row.student.ordinal for row in run]
        expected = list(range(1, len(run) + 1))

        if ordinals != expected:
            issues.append(
                "La columna ORDE no forma la secuencia completa 1..N "
                f"en la parte {run_index} del grupo "
                f"(detectado: {', '.join(map(str, ordinals))})"
            )

    for previous, current in zip(rows, rows[1:]):
        if current.student.ordinal != 1:
            continue

        if (
            previous.course_section is not None
            and current.course_section is not None
            and previous.course_section == current.course_section
        ):
            issues.append(
                "ORDE se reinicia en 1 sin haberse detectado una nueva fila CURS"
            )
            break

    return issues


def _build_class_result(
    source: Path,
    group_code: str | None,
    rows: list[AssignedStudent],
) -> ClassResult:
    issues: list[str] = []

    group_raw = _most_common_nonempty([row.group_raw for row in rows])
    tutors = list(dict.fromkeys(row.tutor for row in rows if row.tutor))
    tutor = tutors[0] if tutors else None
    if len(tutors) > 1:
        issues.append("TUTOR no es consistente dentro del grupo")

    course_values = _unique_course_values(rows)
    course, courses_ok = resolve_course_values(course_values)
    if not course_values:
        issues.append("No se ha podido detectar CURS para este grupo")
    elif not courses_ok:
        issues.append("Se han detectado valores de CURS incompatibles dentro del grupo")

    if not group_code:
        issues.append("No se ha podido detectar GRUP para estas filas de alumnado")

    raw_students = [row.student for row in rows]

    # ORDE se valida por partes CURS. Un mismo GRUP de Bachillerato puede
    # contener, por ejemplo, 1..21 y luego 1..11 tras una nueva fila CURS.
    issues.extend(_validate_ordinal_runs(rows))

    nias = [student.nia for student in raw_students]
    if len(set(nias)) != len(nias):
        issues.append("Se han detectado NIA duplicados dentro del grupo")

    # Dedupe sólo después de validar para no ocultar incidencias.
    unique_students: list[Student] = []
    seen_nia: set[str] = set()
    for student in raw_students:
        if student.nia in seen_nia:
            continue
        seen_nia.add(student.nia)
        unique_students.append(student)

    return ClassResult(
        source=source,
        metadata=PageMetadata(
            group_raw=group_raw,
            group_code=group_code,
            course=course,
            tutor=tutor,
        ),
        students=unique_students,
        issues=issues,
        course_values=tuple(course_values),
    )


def process_pdf(pdf_path: Path) -> PdfResult:
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"No se ha podido abrir el PDF: {exc}") from exc

    try:
        report_signature, signature_pages = detect_itaca3_report_signature(document)
        assigned = assign_students_to_metadata(document)
        issues: list[str] = []

        if not report_signature:
            issues.append(
                "No se ha detectado la cabecera completa del listado soportado de "
                "ITACA 3 (ORDE, NIA, REPETIX, COGNOMS I NOM, MATÈRIA)"
            )

        if not assigned:
            return PdfResult(
                source=pdf_path,
                classes=[],
                page_count=document.page_count,
                issues=issues + ["No se ha detectado alumnado"],
                report_signature=report_signature,
                signature_pages=signature_pages,
            )

        # GRUP sigue siendo la unidad natural de salida para iDoceo.
        # Dentro de un mismo GRUP puede haber varias secciones CURS; se
        # conservan dentro de la misma clase y ORDE se valida por sección.
        # Las filas sin GRUP quedan juntas en una clase anónima para revisar.
        buckets: dict[str, list[AssignedStudent]] = {}
        display_codes: dict[str, str | None] = {}

        for row in assigned:
            if row.group_code:
                key = "group:" + row.group_code.casefold()
                display_codes.setdefault(key, row.group_code)
            else:
                # Si falla GRUP, no mezclamos accidentalmente páginas/series.
                key = f"unassigned:{row.student.page}"
                display_codes[key] = None
            buckets.setdefault(key, []).append(row)

        classes = [
            _build_class_result(pdf_path, display_codes[key], rows)
            for key, rows in buckets.items()
        ]

        if not classes:
            issues.append("No se ha podido reconstruir ninguna clase")

        return PdfResult(
            source=pdf_path,
            classes=classes,
            page_count=document.page_count,
            issues=issues,
            report_signature=report_signature,
            signature_pages=signature_pages,
        )
    finally:
        document.close()


# ===========================================================================
# XLSX
# ===========================================================================

def safe_filename_component(text: str) -> str:
    text = clean_spaces(text)
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    return text.strip(" ._") or "grupo"


def safe_sheet_name(text: str) -> str:
    text = re.sub(r"[\[\]:*?/\\]", "_", text)
    return (clean_spaces(text).strip("'") or "Alumnado")[:31]


def unique_output_path(output_dir: Path, base_name: str) -> Path:
    candidate = output_dir / f"{base_name}.xlsx"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = output_dir / f"{base_name}__{counter}.xlsx"
        if not candidate.exists():
            return candidate
        counter += 1


def write_idoceo_xlsx(
    result: ClassResult,
    output_path: Path,
    include_nia: bool,
) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:
        raise RuntimeError(
            "Falta openpyxl. Instálalo con:\n  python -m pip install openpyxl"
        ) from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = safe_sheet_name(result.metadata.group_code or "Alumnado")

    headers = ["Apellidos", "Nombre"]
    if include_nia:
        headers.append("NIA")
    sheet.append(headers)

    for student in result.students:
        row = [student.surnames, student.given_names]
        if include_nia:
            row.append(student.nia)
        sheet.append(row)

    for cell in sheet[1]:
        cell.font = Font(bold=True)

    sheet.freeze_panes = "A2"
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 26
    if include_nia:
        sheet.column_dimensions["C"].width = 16

    workbook.save(output_path)


# ===========================================================================
# CLI helpers
# ===========================================================================

def print_result_check(result: PdfResult) -> None:
    print(f"PDF: {result.source.name}")
    print(f"Páginas: {result.page_count}")
    print(
        "Firma ITACA 3: "
        + (
            "OK (páginas " + ", ".join(map(str, result.signature_pages)) + ")"
            if result.report_signature
            else "NO DETECTADA"
        )
    )
    print(f"Clases detectadas: {len(result.classes)}")

    if result.issues:
        print("Incidencias del PDF:")
        for issue in result.issues:
            print(f"  - {issue}")

    for index, cls in enumerate(result.classes, start=1):
        print()
        print(f"Clase {index}")
        print(f"  GRUP: {cls.metadata.group_code or 'NO DETECTADO'}")
        print(f"  CURS: {cls.metadata.course or 'NO DETECTADO'}")
        if len(cls.course_values) > 1:
            print(f"  Secciones CURS: {len(cls.course_values)}")
            for value in cls.course_values:
                print(f"    - {value}")
        print(f"  TUTOR: {'SÍ' if cls.metadata.tutor else 'NO INDICADO'}")
        print(f"  Alumnos: {len(cls.students)}")
        if cls.students:
            print("  ORDE: " + ", ".join(str(s.ordinal) for s in cls.students))
        if cls.issues:
            print("  Validación: REVISAR")
            for issue in cls.issues:
                print(f"    - {issue}")
        else:
            print("  Validación: OK")


def check_pdf(pdf_path: Path) -> int:
    try:
        result = process_pdf(pdf_path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print_result_check(result)
    return 0


def _write_class_file(
    cls: ClassResult,
    output_dir: Path,
    include_nia: bool,
) -> Path:
    group = cls.metadata.group_code or cls.source.stem
    base = safe_filename_component(group) + "_idoceo"
    output_path = unique_output_path(output_dir, base)
    write_idoceo_xlsx(cls, output_path, include_nia)
    return output_path


def extract_one(
    pdf_path: Path,
    output_path: Path | None,
    include_nia: bool,
) -> int:
    try:
        result = process_pdf(pdf_path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not result.classes:
        print("ERROR: no se ha detectado ninguna clase.", file=sys.stderr)
        return 1

    created: list[Path] = []

    try:
        if len(result.classes) == 1:
            cls = result.classes[0]
            if output_path is None:
                group = cls.metadata.group_code or pdf_path.stem
                output_path = pdf_path.with_name(
                    safe_filename_component(group) + "_idoceo.xlsx"
                )
            elif output_path.exists() and output_path.is_dir():
                output_path = _write_class_file(cls, output_path, include_nia)
                created.append(output_path)
                output_path = None

            if output_path is not None:
                write_idoceo_xlsx(cls, output_path, include_nia)
                created.append(output_path)
        else:
            if output_path is not None and output_path.suffix.casefold() == ".xlsx":
                print(
                    "ERROR: el PDF contiene varias clases; -o debe ser una carpeta, "
                    "no un archivo XLSX.",
                    file=sys.stderr,
                )
                return 2

            output_dir = output_path or (pdf_path.parent / "iDoceo")
            output_dir.mkdir(parents=True, exist_ok=True)
            for cls in result.classes:
                created.append(_write_class_file(cls, output_dir, include_nia))

    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_result_check(result)
    print()
    print("NIA exportado: " + ("SÍ" if include_nia else "NO"))
    for path in created:
        print(f"XLSX: {path}")
    return 0


def find_pdfs(input_dir: Path, recursive: bool) -> list[Path]:
    iterator = input_dir.rglob("*.pdf") if recursive else input_dir.glob("*.pdf")
    return sorted(
        (path for path in iterator if path.is_file()),
        key=lambda path: str(path).casefold(),
    )


def write_manifest(
    output_dir: Path,
    rows: list[dict[str, str]],
    include_nia: bool,
) -> Path:
    manifest_path = output_dir / "idoceo_manifest.txt"
    lines = [
        "ITACA → iDoceo",
        f"Script: {SCRIPT_VERSION}",
        "",
        f"Clases procesadas: {len(rows)}",
        f"NIA incluido en XLSX: {'SÍ' if include_nia else 'NO'}",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"PDF: {row['source']}",
                f"  Estado: {row['status']}",
                f"  Grupo: {row['group']}",
                f"  Curso: {row['course']}",
                f"  Alumnos: {row['students']}",
                f"  XLSX: {row['xlsx']}",
                "",
            ]
        )
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path


def batch_extract(
    input_dir: Path,
    output_dir: Path | None,
    recursive: bool,
    include_nia: bool,
) -> int:
    if not input_dir.is_dir():
        print(f"ERROR: no es una carpeta: {input_dir}", file=sys.stderr)
        return 1

    pdfs = find_pdfs(input_dir, recursive)
    if not pdfs:
        print("ERROR: no se han encontrado PDF en la carpeta.", file=sys.stderr)
        return 1

    output_dir = output_dir or (input_dir / "iDoceo")
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    generated = 0
    failures = 0
    seen_groups: Counter[str] = Counter()

    for pdf_path in pdfs:
        try:
            result = process_pdf(pdf_path)
            if not result.classes:
                raise RuntimeError("no se ha detectado ninguna clase")

            for cls in result.classes:
                group = cls.metadata.group_code or pdf_path.stem
                group_key = group.casefold()
                seen_groups[group_key] += 1
                output_path = _write_class_file(cls, output_dir, include_nia)

                notes = list(result.issues) + list(cls.issues)
                if seen_groups[group_key] > 1:
                    notes.append("grupo repetido en el lote")

                state = "REVISAR" if notes else "OK"
                print(
                    f"{state}  {pdf_path.name} [{group}] -> {output_path.name} "
                    f"[{len(cls.students)} alumnos]"
                )
                rows.append(
                    {
                        "source": pdf_path.name,
                        "status": state + (f" - {'; '.join(notes)}" if notes else ""),
                        "group": cls.metadata.group_code or "NO DETECTADO",
                        "course": cls.metadata.course or "NO DETECTADO",
                        "students": str(len(cls.students)),
                        "xlsx": output_path.name,
                    }
                )
                generated += 1

        except Exception as exc:
            print(f"ERROR  {pdf_path.name}: {exc}", file=sys.stderr)
            failures += 1

    manifest = write_manifest(output_dir, rows, include_nia)
    print()
    print(f"PDF encontrados: {len(pdfs)}")
    print(f"XLSX generados: {generated}")
    print(f"Errores: {failures}")
    print(f"Carpeta de salida: {output_dir}")
    print(f"Resumen: {manifest}")
    return 0 if failures == 0 else 2
