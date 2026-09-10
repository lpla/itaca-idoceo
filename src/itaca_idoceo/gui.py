from __future__ import annotations

import os
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Tkinter no está disponible en esta instalación de Python."
    ) from exc

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError as exc:  # pragma: no cover
    DND_FILES = None
    TkinterDnD = None
    TKINTERDND_IMPORT_ERROR: Exception | None = exc
else:
    TKINTERDND_IMPORT_ERROR = None

from . import __version__
from .core import (
    ClassResult,
    PdfResult,
    process_pdf,
    safe_filename_component,
    unique_output_path,
    write_idoceo_xlsx,
)
from .diagnostics import build_anonymized_diagnostic


class ItacaIdoceoApp(tk.Tk):
    def __init__(self, initial_paths: list[str] | None = None):
        super().__init__()

        self.dnd_available = False
        self.dnd_error: str | None = None
        self._enable_drag_and_drop()

        self.title(f"ITACA → iDoceo {__version__}")
        self.geometry("980x620")
        self.minsize(820, 500)

        self.results: dict[Path, PdfResult] = {}
        self.errors: dict[Path, str] = {}
        # Tree row -> (PDF, índice de clase). None representa una fila de error.
        self.row_map: dict[str, tuple[Path, int | None]] = {}
        self.last_output_dir: Path | None = None
        self.include_nia = tk.BooleanVar(value=False)
        self.include_repetix = tk.BooleanVar(value=False)
        self.include_materia = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value=self._empty_status_text())

        self._build_ui()

        if initial_paths:
            self.after(50, lambda: self.add_paths(initial_paths))

    def _enable_drag_and_drop(self) -> None:
        if TkinterDnD is None:
            self.dnd_error = f"tkinterdnd2 no disponible: {TKINTERDND_IMPORT_ERROR}"
            return
        try:
            TkinterDnD.require(self)
        except Exception as exc:
            self.dnd_error = f"{type(exc).__name__}: {exc}"
            return
        self.dnd_available = True

    def _empty_status_text(self) -> str:
        return (
            "Arrastra o haz clic para añadir listados de ITACA."
            if self.dnd_available
            else "Haz clic en el área superior para añadir PDF o una carpeta."
        )

    def _dnd_technical_text(self) -> str:
        try:
            tcl = self.tk.call("info", "patchlevel")
        except Exception:
            tcl = "desconocido"
        try:
            tk_version = self.tk.call("package", "provide", "Tk")
        except Exception:
            tk_version = "desconocido"

        state = "Disponible" if self.dnd_available else "No disponible"
        detail = f"\nMotivo: {self.dnd_error}" if self.dnd_error else ""
        return (
            f"Arrastrar y soltar: {state}\n"
            f"Python: {platform.python_version()}\n"
            f"Tcl: {tcl}\nTk: {tk_version}{detail}"
        )

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self._build_menu()

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="ITACA → iDoceo",
            font=("TkDefaultFont", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Convierte listados PDF de alumnado exportados por ITACA en XLSX "
                "para iDoceo. Todo se procesa localmente en este ordenador."
            ),
            wraplength=930,
        ).pack(anchor="w", pady=(4, 12))

        if self.dnd_available:
            drop_text = (
                "ARRASTRA AQUÍ PDF O UNA CARPETA\n"
                "o haz clic para elegir PDF o carpeta"
            )
        else:
            drop_text = "HAZ CLIC AQUÍ PARA AÑADIR PDF O UNA CARPETA"

        self.drop_area = tk.Label(
            outer,
            text=drop_text,
            justify="center",
            relief="groove",
            borderwidth=2,
            padx=20,
            pady=24,
            cursor="hand2",
        )
        self.drop_area.pack(fill="x", pady=(0, 12))

        if self.dnd_available and DND_FILES is not None:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self._on_drop)

        self.drop_area.bind("<Button-1>", self._show_add_menu)
        self.drop_area.bind("<Return>", lambda _event: self._show_add_menu())
        self.drop_area.configure(takefocus=True)

        self.add_menu = tk.Menu(self, tearoff=False)
        self.add_menu.add_command(label="Uno o varios PDF…", command=self.choose_pdfs)
        self.add_menu.add_command(label="Una carpeta…", command=self.choose_folder)

        export_options = ttk.Frame(outer)
        export_options.pack(fill="x", pady=(0, 10))
        ttk.Label(export_options, text="Datos opcionales en el XLSX:").pack(side="left")
        ttk.Checkbutton(
            export_options,
            text="NIA (ID del estudiante)",
            variable=self.include_nia,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            export_options,
            text="REPETIX",
            variable=self.include_repetix,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            export_options,
            text="MATÈRIA / MÒDUL",
            variable=self.include_materia,
        ).pack(side="left", padx=(12, 0))

        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)

        columns = ("file", "group", "course", "students", "status")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("file", text="PDF")
        self.tree.heading("group", text="Grupo")
        self.tree.heading("course", text="Curso")
        self.tree.heading("students", text="Alumnos")
        self.tree.heading("status", text="Estado")

        self.tree.column("file", width=260, minwidth=150)
        self.tree.column("group", width=110, anchor="center")
        self.tree.column("course", width=290, minwidth=120)
        self.tree.column("students", width=75, anchor="center")
        self.tree.column("status", width=95, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda _event: self.show_details())
        self.tree.bind("<Delete>", lambda _event: self.remove_selected())
        self.tree.bind("<BackSpace>", lambda _event: self.remove_selected())
        self.tree.bind("<Button-2>", self._show_tree_context_menu)
        self.tree.bind("<Button-3>", self._show_tree_context_menu)

        self.progress_holder = ttk.Frame(outer)
        self.progress_holder.pack(fill="x")
        self.progress = ttk.Progressbar(self.progress_holder, mode="indeterminate")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status_text).grid(row=0, column=0, sticky="w")

        self.open_button = ttk.Button(
            bottom,
            text="Abrir carpeta",
            command=self.open_last_output,
        )

        self.convert_button = ttk.Button(
            bottom,
            text="Convertir para iDoceo",
            command=self.convert,
            state="disabled",
        )
        self.convert_button.grid(row=0, column=2, sticky="e")

        self.tree_menu = tk.Menu(self, tearoff=False)
        self.tree_menu.add_command(label="Detalles", command=self.show_details)
        self.tree_menu.add_command(label="Quitar PDF de la lista", command=self.remove_selected)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Añadir PDF…", command=self.choose_pdfs)
        file_menu.add_command(label="Añadir carpeta…", command=self.choose_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Vaciar lista", command=self.clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Cómo importar en iDoceo…", command=self.show_import_help)
        help_menu.add_separator()
        help_menu.add_command(
            label="Copiar diagnóstico anonimizado",
            command=self.copy_anonymized_diagnostic,
        )
        help_menu.add_command(label="Detalles técnicos…", command=self.show_technical_details)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        self.configure(menu=menubar)

    # ---------------------------------------------------------- Entrada/DnD

    def _show_add_menu(self, event=None) -> str:
        """Muestra junto al área principal las dos fuentes posibles de entrada."""
        if event is not None:
            x = event.x_root
            y = event.y_root
        else:
            x = self.drop_area.winfo_rootx() + self.drop_area.winfo_width() // 2
            y = self.drop_area.winfo_rooty() + self.drop_area.winfo_height() // 2
        try:
            self.add_menu.tk_popup(x, y)
        finally:
            self.add_menu.grab_release()
        return "break"

    def _on_drop(self, event) -> str:
        try:
            paths = list(self.tk.splitlist(event.data))
        except Exception:
            paths = [str(event.data)]
        self.add_paths(paths)
        return getattr(event, "action", "copy")

    def choose_pdfs(self) -> None:
        filenames = filedialog.askopenfilenames(
            title="Selecciona los PDF exportados por ITACA",
            filetypes=[("Documentos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if filenames:
            self.add_paths(list(filenames))

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta con PDF de ITACA")
        if folder:
            self.add_paths([folder])

    def _collect_pdfs(self, paths: list[str]) -> list[Path]:
        pdfs: set[Path] = set()
        for raw in paths:
            path = Path(raw).expanduser()
            if path.is_file() and path.suffix.casefold() == ".pdf":
                pdfs.add(path.resolve())
            elif path.is_dir():
                pdfs.update(pdf.resolve() for pdf in path.rglob("*.pdf") if pdf.is_file())
        return sorted(pdfs, key=lambda path: str(path).casefold())

    def _remove_rows_for_pdf(self, pdf: Path) -> None:
        for iid, (row_pdf, _index) in list(self.row_map.items()):
            if row_pdf == pdf:
                if self.tree.exists(iid):
                    self.tree.delete(iid)
                self.row_map.pop(iid, None)

    def _insert_result_rows(self, pdf: Path, result: PdfResult) -> None:
        self._remove_rows_for_pdf(pdf)
        for index, cls in enumerate(result.classes):
            iid = f"{pdf}::class::{index}"
            self.row_map[iid] = (pdf, index)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(pdf.name, cls.metadata.group_code or "—", cls.metadata.course or "—", len(cls.students), "…"),
            )

    def add_paths(self, paths: list[str]) -> None:
        pdfs = self._collect_pdfs(paths)
        if not pdfs:
            messagebox.showwarning(
                "ITACA → iDoceo",
                "No se ha encontrado ningún archivo PDF en la selección.",
                parent=self,
            )
            return

        self._busy(True)
        try:
            for pdf in pdfs:
                if pdf in self.results or pdf in self.errors:
                    continue
                try:
                    result = process_pdf(pdf)
                    if not result.classes:
                        raise RuntimeError("No se ha detectado ninguna clase")
                    self.results[pdf] = result
                    self.errors.pop(pdf, None)
                    self._insert_result_rows(pdf, result)
                except Exception as exc:
                    self.errors[pdf] = str(exc)
                    iid = f"{pdf}::error"
                    self.row_map[iid] = (pdf, None)
                    self.tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(pdf.name, "—", "—", "0", "Error"),
                    )
            self._recalculate_statuses()
        finally:
            self._busy(False)

        self._refresh_controls()
        self._update_summary()

    # ------------------------------------------------------------- Validación

    def _all_classes(self):
        for pdf, result in self.results.items():
            for index, cls in enumerate(result.classes):
                yield pdf, index, cls, result

    def _group_counts(self) -> Counter[str]:
        return Counter(
            cls.metadata.group_code.casefold()
            for _pdf, _index, cls, _result in self._all_classes()
            if cls.metadata.group_code
        )

    def _issues_for_class(self, pdf: Path, index: int) -> list[str]:
        result = self.results[pdf]
        cls = result.classes[index]
        issues = list(result.issues) + list(cls.issues)
        group = cls.metadata.group_code
        if group and self._group_counts()[group.casefold()] > 1:
            issues.append("Hay más de un grupo cargado con el mismo código")
        return issues

    def _recalculate_statuses(self) -> None:
        for pdf, index, cls, _result in self._all_classes():
            iid = f"{pdf}::class::{index}"
            issues = self._issues_for_class(pdf, index)
            self.tree.item(
                iid,
                values=(
                    pdf.name,
                    cls.metadata.group_code or "—",
                    cls.metadata.course or "—",
                    len(cls.students),
                    "Revisar" if issues else "Correcto",
                ),
            )

    def _update_summary(self) -> None:
        classes = list(self._all_classes())
        review = sum(bool(self._issues_for_class(pdf, index)) for pdf, index, _cls, _r in classes)
        correct = len(classes) - review
        errors = len(self.errors)

        parts = []
        if correct:
            parts.append(f"{correct} correcto(s)")
        if review:
            parts.append(f"{review} para revisar")
        if errors:
            parts.append(f"{errors} con error")
        self.status_text.set(" · ".join(parts) if parts else self._empty_status_text())

    # -------------------------------------------------------------- Acciones

    def _show_tree_context_menu(self, event) -> str:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return "break"
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        try:
            self.tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_menu.grab_release()
        return "break"

    def show_details(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return

        iid = selection[0]
        mapping = self.row_map.get(iid)
        if mapping is None:
            return
        pdf, index = mapping

        if index is None:
            detail = self.errors.get(pdf, "Error desconocido")
            messagebox.showerror("Detalles del listado", f"PDF: {pdf.name}\n\n{detail}", parent=self)
            return

        result = self.results[pdf]
        cls = result.classes[index]
        issues = self._issues_for_class(pdf, index)
        validation = "Correcto" if not issues else "Revisar:\n- " + "\n- ".join(issues)

        extra = ""
        if len(result.classes) > 1:
            extra = f"Clase dentro del PDF: {index + 1} de {len(result.classes)}\n"

        course_values = cls.course_values
        if len(course_values) > 1:
            course_detail = (
                f"Curso mostrado: {cls.metadata.course or 'No detectado'}\n"
                f"Secciones CURS: {len(course_values)}\n"
                + "".join(f"  • {value}\n" for value in course_values)
            )
        else:
            course_detail = f"Curso: {cls.metadata.course or 'No detectado'}\n"

        messagebox.showinfo(
            "Detalles del listado",
            (
                f"PDF: {pdf.name}\n{extra}"
                f"Grupo: {cls.metadata.group_code or 'No detectado'}\n"
                f"{course_detail}"
                f"Tutor: {cls.metadata.tutor or 'No indicado'}\n"
                f"Alumnos: {len(cls.students)}\n\n"
                f"Validación: {validation}"
            ),
            parent=self,
        )

    def _diagnostic_environment(self) -> dict[str, str]:
        try:
            tcl = str(self.tk.call("info", "patchlevel"))
        except Exception:
            tcl = "desconocido"
        try:
            tk_version = str(self.tk.call("package", "provide", "Tk"))
        except Exception:
            tk_version = "desconocido"
        return {
            "Sistema": f"{platform.system()} {platform.release()}",
            "Arquitectura": platform.machine() or "desconocida",
            "Python": platform.python_version(),
            "Tcl": tcl,
            "Tk": tk_version,
            "Drag and drop": "disponible" if self.dnd_available else "no disponible",
        }

    def copy_anonymized_diagnostic(self) -> None:
        results = list(self.results.values())
        extra: dict[tuple[int, int], list[str]] = {}
        for pdf_index, (pdf, result) in enumerate(self.results.items(), start=1):
            for class_index, _cls in enumerate(result.classes, start=1):
                extra[(pdf_index, class_index)] = self._issues_for_class(
                    pdf, class_index - 1
                )

        diagnostic = build_anonymized_diagnostic(
            results,
            class_issues=extra,
            error_count=len(self.errors),
            environment=self._diagnostic_environment(),
        )
        self.clipboard_clear()
        self.clipboard_append(diagnostic)
        self.update_idletasks()
        messagebox.showinfo(
            "Diagnóstico copiado",
            (
                "Se ha copiado un diagnóstico preparado para compartir.\n\n"
                "No contiene nombres/rutas de archivos, centro, grupo, curso, tutor, "
                "nombres del alumnado ni NIA."
            ),
            parent=self,
        )

    def show_technical_details(self) -> None:
        messagebox.showinfo(
            "Detalles técnicos",
            f"ITACA → iDoceo {__version__}\n\n{self._dnd_technical_text()}",
            parent=self,
        )

    def show_import_help(self) -> None:
        messagebox.showinfo(
            "Importar el XLSX en iDoceo",
            (
                "En el asistente de importación de iDoceo:\n\n"
                "1. Selecciona la primera fila como cabecera.\n"
                "2. En la composición del nombre, asigna Nombre y Apellidos.\n"
                "3. Si has incluido el NIA, asígnalo a ID / Student ID.\n"
                "4. Si incluyes REPETIX o MATÈRIA / MÒDUL, decide explícitamente dónde quieres importarlos; "
                "no los dejes seleccionados accidentalmente como columnas de notas.\n"
                "5. Comprueba que no haya columnas no deseadas seleccionadas como datos del cuaderno.\n"
                "6. Crea una clase nueva o añade los alumnos a una existente."
            ),
            parent=self,
        )

    def remove_selected(self) -> None:
        paths: set[Path] = set()
        for iid in self.tree.selection():
            mapping = self.row_map.get(iid)
            if mapping:
                paths.add(mapping[0])

        for pdf in paths:
            self.results.pop(pdf, None)
            self.errors.pop(pdf, None)
            self._remove_rows_for_pdf(pdf)

        self._recalculate_statuses()
        self._refresh_controls()
        self._update_summary()

    def clear_all(self) -> None:
        self.results.clear()
        self.errors.clear()
        self.row_map.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.last_output_dir = None
        self.open_button.grid_remove()
        self._refresh_controls()
        self._update_summary()

    def _refresh_controls(self) -> None:
        has_classes = any(result.classes for result in self.results.values())
        self.convert_button.configure(state="normal" if has_classes else "disabled")

    def _busy(self, active: bool) -> None:
        if active:
            self.configure(cursor="watch")
            self.progress.pack(fill="x", pady=(8, 0))
            self.progress.start(10)
            self.convert_button.configure(state="disabled")
        else:
            self.configure(cursor="")
            self.progress.stop()
            self.progress.pack_forget()
            self._refresh_controls()
        self.update_idletasks()

    # --------------------------------------------------------------- Conversión

    def _default_output_dir(self) -> Path | None:
        parents = {path.parent for path in self.results}
        return next(iter(parents)) / "iDoceo" if len(parents) == 1 else None

    def _choose_output_dir(self) -> Path | None:
        default = self._default_output_dir()
        if default is not None:
            return default
        folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar los XLSX de iDoceo")
        return Path(folder) if folder else None

    def convert(self) -> None:
        classes = list(self._all_classes())
        if not classes:
            return

        review = [
            (pdf, index)
            for pdf, index, _cls, _result in classes
            if self._issues_for_class(pdf, index)
        ]
        if review:
            proceed = messagebox.askyesno(
                "Hay clases para revisar",
                (
                    f"Hay {len(review)} clase(s) marcada(s) como 'Revisar'.\n\n"
                    "Haz doble clic sobre una fila para ver las incidencias. "
                    "¿Quieres convertirlas de todas formas?"
                ),
                parent=self,
            )
            if not proceed:
                return

        output_dir = self._choose_output_dir()
        if output_dir is None:
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        self._busy(True)

        created: list[Path] = []
        failures: list[str] = []

        try:
            for pdf, _index, cls, _result in classes:
                group = cls.metadata.group_code or pdf.stem
                output_path = unique_output_path(
                    output_dir,
                    safe_filename_component(group) + "_idoceo",
                )
                try:
                    write_idoceo_xlsx(
                        cls,
                        output_path,
                        self.include_nia.get(),
                        self.include_repetix.get(),
                        self.include_materia.get(),
                    )
                    created.append(output_path)
                except Exception as exc:
                    failures.append(f"{pdf.name} [{group}]: {exc}")
        finally:
            self._busy(False)

        self.last_output_dir = output_dir
        self.open_button.grid(row=0, column=1, sticky="e", padx=(8, 8))
        total_students = sum(len(cls.students) for _p, _i, cls, _r in classes)

        if failures:
            self.status_text.set(f"{len(created)} archivo(s) creados; {len(failures)} error(es).")
            messagebox.showwarning(
                "Conversión terminada con incidencias",
                f"Se han creado {len(created)} XLSX.\n\n" + "\n".join(failures[:8]),
                parent=self,
            )
        else:
            self.status_text.set(
                f"Conversión completada: {len(created)} clase(s), {total_students} alumno(s)."
            )
            messagebox.showinfo(
                "Conversión completada",
                (
                    f"{len(created)} archivo(s) XLSX creados.\n"
                    f"{total_students} alumno(s) procesados.\n\n"
                    f"Carpeta: {output_dir}"
                ),
                parent=self,
            )

    def open_last_output(self) -> None:
        if self.last_output_dir:
            open_folder(self.last_output_dir)


def open_folder(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        raise RuntimeError(f"No se ha podido abrir la carpeta: {exc}") from exc


def main(initial_paths: list[str] | None = None) -> int:
    try:
        app = ItacaIdoceoApp(initial_paths=initial_paths)
        app.mainloop()
        return 0
    except (tk.TclError, RuntimeError) as exc:
        print(
            "ERROR: no se ha podido iniciar la interfaz gráfica de Tk.\n"
            f"Detalle: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
