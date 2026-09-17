from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pymupdf

from .core import (
    canonical_group_code,
    clean_header_value_tokens,
    clean_spaces,
    extract_visual_words,
    is_name_component,
    label_key,
    normalize_header_token,
    same_visual_row,
)


MISSING_PHOTO_KEY = "FOTOGRAFIANODISPONIBLE"


@dataclass(frozen=True)
class PhotoCandidate:
    page: int
    xref: int
    x0: float
    y0: float
    x1: float
    y1: float
    width_px: int
    height_px: int
    missing_photo: bool = False

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class MissingPhotoBlock:
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


@dataclass(frozen=True)
class NameBlock:
    block: int
    x0: float
    y0: float
    x1: float
    y1: float
    full_name: str
    surnames: str
    given_names: str
    line_count: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0


@dataclass(frozen=True)
class _RawTextBlock:
    block: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    line_count: int
    line_height: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0


@dataclass(frozen=True)
class PhotoRosterStudent:
    page: int
    ordinal: int
    row: int
    column: int
    full_name: str
    surnames: str
    given_names: str
    xref: int
    image_x0: float
    image_y0: float
    image_x1: float
    image_y1: float
    name_lines: int

    @property
    def has_photo(self) -> bool:
        return self.xref > 0


@dataclass(frozen=True)
class PhotoRosterPageSummary:
    page: int
    candidate_photos: int
    paired_students: int
    rows: int
    max_columns: int
    wrapped_names: int
    missing_photos: int = 0


@dataclass
class PhotoRosterResult:
    source: Path
    page_count: int
    students: list[PhotoRosterStudent]
    pages: list[PhotoRosterPageSummary]
    issues: list[str]
    group_raw: str | None = None
    group_code: str | None = None
    tutor: str | None = None

    @property
    def is_valid(self) -> bool:
        return bool(self.students) and not self.issues


def _visual_rect(page, bbox) -> pymupdf.Rect:
    return pymupdf.Rect(*bbox) * page.rotation_matrix


def _parse_name_text(text: str) -> tuple[str, str, str] | None:
    """Reconoce ``APELLIDOS, NOMBRE`` aunque el texto provenga de varias líneas."""
    tokens = [token.strip() for token in clean_spaces(text).split(" ") if token.strip()]
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
    given_tokens = tokens[comma_index + 1 :]
    if any("," in token for token in surname_tokens[:-1]):
        return None

    last_surname = surname_tokens[-1][:-1]
    if not last_surname:
        return None
    surname_components = surname_tokens[:-1] + [last_surname]

    if not all(is_name_component(token) for token in surname_components):
        return None
    if not all(is_name_component(token) for token in given_tokens):
        return None

    surnames = " ".join(surname_components)
    given_names = " ".join(given_tokens)
    return f"{surnames}, {given_names}", surnames, given_names


def _continuation_is_name_text(text: str) -> bool:
    """Acepta sólo continuaciones sin coma formadas por componentes de nombre."""
    tokens = [token.strip() for token in clean_spaces(text).split(" ") if token.strip()]
    return bool(tokens) and not any("," in token for token in tokens) and all(
        is_name_component(token) for token in tokens
    )


def _same_name_column(anchor: _RawTextBlock, candidate: _RawTextBlock) -> bool:
    """Decide si dos líneas pueden pertenecer a la misma celda de nombre.

    Los nombres del informe pueden ir centrados o alineados a la izquierda. Una
    línea de apellidos muy larga y una segunda línea con un nombre corto pueden
    tener centros bastante alejados aunque comiencen exactamente en el mismo X.
    Las columnas observadas están separadas unos 94 pt, así que exigimos cercanía
    por centro *o* por borde izquierdo, sin utilizar el borde derecho (que una
    línea larga podría acercar artificialmente a la columna vecina).
    """
    return min(abs(candidate.cx - anchor.cx), abs(candidate.x0 - anchor.x0)) <= 44.0


def _merge_name_blocks(raw_blocks: list[_RawTextBlock]) -> list[NameBlock]:
    """Reconstruye nombres que el PDF haya partido en varios bloques de texto.

    Algunos listados dibujan visualmente un único ``APELLIDOS, NOMBRE`` en dos
    líneas pero guardan la segunda línea como un bloque PDF independiente. La
    unión se restringe a bloques inmediatamente inferiores y a la misma columna,
    para no absorber texto del alumno contiguo.
    """
    result: list[NameBlock] = []
    consumed: set[int] = set()

    for anchor in sorted(raw_blocks, key=lambda item: (item.y0, item.x0, item.block)):
        if anchor.block in consumed or "," not in anchor.text:
            continue

        merged = [anchor]
        merged_text = anchor.text
        best_parsed = _parse_name_text(merged_text)
        best_blocks = list(merged) if best_parsed is not None else []
        current_y1 = anchor.y1
        current_height = anchor.line_height

        for _ in range(2):
            candidates: list[_RawTextBlock] = []
            max_gap = max(4.0, min(12.0, current_height * 1.6))
            for candidate in raw_blocks:
                if candidate.block == anchor.block or candidate.block in consumed:
                    continue
                if candidate in merged or not _continuation_is_name_text(candidate.text):
                    continue
                if candidate.y0 < current_y1 - 1.5:
                    continue
                if candidate.y0 - current_y1 > max_gap:
                    continue
                if not _same_name_column(anchor, candidate):
                    continue
                candidates.append(candidate)

            if not candidates:
                break

            candidates.sort(
                key=lambda item: (
                    max(0.0, item.y0 - current_y1),
                    min(abs(item.cx - anchor.cx), abs(item.x0 - anchor.x0)),
                    item.x0,
                )
            )
            candidate = candidates[0]
            proposed_text = clean_spaces(f"{merged_text} {candidate.text}")
            proposed_parsed = _parse_name_text(proposed_text)

            # Si el ancla ya era un nombre completo, sólo incorporamos la línea
            # siguiente cuando el conjunto sigue siendo un nombre válido. Si el
            # ancla terminaba en coma, permitimos que la continuación lo complete.
            if proposed_parsed is None and best_parsed is not None:
                break

            merged.append(candidate)
            merged_text = proposed_text
            current_y1 = max(current_y1, candidate.y1)
            current_height = max(current_height, candidate.line_height)
            if proposed_parsed is not None:
                best_parsed = proposed_parsed
                best_blocks = list(merged)

        if best_parsed is None:
            continue

        full_name, surnames, given_names = best_parsed
        blocks_for_name = best_blocks or [anchor]
        if len(blocks_for_name) > 1:
            consumed.update(block.block for block in blocks_for_name[1:])

        result.append(
            NameBlock(
                block=anchor.block,
                x0=min(block.x0 for block in blocks_for_name),
                y0=min(block.y0 for block in blocks_for_name),
                x1=max(block.x1 for block in blocks_for_name),
                y1=max(block.y1 for block in blocks_for_name),
                full_name=full_name,
                surnames=surnames,
                given_names=given_names,
                line_count=sum(block.line_count for block in blocks_for_name),
            )
        )

    return result


def _extract_name_blocks(page) -> list[NameBlock]:
    text_dict = page.get_text("dict", sort=False)
    raw_blocks: list[_RawTextBlock] = []

    for block_index, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") != 0:
            continue

        lines: list[str] = []
        rects: list[pymupdf.Rect] = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(str(span.get("text", "")) for span in spans).strip()
            if not text:
                continue
            lines.append(text)
            rects.append(_visual_rect(page, line.get("bbox", (0, 0, 0, 0))))

        if not lines or not rects:
            continue

        raw_blocks.append(
            _RawTextBlock(
                block=block_index,
                text=clean_spaces(" ".join(lines)),
                x0=min(rect.x0 for rect in rects),
                y0=min(rect.y0 for rect in rects),
                x1=max(rect.x1 for rect in rects),
                y1=max(rect.y1 for rect in rects),
                line_count=len(lines),
                line_height=float(median(rect.height for rect in rects)),
            )
        )

    return _merge_name_blocks(raw_blocks)


def _looks_like_portrait_photo(rect: pymupdf.Rect, page) -> bool:
    width = rect.width
    height = rect.height
    if width < 40 or height < 55:
        return False
    if width > page.rect.width * 0.25 or height > page.rect.height * 0.25:
        return False
    if rect.y0 < page.rect.height * 0.15:
        return False
    ratio = width / height if height else 0.0
    return 0.55 <= ratio <= 1.05


def _extract_photo_candidates(page, page_number: int) -> list[PhotoCandidate]:
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        infos = []

    result: list[PhotoCandidate] = []
    for info in infos:
        bbox = info.get("bbox")
        xref = int(info.get("xref") or 0)
        if not bbox or xref <= 0:
            continue
        rect = _visual_rect(page, bbox)
        if not _looks_like_portrait_photo(rect, page):
            continue
        result.append(
            PhotoCandidate(
                page=page_number,
                xref=xref,
                x0=rect.x0,
                y0=rect.y0,
                x1=rect.x1,
                y1=rect.y1,
                width_px=int(info.get("width") or 0),
                height_px=int(info.get("height") or 0),
            )
        )
    return result


def _is_missing_photo_text(text: str) -> bool:
    return normalize_header_token(text) == MISSING_PHOTO_KEY


def _extract_missing_photo_blocks(page) -> list[MissingPhotoBlock]:
    """Localiza el marcador textual ``Fotografía no disponible``.

    El informe observado lo dibuja dentro de una casilla del mismo tamaño que
    las fotos. Primero intentamos reconstruir el texto por bloque; como
    salvaguarda, también agrupamos las tres palabras por proximidad visual para
    tolerar generadores PDF que las separen en bloques distintos.
    """
    text_dict = page.get_text("dict", sort=False)
    result: list[MissingPhotoBlock] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines: list[str] = []
        rects: list[pymupdf.Rect] = []
        for line in block.get("lines", []):
            text = "".join(
                str(span.get("text", "")) for span in line.get("spans", [])
            ).strip()
            if not text:
                continue
            lines.append(text)
            rects.append(_visual_rect(page, line.get("bbox", (0, 0, 0, 0))))
        if lines and rects and _is_missing_photo_text(" ".join(lines)):
            result.append(
                MissingPhotoBlock(
                    x0=min(rect.x0 for rect in rects),
                    y0=min(rect.y0 for rect in rects),
                    x1=max(rect.x1 for rect in rects),
                    y1=max(rect.y1 for rect in rects),
                )
            )

    if result:
        return result

    words: list[tuple[str, pymupdf.Rect]] = []
    for item in page.get_text("words", sort=False):
        rect = _visual_rect(page, item[:4])
        words.append((normalize_header_token(str(item[4])), rect))

    fotografia = [rect for key, rect in words if key == "FOTOGRAFIA"]
    no_words = [rect for key, rect in words if key == "NO"]
    disponible = [rect for key, rect in words if key == "DISPONIBLE"]

    for first in fotografia:
        nearby_no = [
            rect
            for rect in no_words
            if abs(((rect.x0 + rect.x1) / 2.0) - ((first.x0 + first.x1) / 2.0)) <= 75
            and abs(((rect.y0 + rect.y1) / 2.0) - ((first.y0 + first.y1) / 2.0)) <= 28
        ]
        nearby_available = [
            rect
            for rect in disponible
            if abs(((rect.x0 + rect.x1) / 2.0) - ((first.x0 + first.x1) / 2.0)) <= 75
            and 0 <= ((rect.y0 + rect.y1) / 2.0) - ((first.y0 + first.y1) / 2.0) <= 45
        ]
        if not nearby_no or not nearby_available:
            continue
        second = min(nearby_no, key=lambda rect: abs(rect.y0 - first.y0))
        third = min(nearby_available, key=lambda rect: abs(rect.y0 - first.y0))
        rects = [first, second, third]
        result.append(
            MissingPhotoBlock(
                x0=min(rect.x0 for rect in rects),
                y0=min(rect.y0 for rect in rects),
                x1=max(rect.x1 for rect in rects),
                y1=max(rect.y1 for rect in rects),
            )
        )

    return result


def _cluster_rows(
    photos: list[PhotoCandidate],
    tolerance: float = 12.0,
) -> list[list[PhotoCandidate]]:
    rows: list[list[PhotoCandidate]] = []
    for photo in sorted(photos, key=lambda item: (item.y0, item.x0)):
        best_index: int | None = None
        best_distance: float | None = None
        for index, row in enumerate(rows):
            mean_y = sum(item.y0 for item in row) / len(row)
            distance = abs(photo.y0 - mean_y)
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best_index = index
                best_distance = distance
        if best_index is None:
            rows.append([photo])
        else:
            rows[best_index].append(photo)

    rows.sort(key=lambda row: sum(item.y0 for item in row) / len(row))
    for row in rows:
        row.sort(key=lambda item: item.x0)
    return rows


def _add_missing_photo_slots(
    photos: list[PhotoCandidate],
    missing_blocks: list[MissingPhotoBlock],
    page_number: int,
) -> list[PhotoCandidate]:
    """Convierte los marcadores sin foto en casillas geométricas de la cuadrícula."""
    if not missing_blocks:
        return list(photos)
    if not photos:
        # Sin ninguna fotografía real no tenemos todavía una referencia segura
        # para inferir el tamaño y la fila de las casillas.
        return list(photos)

    width = float(median(photo.width for photo in photos))
    height = float(median(photo.height for photo in photos))
    real_rows = _cluster_rows(photos)
    result = list(photos)

    for block in missing_blocks:
        row = min(
            real_rows,
            key=lambda items: abs(
                (sum(item.cy for item in items) / len(items)) - block.cy
            ),
        )
        row_cy = sum(item.cy for item in row) / len(row)
        if abs(row_cy - block.cy) > max(45.0, height * 0.8):
            continue

        row_y0 = float(median(item.y0 for item in row))
        row_y1 = float(median(item.y1 for item in row))
        result.append(
            PhotoCandidate(
                page=page_number,
                xref=0,
                x0=block.cx - width / 2.0,
                y0=row_y0,
                x1=block.cx + width / 2.0,
                y1=row_y1,
                width_px=0,
                height_px=0,
                missing_photo=True,
            )
        )

    return result


def _pair_row(
    row: list[PhotoCandidate],
    name_blocks: list[NameBlock],
    next_row_y: float | None,
    used_blocks: set[int],
) -> list[tuple[PhotoCandidate, NameBlock | None]]:
    pairs: list[tuple[PhotoCandidate, NameBlock | None]] = []

    for photo in row:
        lower_limit = photo.y1 - 3.0
        upper_limit = (
            next_row_y - 3.0
            if next_row_y is not None
            else photo.y1 + max(45.0, photo.height * 0.55)
        )
        max_x_distance = max(18.0, photo.width * 0.75)

        candidates = [
            block
            for block in name_blocks
            if block.block not in used_blocks
            and block.y0 >= lower_limit
            and block.y0 <= upper_limit
            and abs(block.cx - photo.cx) <= max_x_distance
        ]

        if not candidates:
            pairs.append((photo, None))
            continue

        block = min(
            candidates,
            key=lambda item: (
                max(0.0, item.y0 - photo.y1),
                abs(item.cx - photo.cx),
            ),
        )
        used_blocks.add(block.block)
        pairs.append((photo, block))

    return pairs


def _extract_group_metadata(page) -> tuple[str | None, str | None, str | None]:
    """Reutiliza la geometría GRUP/GRUPO ... TUTOR del informe clásico."""
    words = extract_visual_words(page)
    group_labels = [
        word for word in words if label_key(word.text) in {"GRUP", "GRUPO"}
    ]
    tutor_labels = [word for word in words if label_key(word.text) == "TUTOR"]

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
        group_words = [
            word
            for word in words
            if word is not group_label
            and same_visual_row(word, group_label, tolerance=9.0)
            and group_label.cx < word.cx < tutor_label.cx
            and label_key(word.text) not in {"GRUP", "GRUPO", "TUTOR"}
        ]
        group_words.sort(key=lambda word: word.x0)
        group_raw = clean_header_value_tokens([word.text for word in group_words])

        tutor_words = [
            word
            for word in words
            if word is not tutor_label
            and same_visual_row(word, tutor_label, tolerance=9.0)
            and word.cx > tutor_label.cx
            and label_key(word.text) not in {"GRUP", "GRUPO", "TUTOR"}
        ]
        tutor_words.sort(key=lambda word: word.x0)
        tutor = clean_header_value_tokens([word.text for word in tutor_words])
        return group_raw, canonical_group_code(group_raw), tutor

    return None, None, None


def detect_photo_roster(pdf_path: Path) -> PhotoRosterResult:
    """Detecta la cuadrícula de alumnado, incluyendo casillas sin fotografía."""
    document = pymupdf.open(pdf_path)
    try:
        students: list[PhotoRosterStudent] = []
        summaries: list[PhotoRosterPageSummary] = []
        issues: list[str] = []
        ordinal = 0
        group_raw: str | None = None
        group_code: str | None = None
        tutor: str | None = None

        for page_number, page in enumerate(document, start=1):
            page_group_raw, page_group_code, page_tutor = _extract_group_metadata(page)
            if group_raw is None and page_group_raw:
                group_raw = page_group_raw
                group_code = page_group_code
                tutor = page_tutor

            photos = _extract_photo_candidates(page, page_number)
            missing_blocks = _extract_missing_photo_blocks(page)
            slots = _add_missing_photo_slots(photos, missing_blocks, page_number)
            names = _extract_name_blocks(page)
            rows = _cluster_rows(slots)
            used_blocks: set[int] = set()
            paired_on_page = 0
            wrapped_on_page = 0
            missing_on_page = sum(slot.missing_photo for slot in slots)

            if missing_blocks and missing_on_page != len(missing_blocks):
                issues.append(
                    f"Página {page_number}: no se han podido ubicar todas las casillas "
                    "de «Fotografía no disponible»"
                )

            if slots and page.rect.width >= page.rect.height:
                issues.append(
                    f"Página {page_number}: se detecta una cuadrícula de alumnado "
                    "pero la página no está en orientación vertical"
                )

            for row_index, row in enumerate(rows, start=1):
                next_row_y = None
                if row_index < len(rows):
                    next_row = rows[row_index]
                    next_row_y = min(item.y0 for item in next_row)

                for column_index, (slot, name) in enumerate(
                    _pair_row(row, names, next_row_y, used_blocks),
                    start=1,
                ):
                    if name is None:
                        issues.append(
                            f"Página {page_number}: una casilla de la fila {row_index}, "
                            f"columna {column_index} no tiene un nombre inequívoco debajo"
                        )
                        continue

                    ordinal += 1
                    paired_on_page += 1
                    if name.line_count > 1:
                        wrapped_on_page += 1

                    students.append(
                        PhotoRosterStudent(
                            page=page_number,
                            ordinal=ordinal,
                            row=row_index,
                            column=column_index,
                            full_name=name.full_name,
                            surnames=name.surnames,
                            given_names=name.given_names,
                            xref=slot.xref,
                            image_x0=slot.x0,
                            image_y0=slot.y0,
                            image_x1=slot.x1,
                            image_y1=slot.y1,
                            name_lines=name.line_count,
                        )
                    )

            if slots:
                if any(len(row) > 6 for row in rows):
                    issues.append(
                        f"Página {page_number}: se han detectado más de 6 casillas en una fila"
                    )
                if len(slots) != paired_on_page:
                    issues.append(
                        f"Página {page_number}: {len(slots)} casillas de alumnado y "
                        f"{paired_on_page} parejas casilla/nombre"
                    )

                summaries.append(
                    PhotoRosterPageSummary(
                        page=page_number,
                        candidate_photos=len(photos),
                        paired_students=paired_on_page,
                        rows=len(rows),
                        max_columns=max((len(row) for row in rows), default=0),
                        wrapped_names=wrapped_on_page,
                        missing_photos=missing_on_page,
                    )
                )

        if not summaries:
            issues.append("No se ha detectado una cuadrícula compatible de alumnado")
        if summaries and not students:
            issues.append("No se ha podido emparejar ninguna casilla con un nombre")

        return PhotoRosterResult(
            source=pdf_path,
            page_count=document.page_count,
            students=students,
            pages=summaries,
            issues=issues,
            group_raw=group_raw,
            group_code=group_code,
            tutor=tutor,
        )
    finally:
        document.close()


def print_photo_roster_check(result: PhotoRosterResult) -> None:
    """Muestra sólo métricas estructurales; nunca nombres, NIA ni rutas."""
    print(
        "Formato de listado con fotos: "
        + ("COMPATIBLE" if result.students else "NO DETECTADO")
    )
    print(f"Páginas: {result.page_count}")
    print(f"Alumnos emparejados: {len(result.students)}")
    print(f"Incidencias: {len(result.issues)}")

    for page in result.pages:
        print(
            f"Página {page.page}: fotos={page.candidate_photos} "
            f"sin_foto={page.missing_photos} parejas={page.paired_students} "
            f"filas={page.rows} máx_columnas={page.max_columns} "
            f"nombres_multilínea={page.wrapped_names}"
        )

    for issue in result.issues:
        print(f"REVISAR: {issue}")


def check_photo_roster(pdf_path: Path) -> int:
    try:
        result = detect_photo_roster(pdf_path)
    except Exception as exc:
        print(f"ERROR: no se ha podido analizar el listado con fotos: {exc}")
        return 1

    print_photo_roster_check(result)
    return 0 if result.is_valid else 2
