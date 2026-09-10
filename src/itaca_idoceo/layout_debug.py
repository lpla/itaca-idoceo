from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import unicodedata

import pymupdf


SAFE_LABELS = {
    "ORDE", "NIA", "REPETIX", "COGNOMS", "I", "NOM", "MATERIA", "MODUL",
}


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _mask_free_token(text: str) -> str:
    """Describe la forma de un token sin conservar su contenido."""
    if not text:
        return "<EMPTY>"
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    comma = "," if "," in text else ""
    hyphen = "-" if "-" in text else ""
    apost = "'" if ("'" in text or "’" in text) else ""
    other = len(text) - letters - digits - text.count(",") - text.count("-") - text.count("'") - text.count("’")
    parts = [f"L{letters}"] if letters else []
    if digits:
        parts.append(f"D{digits}")
    if comma:
        parts.append("COMMA")
    if hyphen:
        parts.append("HYPHEN")
    if apost:
        parts.append("APOST")
    if other > 0:
        parts.append(f"P{other}")
    return "<" + ":".join(parts or [f"LEN{len(text)}"]) + ">"


def sanitize_word(text: str, *, ordinal_position: bool = False) -> str:
    key = _norm(text)
    if key in SAFE_LABELS:
        # Canonicalizamos acentos para que el informe no dependa de codificación.
        return key
    if text.strip().upper() == "R":
        return "R"
    if text.strip().isdigit():
        if ordinal_position:
            # ORDE no es un identificador personal y resulta esencial para localizar la fila.
            return f"ORDE={int(text.strip())}"
        return f"<NUM:{len(text.strip())}>"
    return _mask_free_token(text.strip())


def _visual_rect(page, word_tuple) -> pymupdf.Rect:
    x0, y0, x1, y1 = word_tuple[:4]
    return pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix


def _block_visual_rect(page, items) -> pymupdf.Rect:
    rects = [_visual_rect(page, item) for item in items]
    return pymupdf.Rect(
        min(r.x0 for r in rects), min(r.y0 for r in rects),
        max(r.x1 for r in rects), max(r.y1 for r in rects),
    )


def _line_visual_rect(page, items) -> pymupdf.Rect:
    return _block_visual_rect(page, items)


def _line_raw_y0(items) -> float:
    return min(float(item[1]) for item in items)


def _is_ordinal_line(items, height: float) -> bool:
    return (
        len(items) == 1
        and str(items[0][4]).strip().isdigit()
        and 0.92 <= float(items[0][1]) / height <= 0.99
    )


def _is_nia_line(items, height: float) -> bool:
    return (
        len(items) == 1
        and str(items[0][4]).strip().isdigit()
        and 0.84 <= float(items[0][1]) / height <= 0.92
    )


def build_layout_report(pdf_path: Path, only_ordinals: set[int] | None = None) -> str:
    """Genera un informe geométrico que no contiene texto libre del PDF.

    Se conservan únicamente etiquetas estructurales conocidas, el marcador R y
    los valores de ORDE. NIA, nombres, materias, grupo, curso, tutor, centro y
    cualquier otro texto libre se sustituyen por descriptores de forma.
    """
    rows: list[str] = [
        "ITACA -> iDoceo | informe anonimo de estructura v1",
        "NO CONTIENE: nombre/ruta del PDF, NIA, nombres, materias, grupo, curso, tutor ni centro.",
        "Texto libre: sustituido por <Lx:Dy:...>; numeros no-ORDE: <NUM:n>.",
        "",
    ]

    doc = pymupdf.open(pdf_path)
    try:
        rows.append(f"PAGINAS={doc.page_count}")
        for page_index, page in enumerate(doc):
            words = list(page.get_text("words", sort=False))
            if not words:
                continue
            height = page.cropbox.height
            grouped: dict[int, dict[int, list[tuple]]] = defaultdict(lambda: defaultdict(list))
            block_items: dict[int, list[tuple]] = defaultdict(list)
            for item in words:
                block = int(item[5]); line = int(item[6])
                grouped[block][line].append(item)
                block_items[block].append(item)

            anchors: list[tuple[int, int, pymupdf.Rect]] = []
            for block, lines in grouped.items():
                ordinal = None
                has_nia = False
                for line_items in lines.values():
                    if _is_ordinal_line(line_items, height):
                        ordinal = int(str(line_items[0][4]).strip())
                    if _is_nia_line(line_items, height):
                        has_nia = True
                if ordinal is not None and has_nia:
                    if only_ordinals and ordinal not in only_ordinals:
                        continue
                    anchors.append((block, ordinal, _block_visual_rect(page, block_items[block])))

            if not anchors:
                continue

            rows.append("")
            rows.append(
                f"PAGE={page_index + 1} rotation={page.rotation} "
                f"crop={page.cropbox.width:.1f}x{page.cropbox.height:.1f} "
                f"anchors={len(anchors)}"
            )

            for anchor_block, ordinal, anchor_rect in anchors:
                # Una continuación de celda suele ser otro bloque a pocos puntos
                # de la misma fila visual. Un margen moderado captura ese bloque
                # y, como mucho, parte de las filas vecinas para dar contexto.
                margin_y = 12.0
                cluster_blocks = []
                for block, items in block_items.items():
                    rect = _block_visual_rect(page, items)
                    vertical_close = not (
                        rect.y1 < anchor_rect.y0 - margin_y
                        or rect.y0 > anchor_rect.y1 + margin_y
                    )
                    horizontal_table_overlap = rect.x1 >= 20 and rect.x0 <= page.rect.width - 20
                    if vertical_close and horizontal_table_overlap:
                        cluster_blocks.append((rect.y0, rect.x0, block, rect))
                cluster_blocks.sort()

                rows.append("")
                rows.append(
                    f"ROW ORDE={ordinal} anchor_block={anchor_block} "
                    f"anchor_visual=({anchor_rect.x0:.1f},{anchor_rect.y0:.1f},"
                    f"{anchor_rect.x1:.1f},{anchor_rect.y1:.1f})"
                )
                for _, _, block, rect in cluster_blocks:
                    mark = "*" if block == anchor_block else "+"
                    rows.append(
                        f"  {mark} BLOCK {block} visual=({rect.x0:.1f},{rect.y0:.1f},"
                        f"{rect.x1:.1f},{rect.y1:.1f})"
                    )
                    for line_no in sorted(grouped[block]):
                        items = sorted(grouped[block][line_no], key=lambda item: int(item[7]))
                        lrect = _line_visual_rect(page, items)
                        raw_y0 = _line_raw_y0(items)
                        ordinal_position = _is_ordinal_line(items, height)
                        tokens = " ".join(
                            sanitize_word(str(item[4]), ordinal_position=ordinal_position)
                            for item in items
                        )
                        rows.append(
                            f"      L{line_no} raw_y={raw_y0:.1f} raw_f={raw_y0/height:.4f} "
                            f"visual=({lrect.x0:.1f},{lrect.y0:.1f},{lrect.x1:.1f},{lrect.y1:.1f}) "
                            f":: {tokens}"
                        )
    finally:
        doc.close()

    return "\n".join(rows) + "\n"
