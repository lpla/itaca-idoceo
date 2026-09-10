from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import batch_extract, check_pdf, extract_one
from .integrations import install_integration, uninstall_integration


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
    extract.add_argument("-o", "--output", type=Path, default=None, help="XLSX de salida si hay una clase; carpeta de salida si hay varias")
    extract.add_argument(
        "--include-nia",
        action="store_true",
        help="Incluye NIA para mapearlo al campo ID/Student ID de iDoceo.",
    )

    batch = subparsers.add_parser(
        "batch",
        help="Convierte todos los PDF de una carpeta, un XLSX por grupo.",
    )
    batch.add_argument("folder", type=Path)
    batch.add_argument("-o", "--output-dir", type=Path, default=None)
    batch.add_argument("-r", "--recursive", action="store_true")
    batch.add_argument("--include-nia", action="store_true")

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


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Sin argumentos: comportamiento pensado para usuario final.
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
        )

    if args.command == "batch":
        return batch_extract(
            input_dir=args.folder,
            output_dir=args.output_dir,
            recursive=args.recursive,
            include_nia=args.include_nia,
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

    parser.error("comando no reconocido")
    return 2
