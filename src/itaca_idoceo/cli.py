from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import batch_extract, check_pdf, extract_one
from .integrations import install_integration, uninstall_integration
from .photo_export import export_photo_roster_cli
from .photo_reference_pool import check_photo_roster_with_references
from .photo_roster import check_photo_roster


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="itaca-idoceo",
        description=(
            "Convierte localmente listados PDF de alumnado de ITACA "
            "en XLSX preparados para importar en iDoceo."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser(
        "check",
        help="Comprueba grupo, curso y alumnado sin mostrar nombres ni NIA.",
    )
    check.add_argument("pdf", type=Path)

    extract = subparsers.add_parser(
        "extract",
        help="Convierte un PDF en uno o varios XLSX (uno por grupo).",
    )
    extract.add_argument("pdf", type=Path)
    extract.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="XLSX de salida si hay una clase; carpeta de salida si hay varias",
    )
    extract.add_argument(
        "--include-nia",
        action="store_true",
        help="Incluye NIA para mapearlo al campo ID/Student ID de iDoceo.",
    )
    extract.add_argument(
        "--include-repetix",
        action="store_true",
        help="Incluye la columna REPETIX tal como aparece en ITACA.",
    )
    extract.add_argument(
        "--include-materia",
        action="store_true",
        help="Incluye la columna MATÈRIA tal como aparece en ITACA.",
    )

    batch = subparsers.add_parser(
        "batch",
        help="Convierte todos los PDF de una carpeta, un XLSX por grupo.",
    )
    batch.add_argument("folder", type=Path)
    batch.add_argument("-o", "--output-dir", type=Path, default=None)
    batch.add_argument("-r", "--recursive", action="store_true")
    batch.add_argument("--include-nia", action="store_true")
    batch.add_argument("--include-repetix", action="store_true")
    batch.add_argument("--include-materia", action="store_true")

    integrate = subparsers.add_parser(
        "integrate",
        help="Instala accesos gráficos locales para el sistema operativo.",
    )
    integrate.add_argument(
        "--replace",
        action="store_true",
        help="Sustituye una integración anterior creada por la herramienta.",
    )

    subparsers.add_parser(
        "uninstall-integration",
        help="Elimina los accesos gráficos creados por 'integrate'.",
    )

    layout = subparsers.add_parser(
        "layout-report",
        help="Genera un informe geométrico anonimizado para depurar formatos PDF.",
    )
    layout.add_argument("pdf", type=Path)
    layout.add_argument(
        "--orde",
        type=int,
        action="append",
        default=None,
        help="Limita el informe a una o varias filas ORDE (se puede repetir).",
    )
    layout.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fichero de texto de salida; si se omite, se imprime por pantalla.",
    )

    photo_layout = subparsers.add_parser(
        "photo-layout-report",
        help="Genera un informe anonimizado de texto e imágenes para listados con fotos.",
    )
    photo_layout.add_argument("pdf", type=Path)
    photo_layout.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fichero de texto de salida; si se omite, se imprime por pantalla.",
    )

    photo_check = subparsers.add_parser(
        "photo-check",
        help=(
            "Comprueba de forma anónima el emparejamiento foto/nombre de un "
            "listado con fotos."
        ),
    )
    photo_check.add_argument("pdf", type=Path)
    photo_check.add_argument(
        "--reference-pdf",
        type=Path,
        action="append",
        default=[],
        help=(
            "PDF tabular ya soportado que se usará como referencia. Puede "
            "repetirse para aportar varios PDF."
        ),
    )
    photo_check.add_argument(
        "--reference-folder",
        type=Path,
        default=None,
        help=(
            "Carpeta con PDF de referencia. Se buscan PDF recursivamente y "
            "se ignoran los que no tengan el formato tabular soportado."
        ),
    )

    photo_export = subparsers.add_parser(
        "photo-export",
        help="Extrae alumnado y fotos de un listado fotográfico para iDoceo.",
    )
    photo_export.add_argument("pdf", type=Path)
    photo_export.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Carpeta de salida. Si se omite, se crea junto al PDF.",
    )
    photo_export.add_argument(
        "--reference-pdf",
        type=Path,
        action="append",
        default=[],
        help=(
            "PDF tabular ya soportado para enriquecer el alumnado con NIA y "
            "otros campos. Puede repetirse para aportar varios PDF."
        ),
    )
    photo_export.add_argument(
        "--reference-folder",
        type=Path,
        default=None,
        help=(
            "Carpeta con PDF tabulares de referencia. Se buscan PDF "
            "recursivamente y se ignoran los formatos no soportados."
        ),
    )
    photo_export.add_argument(
        "--include-repetix",
        action="store_true",
        help="Incluye REPETIX obtenido de las referencias tabulares.",
    )
    photo_export.add_argument(
        "--include-materia",
        action="store_true",
        help="Incluye MATÈRIA/MÒDUL obtenido de las referencias tabulares.",
    )

    return parser


def _launch_gui(paths: list[str] | None = None) -> int:
    try:
        from .gui import main as gui_main
    except Exception as exc:
        print(
            "ERROR: no se ha podido cargar la interfaz gráfica.\n"
            "Comprueba que Tkinter esté instalado.\n"
            f"Detalle: {exc}",
            file=sys.stderr,
        )
        return 1
    return gui_main(paths or [])


def _collect_reference_pdfs(
    explicit: list[Path],
    folder: Path | None,
    source_pdf: Path,
    parser: argparse.ArgumentParser,
) -> list[Path]:
    paths: list[Path] = []

    for path in explicit:
        if not path.is_file():
            parser.error(f"no existe el fichero de referencia: {path}")
        paths.append(path.resolve())

    if folder is not None:
        if not folder.is_dir():
            parser.error(f"no existe la carpeta de referencias: {folder}")
        paths.extend(
            path.resolve()
            for path in folder.rglob("*.pdf")
            if path.is_file()
        )

    source_resolved = source_pdf.resolve()
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path == source_resolved or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        return _launch_gui()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        return _launch_gui()

    if args.command == "check":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        return check_pdf(args.pdf)

    if args.command == "extract":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        return extract_one(
            pdf_path=args.pdf,
            output_path=args.output,
            include_nia=args.include_nia,
            include_repetix=args.include_repetix,
            include_materia=args.include_materia,
        )

    if args.command == "batch":
        return batch_extract(
            input_dir=args.folder,
            output_dir=args.output_dir,
            recursive=args.recursive,
            include_nia=args.include_nia,
            include_repetix=args.include_repetix,
            include_materia=args.include_materia,
        )

    if args.command == "integrate":
        try:
            created = install_integration(replace=args.replace)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for item in created:
            print(f"Creado: {item}")
        return 0

    if args.command == "uninstall-integration":
        removed = uninstall_integration()
        if removed:
            for item in removed:
                print(f"Eliminado: {item}")
        else:
            print("No se encontró ninguna integración creada por la herramienta.")
        return 0

    if args.command == "layout-report":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        from .layout_debug import build_layout_report

        report = build_layout_report(
            args.pdf,
            only_ordinals=set(args.orde) if args.orde else None,
        )
        if args.output is None:
            print(report, end="")
        else:
            args.output.write_text(report, encoding="utf-8")
            print("Informe anonimizado guardado.")
        return 0

    if args.command == "photo-layout-report":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        from .photo_layout_debug import build_photo_layout_report

        report = build_photo_layout_report(args.pdf)
        if args.output is None:
            print(report, end="")
        else:
            args.output.write_text(report, encoding="utf-8")
            print("Informe anonimizado de listado con fotos guardado.")
        return 0

    if args.command == "photo-check":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        references = _collect_reference_pdfs(
            args.reference_pdf,
            args.reference_folder,
            args.pdf,
            parser,
        )
        if not references:
            return check_photo_roster(args.pdf)
        return check_photo_roster_with_references(args.pdf, references)

    if args.command == "photo-export":
        if not args.pdf.is_file():
            parser.error(f"no existe el fichero: {args.pdf}")
        references = _collect_reference_pdfs(
            args.reference_pdf,
            args.reference_folder,
            args.pdf,
            parser,
        )
        return export_photo_roster_cli(
            args.pdf,
            args.output_dir,
            reference_pdfs=references,
            include_repetix=args.include_repetix,
            include_materia=args.include_materia,
        )

    parser.error("comando no reconocido")
    return 2
