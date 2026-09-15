from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .core import clean_spaces, is_name_component


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

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


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


@dataclass(frozen=True)
class PhotoRosterPageSummary:
    page: int
    candidate_photos: int
    paired_students: int
    rows: int
    max_columns: int
    wrapped_names: int


@dataclass
class PhotoRosterResult:
    source: Path
    page_count: int
    students: list[PhotoRosterStudent]
    pages: list[PhotoRosterPageSummary]
    issues: list[str]

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


def _extract_name_blocks(page) -> list[NameBlock]:
    text_dict = page.get_text("dict", sort=False)
    result: list[NameBlock] = []

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

        parsed = _parse_name_text(" ".join(lines))
        if parsed is None:
            continue

        full_name, surnames, given_names = parsed
        result.append(
            NameBlock(
                block=block_index,
                x0=min(rect.x0 for rect in rects),
                y0=min(rect.y0 for rect in rects),
                x1=max(rect.x1 for rect in rects),
                y1=max(rect.y1 for rect in rects),
                full_name=full_name,
                surnames=surnames,
                given_names=given_names,
                line_count=len(lines),
            )
        )

    return result


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


def detect_photo_roster(pdf_path: Path) -> PhotoRosterResult:
    """Detecta el formato de cuadrícula foto + nombre sin extraer imágenes."""
    document = pymupdf.open(pdf_path)
    try:
        students: list[PhotoRosterStudent] = []
        summaries: list[PhotoRosterPageSummary] = []
        issues: list[str] = []
        ordinal = 0

        for page_number, page in enumerate(document, start=1):
            photos = _extract_photo_candidates(page, page_number)
            names = _extract_name_blocks(page)
            rows = _cluster_rows(photos)
            used_blocks: set[int] = set()
            paired_on_page = 0
            wrapped_on_page = 0

            if photos and page.rect.width >= page.rect.height:
                issues.append(
                    f"Página {page_number}: se detectan fotos pero la página no está en orientación vertical"
                )

            for row_index, row in enumerate(rows, start=1):
                next_row_y = None
                if row_index < len(rows):
                    next_row = rows[row_index]
                    next_row_y = min(item.y0 for item in next_row)

                for column_index, (photo, name) in enumerate(
                    _pair_row(row, names, next_row_y, used_blocks),
                    start=1,
                ):
                    if name is None:
                        issues.append(
                            f"Página {page_number}: una foto de la fila {row_index}, "
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
                            xref=photo.xref,
                            image_x0=photo.x0,
                            image_y0=photo.y0,
                            image_x1=photo.x1,
                            image_y1=photo.y1,
                            name_lines=name.line_count,
                        )
                    )

            if photos:
                if any(len(row) > 6 for row in rows):
                    issues.append(
                        f"Página {page_number}: se han detectado más de 6 fotos en una fila"
                    )
                if len(photos) != paired_on_page:
                    issues.append(
                        f"Página {page_number}: {len(photos)} fotos candidatas y "
                        f"{paired_on_page} parejas foto/nombre"
                    )

                summaries.append(
                    PhotoRosterPageSummary(
                        page=page_number,
                        candidate_photos=len(photos),
                        paired_students=paired_on_page,
                        rows=len(rows),
                        max_columns=max((len(row) for row in rows), default=0),
                        wrapped_names=wrapped_on_page,
                    )
                )

        if not summaries:
            issues.append("No se ha detectado una cuadrícula compatible de fotos de alumnado")
        if summaries and not students:
            issues.append("No se ha podido emparejar ninguna foto con un nombre")

        return PhotoRosterResult(
            source=pdf_path,
            page_count=document.page_count,
            students=students,
            pages=summaries,
            issues=issues,
        )
    finally:
        document.close()


def print_photo_roster_check(result: PhotoRosterResult) -> None:
    """Muestra sólo métricas estructurales; nunca nombres, NIA ni rutas."""
    print("Formato de listado con fotos: " + ("COMPATIBLE" if result.students else "NO DETECTADO"))
    print(f"Páginas: {result.page_count}")
    print(f"Alumnos emparejados: {len(result.students)}")
    print(f"Incidencias: {len(result.issues)}")

    for page in result.pages:
        print(
            f"Página {page.page}: fotos={page.candidate_photos} "
            f"parejas={page.paired_students} filas={page.rows} "
            f"máx_columnas={page.max_columns} nombres_multilínea={page.wrapped_names}"
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
