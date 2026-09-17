from __future__ import annotations

import re


# Partículas frecuentes en nombres y apellidos ibéricos. Se dejan en minúscula
# únicamente cuando el campo contiene más de una palabra y la partícula venía
# completamente en mayúsculas. Así no se reescribe texto que ya tuviera una
# capitalización intencionada.
LOWERCASE_PARTICLES = frozenset(
    {
        "de",
        "del",
        "la",
        "las",
        "los",
        "da",
        "das",
        "do",
        "dos",
        "e",
        "i",
        "y",
    }
)

_ROMAN_NUMERAL_RE = re.compile(r"^[IVXLCDM]+$")
_SPLIT_JOINERS_RE = re.compile(r"([-’'])")


def _has_lowercase(text: str) -> bool:
    return any(char.islower() for char in text if char.isalpha())


def _title_simple_piece(piece: str) -> str:
    if not piece:
        return piece
    # Si el origen ya trae minúsculas, preservamos exactamente esa elección
    # para no estropear casos como McDonald u O'Connor.
    if _has_lowercase(piece):
        return piece
    if _ROMAN_NUMERAL_RE.fullmatch(piece):
        return piece

    lowered = piece.lower()
    # Heurística común para McDonald / McCarthy cuando el PDF llega en mayúsculas.
    if lowered.startswith("mc") and len(lowered) > 2 and lowered[2].isalpha():
        return "Mc" + lowered[2].upper() + lowered[3:]
    return lowered[:1].upper() + lowered[1:]


def _title_name_token(token: str) -> str:
    if _has_lowercase(token):
        return token
    parts = _SPLIT_JOINERS_RE.split(token)
    return "".join(
        part if part in {"-", "'", "’"} else _title_simple_piece(part)
        for part in parts
    )


def normalize_name_field(text: str) -> str:
    """Normaliza opcionalmente un campo de nombre/apellidos de ITACA.

    La función está pensada para los listados que suelen llegar completamente en
    mayúsculas. No modifica palabras que ya contienen minúsculas, conserva
    guiones y apóstrofos, aplica capitalización a cada componente y mantiene en
    minúscula partículas ibéricas frecuentes como ``de``, ``del`` o ``da``.

    Es una heurística de presentación, no de identidad: el matching interno debe
    seguir usando siempre el texto original extraído del PDF.
    """
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    if not tokens:
        return ""

    multiple = len(tokens) > 1
    normalized: list[str] = []
    for token in tokens:
        folded = token.casefold()
        if multiple and folded in LOWERCASE_PARTICLES and not _has_lowercase(token):
            normalized.append(folded)
        else:
            normalized.append(_title_name_token(token))
    return " ".join(normalized)


def normalize_person_name(surnames: str, given_names: str) -> tuple[str, str]:
    """Devuelve ``(apellidos, nombre)`` normalizados para salida al usuario."""
    return normalize_name_field(surnames), normalize_name_field(given_names)


def normalized_full_name(surnames: str, given_names: str) -> str:
    normalized_surnames, normalized_given = normalize_person_name(surnames, given_names)
    return f"{normalized_surnames}, {normalized_given}"
