from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import pymupdf


SAFE_LABELS = {
    "ALUMNES",
    "ASSIGNATURA",
    "CENTRE",
    "COGNOMS",
    "CURS",
    "DISPONIBLE",
    "FOTOGRAFIA",
    "GRUP",
    "GRUPO",
    "I",
    "LLISTAT",
    "MATERIA",
    "MODUL",
    "NIA",
    "NO",
    "NOM",
    "PROFESSOR",
    "TUTOR",
}


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _mask_token(text: str) -> str:
    if not text:
        return "<EMPTY>"
    key = _norm(text)
    if key in SAFE_LABELS:
        return key
    if text.strip().isdigit():
        return f"<NUM:{len(text.strip())}>"

    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    comma = "," if "," in text else ""
    hyphen = "-" if "-" in text else ""
    apost = "'" if ("'" in text or "’" in text) else ""
    other = (
        len(text)
        - letters
        - digits
        - text.count(",")
        - text.count("-")
        - text.count("'")
        - text.count("’")
    )
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


def _visual_rect(page, bbox) -> pymupdf.Rect:
    return pymupdf.Rect(*bbox) * page.rotation_matrix


def _looks_like_name(text: str) -> bool:
    if text.count(",") != 1:
        return False
    left, right = text.split(",", 1)
    if not left.strip() or not right.strip():
        return False
    allowed = lambda c: c.isalpha() or c.isspace() or c in "-'’"
    return all(allowed(c) for c in left + right)


def _sanitize_line(text: str) -> str:
    return " ".join(_mask_token(token) for token in text.split())


def build_photo_layout_report(pdf_path: Path) -> str:
    """Genera un informe anónimo de geometría de texto e imágenes.

    Está pensado para estudiar listados de alumnado con fotos sin sacar del
    equipo nombres, NIA, materias, grupo, centro, rutas locales ni bytes de las
    imágenes. Sólo conserva etiquetas estructurales conocidas y la forma de
    los demás tokens.
    """
    rows: list[str] = [
        "ITACA -> iDoceo | informe anonimo de listado con fotos v1",
        "NO CONTIENE: nombre/ruta del PDF, nombres, NIA, materias, grupo, centro ni imagenes.",
        "Texto libre: sustituido por <Lx:Dy:...>; solo se conservan etiquetas estructurales.",
        "Imagenes: solo geometria, dimensiones y xref interno; no se incluyen bytes ni hashes.",
        "",
    ]

    doc = pymupdf.open(pdf_path)
    try:
        rows.append(f"PAGINAS={doc.page_count}")
        for page_index, page in enumerate(doc, start=1):
            text_dict = page.get_text("dict", sort=False)
            text_entries: list[tuple[float, float, str]] = []

            for block_index, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                for line_index, line in enumerate(block.get("lines", [])):
                    text = "".join(
                        str(span.get("text", "")) for span in line.get("spans", [])
                    ).strip()
                    if not text:
                        continue
                    rect = _visual_rect(page, line.get("bbox", (0, 0, 0, 0)))
                    name_like = " yes" if _looks_like_name(text) else " no"
                    text_entries.append(
                        (
                            rect.y0,
                            rect.x0,
                            f"TEXT b={block_index} l={line_index} "
                            f"visual=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}) "
                            f"name_like={name_like.strip()} :: {_sanitize_line(text)}",
                        )
                    )

            image_entries: list[tuple[float, float, str]] = []
            try:
                image_infos = page.get_image_info(xrefs=True)
            except Exception:
                image_infos = []

            for image_index, info in enumerate(image_infos, start=1):
                bbox = info.get("bbox")
                if not bbox:
                    continue
                rect = _visual_rect(page, bbox)
                width = int(info.get("width") or 0)
                height = int(info.get("height") or 0)
                xref = int(info.get("xref") or 0)
                bpc = int(info.get("bpc") or 0)
                image_entries.append(
                    (
                        rect.y0,
                        rect.x0,
                        f"IMAGE {image_index} xref={xref} px={width}x{height} bpc={bpc} "
                        f"visual=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f})",
                    )
                )

            rows.append("")
            rows.append(
                f"PAGE={page_index} rotation={page.rotation} "
                f"visual={page.rect.width:.1f}x{page.rect.height:.1f} "
                f"crop={page.cropbox.width:.1f}x{page.cropbox.height:.1f} "
                f"images={len(image_entries)} text_lines={len(text_entries)}"
            )

            for _, _, entry in sorted(text_entries + image_entries):
                rows.append("  " + entry)
    finally:
        doc.close()

    return "\n".join(rows) + "\n"
