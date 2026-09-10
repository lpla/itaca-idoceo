"""Diagnósticos compartibles sin datos personales ni metadatos identificativos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from . import __version__
from .core import PdfResult

_SAFE_ISSUE_PREFIXES = (
    "La columna ORDE no forma",
    "ORDE se reinicia",
    "Se han detectado NIA duplicados",
    "TUTOR no es consistente",
    "No se ha podido detectar CURS",
    "Se han detectado valores de CURS incompatibles",
    "No se ha podido detectar GRUP",
    "No se ha detectado la cabecera completa",
    "No se ha detectado alumnado",
    "No se ha podido reconstruir ninguna clase",
    "Hay más de un grupo cargado con el mismo código",
)


def _safe_issue(issue: str) -> str:
    """Sólo deja pasar mensajes internos conocidos que no contienen PII."""
    if issue.startswith(_SAFE_ISSUE_PREFIXES):
        return issue
    return "Incidencia de validación (detalle omitido por privacidad)"


def build_anonymized_diagnostic(
    results: Sequence[PdfResult],
    *,
    class_issues: Mapping[tuple[int, int], Sequence[str]] | None = None,
    error_count: int = 0,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Construye un informe apto para copiar en una incidencia pública.

    No incluye nombres/rutas de PDF, GRUP, CURS, TUTOR, nombres de alumnado ni NIA.
    Los mensajes de incidencia se filtran mediante una lista de mensajes internos
    conocidos antes de incorporarlos.
    """
    class_issues = class_issues or {}
    environment = environment or {}

    lines = [
        f"ITACA → iDoceo {__version__}",
        "Diagnóstico anonimizado",
        "",
        "No incluye nombres ni rutas de archivos, centro, GRUP, CURS, TUTOR, "
        "nombres de alumnado ni NIA.",
    ]

    if environment:
        lines.extend(["", "Entorno:"])
        for key in ("Sistema", "Arquitectura", "Python", "Tcl", "Tk", "Drag and drop"):
            value = environment.get(key)
            if value:
                lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            f"PDF analizados correctamente: {len(results)}",
            f"PDF con error de procesamiento: {error_count}",
        ]
    )

    for pdf_index, result in enumerate(results, start=1):
        lines.extend(
            [
                "",
                f"PDF {pdf_index}:",
                f"- Páginas: {result.page_count}",
                f"- Firma ITACA 3: {'detectada' if result.report_signature else 'no detectada'}",
                f"- Páginas con firma: {len(result.signature_pages)}",
                f"- Grupos/clases reconstruidos: {len(result.classes)}",
            ]
        )

        pdf_issues = [_safe_issue(issue) for issue in result.issues]
        if pdf_issues:
            lines.append("- Incidencias del PDF:")
            lines.extend(f"  - {issue}" for issue in pdf_issues)

        for class_index, cls in enumerate(result.classes, start=1):
            issues = list(class_issues.get((pdf_index, class_index), cls.issues))
            safe_issues = [_safe_issue(issue) for issue in issues]
            lines.extend(
                [
                    f"- Clase {class_index}:",
                    f"  - Alumnos detectados: {len(cls.students)}",
                    f"  - Secciones CURS detectadas: {len(cls.course_values)}",
                    f"  - TUTOR presente: {'sí' if cls.metadata.tutor else 'no'}",
                    f"  - Estado: {'Revisar' if safe_issues else 'Correcto'}",
                ]
            )
            if safe_issues:
                lines.append("  - Incidencias:")
                lines.extend(f"    - {issue}" for issue in safe_issues)

    return "\n".join(lines) + "\n"
