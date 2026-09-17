from __future__ import annotations

import os
import platform
import subprocess
import sys
import webbrowser
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
from .selection_export import (
    SelectionAnalysis,
    analyze_selection,
    collect_pdf_paths,
    export_analyzed_selection,
)


AUTHOR_NAME = "Leopoldo Pla Sempere"
PORTFOLIO_URL = "https://lpla.github.io"
REPOSITORY_URL = "https://github.com/lpla/itaca-idoceo"
ISSUES_URL = "https://github.com/lpla/itaca-idoceo/issues/new"


class ItacaIdoceoApp(tk.Tk):
    """Interfaz de selección única para referencias y listados actuales con fotos."""

    def __init__(self, initial_paths: list[str] | None = None):
        super().__init__()

        self.dnd_available = False
        self.dnd_error: str | None = None
        self._enable_drag_and_drop()

        self.title(f"ITACA → iDoceo {__version__}")
        self.geometry("1040x650")
        self.minsize(860, 520)

        self.input_pdfs: set[Path] = set()
        self.analysis = SelectionAnalysis(pdfs=[])
        self.row_map: dict[str, Path] = {}
        self.last_output_dir: Path | None = None

        # En el flujo nuevo el NIA es el identificador recomendado desde el
        # principio. Con listados actuales con fotos se usa automáticamente.
        self.include_nia = tk.BooleanVar(value=True)
        self.include_repetix = tk.BooleanVar(value=False)
        self.include_materia = tk.BooleanVar(value=False)
        self.nia_text = tk.StringVar(value="NIA (ID del estudiante, recomendado)")
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
        if self.dnd_available:
            return "Añade juntos todos los PDF de ITACA que tengas disponibles."
        return "Haz clic arriba para añadir todos los PDF de ITACA que tengas disponibles."

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
                "Añade en una sola selección los listados de referencia del centro y, "
                "si ya los tienes, los listados actuales con fotos de tus materias. "
                "La herramienta detecta cada formato y prepara toda la exportación de una vez. "
                "Todo se procesa localmente en este ordenador."
            ),
            wraplength=990,
        ).pack(anchor="w", pady=(4, 12))

        drop_text = (
            "ARRASTRA AQUÍ TODOS LOS PDF O UNA CARPETA\n"
            "o haz clic para elegir PDF o carpeta"
            if self.dnd_available
            else "HAZ CLIC AQUÍ PARA AÑADIR TODOS LOS PDF O UNA CARPETA"
        )
        self.drop_area = tk.Label(
            outer,
            text=drop_text,
            justify="center",
            relief="groove",
            borderwidth=2,
            padx=20,
            pady=24,
            cursor="hand2",
            takefocus=True,
        )
        self.drop_area.pack(fill="x", pady=(0, 12))
        self.drop_area.bind("<Button-1>", self._show_add_menu)
        self.drop_area.bind("<Return>", lambda _event: self._show_add_menu())

        if self.dnd_available and DND_FILES is not None:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self._on_drop)

        self.add_menu = tk.Menu(self, tearoff=False)
        self.add_menu.add_command(label="Uno o varios PDF…", command=self.choose_pdfs)
        self.add_menu.add_command(label="Una carpeta…", command=self.choose_folder)

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=(0, 10))
        ttk.Label(options, text="Datos en los XLSX:").pack(side="left")
        self.nia_check = ttk.Checkbutton(
            options,
            textvariable=self.nia_text,
            variable=self.include_nia,
        )
        self.nia_check.pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            options,
            text="REPETIX",
            variable=self.include_repetix,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            options,
            text="MATÈRIA / MÒDUL",
            variable=self.include_materia,
        ).pack(side="left", padx=(12, 0))

        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)

        columns = ("file", "kind", "detail", "students", "status")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("file", text="PDF")
        self.tree.heading("kind", text="Tipo detectado")
        self.tree.heading("detail", text="Contenido")
        self.tree.heading("students", text="Alumnos")
        self.tree.heading("status", text="Estado")
        self.tree.column("file", width=280, minwidth=160)
        self.tree.column("kind", width=165, anchor="center")
        self.tree.column("detail", width=300, minwidth=150)
        self.tree.column("students", width=75, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda _event: self.show_details())
        self.tree.bind("<Delete>", lambda _event: self.remove_selected())
        self.tree.bind("<BackSpace>", lambda _event: self.remove_selected())

        self.progress = ttk.Progressbar(outer, mode="indeterminate")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_text).grid(row=0, column=0, sticky="w")

        self.open_button = ttk.Button(
            bottom,
            text="Abrir carpeta",
            command=self.open_last_output,
        )
        self.remove_button = ttk.Button(
            bottom,
            text="Quitar seleccionados",
            command=self.remove_selected,
            state="disabled",
        )
        self.remove_button.grid(row=0, column=1, sticky="e", padx=(8, 8))

        self.convert_button = ttk.Button(
            bottom,
            text="Preparar todo para iDoceo",
            command=self.convert,
            state="disabled",
        )
        self.convert_button.grid(row=0, column=3, sticky="e")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._refresh_controls())

        credits = ttk.Frame(outer)
        credits.pack(fill="x", pady=(8, 0))
        ttk.Label(credits, text=f"Desarrollado por {AUTHOR_NAME} · ").pack(side="left")
        portfolio_link = ttk.Label(credits, text="Portfolio", cursor="hand2")
        portfolio_link.pack(side="left")
        portfolio_link.bind("<Button-1>", lambda _event: self._open_url(PORTFOLIO_URL))
        ttk.Label(credits, text=" · ").pack(side="left")
        github_link = ttk.Label(credits, text="GitHub", cursor="hand2")
        github_link.pack(side="left")
        github_link.bind("<Button-1>", lambda _event: self._open_url(REPOSITORY_URL))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Añadir PDF…", command=self.choose_pdfs)
        file_menu.add_command(label="Añadir carpeta…", command=self.choose_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Quitar seleccionados", command=self.remove_selected)
        file_menu.add_command(label="Vaciar lista", command=self.clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Cómo funciona la selección…", command=self.show_workflow_help)
        help_menu.add_separator()
        help_menu.add_command(
            label="Copiar diagnóstico anonimizado",
            command=self.copy_anonymized_diagnostic,
        )
        help_menu.add_command(label="Detalles técnicos…", command=self.show_technical_details)
        help_menu.add_separator()
        help_menu.add_command(
            label="Informar de un problema en GitHub…",
            command=lambda: self._open_url(ISSUES_URL),
        )
        help_menu.add_command(
            label="Proyecto en GitHub…",
            command=lambda: self._open_url(REPOSITORY_URL),
        )
        help_menu.add_command(
            label=f"Portfolio de {AUTHOR_NAME}…",
            command=lambda: self._open_url(PORTFOLIO_URL),
        )
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        self.configure(menu=menubar)

    def _open_url(self, url: str) -> None:
        try:
            opened = webbrowser.open(url, new=2)
        except Exception as exc:
            messagebox.showerror(
                "No se ha podido abrir el enlace",
                f"No se ha podido abrir el navegador.\n\n{exc}",
                parent=self,
            )
            return
        if not opened:
            messagebox.showwarning(
                "No se ha podido abrir el enlace",
                "El sistema no ha confirmado la apertura del navegador.",
                parent=self,
            )

    # ---------------------------------------------------------- Entrada/DnD

    def _show_add_menu(self, event=None) -> str:
        if event is not None:
            x, y = event.x_root, event.y_root
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
            title="Selecciona todos los PDF de ITACA que quieras usar",
            filetypes=[("Documentos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if filenames:
            self.add_paths(list(filenames))

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Selecciona una carpeta con los PDF de ITACA"
        )
        if folder:
            self.add_paths([folder])

    def add_paths(self, paths: list[str]) -> None:
        found = collect_pdf_paths([Path(raw) for raw in paths])
        if not found:
            messagebox.showwarning(
                "ITACA → iDoceo",
                "No se ha encontrado ningún archivo PDF en la selección.",
                parent=self,
            )
            return

        self.input_pdfs.update(found)
        self._reanalyze()

    def _reanalyze(self) -> None:
        self._busy(True)
        try:
            self.analysis = analyze_selection(sorted(self.input_pdfs))
            self._rebuild_tree()
        finally:
            self._busy(False)
        self._refresh_controls()
        self._update_summary()

    def _rebuild_tree(self) -> None:
        self.row_map.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for pdf, result in self.analysis.references.items():
            groups = len(result.classes)
            students = sum(len(cls.students) for cls in result.classes)
            issues = bool(result.issues) or any(cls.issues for cls in result.classes)
            detail = f"{groups} grupo(s) de referencia"
            iid = f"ref::{len(self.row_map)}"
            self.row_map[iid] = pdf
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(pdf.name, "Referencia", detail, students, "Revisar" if issues else "Correcto"),
            )

        for pdf, result in self.analysis.photo_rosters.items():
            photos = sum(page.candidate_photos for page in result.pages)
            missing = sum(page.missing_photos for page in result.pages)
            group = result.group_code or result.group_raw
            detail = f"Listado actual · {photos} foto(s)"
            if group:
                detail = f"{group} · {photos} foto(s)"
            if missing:
                detail += f" · {missing} sin foto"
            iid = f"photo::{len(self.row_map)}"
            self.row_map[iid] = pdf
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    pdf.name,
                    "Materia + fotos",
                    detail,
                    len(result.students),
                    "Correcto" if result.is_valid else "Revisar",
                ),
            )

        for pdf in self.analysis.unsupported:
            iid = f"other::{len(self.row_map)}"
            self.row_map[iid] = pdf
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(pdf.name, "No reconocido", "No se utilizará", 0, "Omitido"),
            )

    # ------------------------------------------------------------- Estado/UI

    def _update_summary(self) -> None:
        refs = len(self.analysis.references)
        photos = len(self.analysis.photo_rosters)
        ignored = len(self.analysis.unsupported)
        if not (refs or photos or ignored):
            self.status_text.set(self._empty_status_text())
            return

        parts = []
        if refs:
            parts.append(f"{refs} referencia(s)")
        if photos:
            parts.append(f"{photos} listado(s) actual(es) con fotos")
        if ignored:
            parts.append(f"{ignored} PDF omitido(s)")
        self.status_text.set(" · ".join(parts))

        if photos:
            self.include_nia.set(True)
            self.nia_text.set("NIA (automático cuando se encuentra en las referencias)")
            self.nia_check.configure(state="disabled")
        else:
            self.nia_text.set("NIA (ID del estudiante, recomendado)")
            self.nia_check.configure(state="normal")

    def _refresh_controls(self) -> None:
        supported = bool(self.analysis.references or self.analysis.photo_rosters)
        self.convert_button.configure(state="normal" if supported else "disabled")
        self.remove_button.configure(state="normal" if self.tree.selection() else "disabled")

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
        self.update_idletasks()

    # -------------------------------------------------------------- Detalles

    def show_details(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        pdf = self.row_map.get(selection[0])
        if pdf is None:
            return

        if pdf in self.analysis.references:
            result = self.analysis.references[pdf]
            students = sum(len(cls.students) for cls in result.classes)
            issues = [*result.issues]
            for cls in result.classes:
                issues.extend(cls.issues)
            validation = "Correcto" if not issues else "Revisar:\n- " + "\n- ".join(issues)
            messagebox.showinfo(
                "Detalles del PDF de referencia",
                (
                    f"PDF: {pdf.name}\n"
                    f"Grupos detectados: {len(result.classes)}\n"
                    f"Alumnos totales: {students}\n\n"
                    f"Validación: {validation}"
                ),
                parent=self,
            )
            return

        if pdf in self.analysis.photo_rosters:
            result = self.analysis.photo_rosters[pdf]
            photos = sum(page.candidate_photos for page in result.pages)
            missing = sum(page.missing_photos for page in result.pages)
            wrapped = sum(page.wrapped_names for page in result.pages)
            validation = "Correcto" if result.is_valid else "Revisar:\n- " + "\n- ".join(result.issues)
            messagebox.showinfo(
                "Detalles del listado actual con fotos",
                (
                    f"PDF: {pdf.name}\n"
                    f"Grupo: {result.group_code or result.group_raw or 'No detectado'}\n"
                    f"Alumnos: {len(result.students)}\n"
                    f"Fotografías: {photos}\n"
                    f"Sin fotografía: {missing}\n"
                    f"Nombres multilínea: {wrapped}\n\n"
                    f"Validación: {validation}"
                ),
                parent=self,
            )
            return

        detail = self.analysis.unsupported.get(pdf, "Formato no reconocido")
        messagebox.showwarning(
            "PDF no utilizado",
            f"PDF: {pdf.name}\n\n{detail}",
            parent=self,
        )

    def show_workflow_help(self) -> None:
        messagebox.showinfo(
            "Cómo funciona la selección",
            (
                "Puedes añadir todos los PDF a la vez.\n\n"
                "• Si sólo hay listados de referencia, se genera un XLSX por grupo.\n"
                "• Si hay uno o más listados actuales con fotos, éstos determinan qué alumnado "
                "pertenece a cada clase. Todos los listados de referencia se usan únicamente "
                "para recuperar NIA y otros metadatos.\n"
                "• Un alumno que sólo aparezca en una referencia antigua no se añade a una "
                "clase actual.\n"
                "• Un alumno actual que no aparezca en las referencias se conserva sin NIA. "
                "Si tiene foto, se prepara por nombre y se marca para comprobación.\n"
                "• Una coincidencia ambigua no se adivina: esa clase queda marcada como "
                "Revisión necesaria."
            ),
            parent=self,
        )

    def copy_anonymized_diagnostic(self) -> None:
        reference_classes = sum(len(result.classes) for result in self.analysis.references.values())
        reference_students = sum(
            len(cls.students)
            for result in self.analysis.references.values()
            for cls in result.classes
        )
        photo_students = sum(len(result.students) for result in self.analysis.photo_rosters.values())
        photo_images = sum(
            page.candidate_photos
            for result in self.analysis.photo_rosters.values()
            for page in result.pages
        )
        missing_images = sum(
            page.missing_photos
            for result in self.analysis.photo_rosters.values()
            for page in result.pages
        )
        text = "\n".join(
            [
                "ITACA -> iDoceo | diagnostico anonimizado de seleccion",
                f"Version={__version__}",
                f"Sistema={platform.system()} {platform.release()}",
                f"Python={platform.python_version()}",
                f"PDF_REFERENCIA={len(self.analysis.references)}",
                f"CLASES_REFERENCIA={reference_classes}",
                f"ALUMNOS_REFERENCIA={reference_students}",
                f"PDF_FOTOS={len(self.analysis.photo_rosters)}",
                f"ALUMNOS_FOTOS={photo_students}",
                f"FOTOS={photo_images}",
                f"SIN_FOTO={missing_images}",
                f"PDF_OMITIDOS={len(self.analysis.unsupported)}",
                "NO CONTIENE rutas, nombres de archivo, grupos, nombres de alumnado ni NIA.",
                "",
            ]
        )
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        messagebox.showinfo(
            "Diagnóstico copiado",
            "Se ha copiado un diagnóstico anonimizado preparado para compartir.",
            parent=self,
        )

    def show_technical_details(self) -> None:
        state = "Disponible" if self.dnd_available else "No disponible"
        detail = f"\nMotivo: {self.dnd_error}" if self.dnd_error else ""
        messagebox.showinfo(
            "Detalles técnicos",
            (
                f"ITACA → iDoceo {__version__}\n\n"
                f"Desarrollado por {AUTHOR_NAME}\n"
                f"Portfolio: {PORTFOLIO_URL}\n"
                f"Repositorio: {REPOSITORY_URL}\n\n"
                f"Arrastrar y soltar: {state}\n"
                f"Python: {platform.python_version()}\n"
                f"Sistema: {platform.system()} {platform.release()}{detail}"
            ),
            parent=self,
        )

    # -------------------------------------------------------------- Acciones

    def remove_selected(self) -> None:
        to_remove = {
            self.row_map[iid]
            for iid in self.tree.selection()
            if iid in self.row_map
        }
        if not to_remove:
            return
        self.input_pdfs.difference_update(to_remove)
        if self.input_pdfs:
            self._reanalyze()
        else:
            self.clear_all()

    def clear_all(self) -> None:
        self.input_pdfs.clear()
        self.analysis = SelectionAnalysis(pdfs=[])
        self.row_map.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.last_output_dir = None
        self.open_button.grid_remove()
        self.include_nia.set(True)
        self.nia_text.set("NIA (ID del estudiante, recomendado)")
        self.nia_check.configure(state="normal")
        self._refresh_controls()
        self._update_summary()

    def _default_output_dir(self) -> Path | None:
        parents = {path.parent for path in self.input_pdfs}
        return next(iter(parents)) / "iDoceo" if len(parents) == 1 else None

    def _choose_output_dir(self) -> Path | None:
        default = self._default_output_dir()
        if default is not None:
            return default
        folder = filedialog.askdirectory(
            title="Selecciona la carpeta donde guardar la exportación para iDoceo"
        )
        return Path(folder) if folder else None

    def convert(self) -> None:
        if not (self.analysis.references or self.analysis.photo_rosters):
            return

        output_dir = self._choose_output_dir()
        if output_dir is None:
            return

        self._busy(True)
        try:
            summary = export_analyzed_selection(
                self.analysis,
                output_dir,
                include_nia_for_reference=self.include_nia.get(),
                include_repetix=self.include_repetix.get(),
                include_materia=self.include_materia.get(),
            )
        finally:
            self._busy(False)

        self.last_output_dir = output_dir
        self.open_button.grid(row=0, column=2, sticky="e", padx=(0, 8))

        if summary.blocking_items:
            self.status_text.set(
                f"{summary.ready_items} resultado(s) preparado(s) · "
                f"{summary.blocking_items} requieren revisión"
            )
            messagebox.showwarning(
                "Exportación terminada con revisión necesaria",
                (
                    f"Resultados preparados: {summary.ready_items}\n"
                    f"Resultados con avisos: {summary.warning_items}\n"
                    f"Resultados bloqueados: {summary.blocking_items}\n\n"
                    "No se ha adivinado ninguna coincidencia ambigua. "
                    "Consulta RESUMEN_EXPORTACION.txt en la carpeta de salida."
                ),
                parent=self,
            )
        elif summary.warning_items:
            self.status_text.set(
                f"Exportación completada: {summary.ready_items} resultado(s), "
                f"{summary.warning_items} con aviso"
            )
            messagebox.showinfo(
                "Exportación preparada con avisos",
                (
                    f"Resultados preparados: {summary.ready_items}\n"
                    f"Con avisos: {summary.warning_items}\n\n"
                    "Los avisos no han impedido la exportación. Pueden corresponder a "
                    "fotografías ausentes o alumnado actual sin NIA en las referencias.\n\n"
                    "Consulta RESUMEN_EXPORTACION.txt para ver qué ocurrirá con cada clase."
                ),
                parent=self,
            )
        else:
            self.status_text.set(
                f"Exportación completada: {summary.ready_items} resultado(s) listos"
            )
            messagebox.showinfo(
                "Exportación completada",
                (
                    f"{summary.ready_items} resultado(s) preparados para iDoceo.\n\n"
                    "Consulta RESUMEN_EXPORTACION.txt en la carpeta de salida."
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
