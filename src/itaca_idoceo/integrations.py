from __future__ import annotations

import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "ITACA a iDoceo"
QUICK_ACTION_NAME = "Abrir en ITACA a iDoceo"


def _python_gui_command() -> list[str]:
    python = Path(sys.executable)
    if platform.system() == "Windows":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.exists():
            python = pythonw
    return [str(python), "-m", "itaca_idoceo.gui"]


def _python_quick_command() -> list[str]:
    return [str(Path(sys.executable)), "-m", "itaca_idoceo.gui"]


def install_integration(replace: bool = False) -> list[Path]:
    system = platform.system()
    if system == "Darwin":
        return _install_macos(replace)
    if system == "Windows":
        return _install_windows(replace)
    if system == "Linux":
        return _install_linux(replace)
    raise RuntimeError(f"Sistema operativo no soportado: {system}")


def uninstall_integration() -> list[Path]:
    system = platform.system()
    candidates: list[Path] = []
    if system == "Darwin":
        candidates = [
            Path.home() / "Applications" / f"{APP_NAME}.app",
            Path.home() / "Library" / "Services" / f"{QUICK_ACTION_NAME}.workflow",
        ]
    elif system == "Linux":
        candidates = [
            Path.home() / ".local" / "share" / "applications" / "itaca-idoceo.desktop"
        ]
    elif system == "Windows":
        desktop = _windows_desktop()
        if desktop:
            candidates = [desktop / f"{APP_NAME}.lnk"]

    removed: list[Path] = []
    for path in candidates:
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
        elif path.exists():
            path.unlink()
            removed.append(path)
    return removed


def _install_linux(replace: bool) -> list[Path]:
    applications = Path.home() / ".local" / "share" / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    desktop = applications / "itaca-idoceo.desktop"
    if desktop.exists() and not replace:
        raise RuntimeError(
            f"Ya existe {desktop}. Usa 'itaca-idoceo integrate --replace' para sustituirlo."
        )

    command = " ".join(shlex.quote(part) for part in _python_gui_command())
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ITACA → iDoceo\n"
        "Comment=Convierte localmente listados de ITACA para iDoceo\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "Categories=Education;Office;\n"
        "StartupNotify=true\n",
        encoding="utf-8",
    )
    desktop.chmod(0o755)
    return [desktop]


def _windows_desktop() -> Path | None:
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "[Environment]::GetFolderPath('Desktop')",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip()
        return Path(value) if value else None
    except Exception:
        return None


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _install_windows(replace: bool) -> list[Path]:
    desktop = _windows_desktop()
    if desktop is None:
        raise RuntimeError("No se ha podido localizar el Escritorio de Windows.")

    shortcut = desktop / f"{APP_NAME}.lnk"
    if shortcut.exists() and not replace:
        raise RuntimeError(
            f"Ya existe {shortcut}. Usa 'itaca-idoceo integrate --replace' para sustituirlo."
        )

    target, *args = _python_gui_command()
    argument_string = subprocess.list2cmdline(args)
    script = "; ".join(
        [
            "$ws = New-Object -ComObject WScript.Shell",
            f"$s = $ws.CreateShortcut({_ps_quote(str(shortcut))})",
            f"$s.TargetPath = {_ps_quote(target)}",
            f"$s.Arguments = {_ps_quote(argument_string)}",
            f"$s.WorkingDirectory = {_ps_quote(str(Path.home()))}",
            "$s.Description = 'Convertir listados de ITACA para iDoceo'",
            "$s.Save()",
        ]
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        check=True,
    )
    return [shortcut]


def _install_macos(replace: bool) -> list[Path]:
    applications = Path.home() / "Applications"
    applications.mkdir(parents=True, exist_ok=True)
    app = applications / f"{APP_NAME}.app"

    services = Path.home() / "Library" / "Services"
    services.mkdir(parents=True, exist_ok=True)
    workflow = services / f"{QUICK_ACTION_NAME}.workflow"

    for path in (app, workflow):
        if path.exists() and not replace:
            raise RuntimeError(
                f"Ya existe {path}. Usa 'itaca-idoceo integrate --replace' para sustituirlo."
            )

    if replace:
        if app.exists():
            shutil.rmtree(app)
        if workflow.exists():
            shutil.rmtree(workflow)

    # Lanzador .app generado localmente con herramientas de macOS.
    gui_cmd = " ".join(shlex.quote(part) for part in _python_gui_command())
    apple_cmd = gui_cmd.replace("\\", "\\\\").replace('"', '\\"')
    applescript = f'do shell script "{apple_cmd} >/dev/null 2>&1 &"'
    subprocess.run(
        ["/usr/bin/osacompile", "-o", str(app), "-e", applescript],
        check=True,
    )

    _write_macos_quick_action(workflow)

    # Fuerza a Services a releer el directorio cuando está disponible.
    pbs = Path("/System/Library/CoreServices/pbs")
    if pbs.exists():
        subprocess.run([str(pbs), "-flush"], check=False)

    return [app, workflow]


def _write_macos_quick_action(workflow: Path) -> None:
    contents = workflow / "Contents"
    contents.mkdir(parents=True, exist_ok=True)

    quick_program = " ".join(
        shlex.quote(part) for part in _python_quick_command()
    )
    # Automator no debe permanecer ocupado mientras la ventana gráfica está abierta.
    quick_cmd = f'( {quick_program} "$@" >/dev/null 2>&1 & )'

    action_uuid = "DCA2DD2E-8C3E-4F73-8B89-0A1CA21D0CE0"

    wflow = {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": quick_cmd,
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,
                        "shell": "/bin/zsh",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": "1CB7B882-F106-47D4-A27E-FBBE9AEC4BE1",
                    "OutputUUID": "42FE3576-7C70-4B5C-8F2F-6360C2BB5EB9",
                    "UUID": action_uuid,
                }
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleID": "com.apple.finder",
            "applicationPath": "/System/Library/CoreServices/Finder.app",
            "applicationBundleIDsByPath": {
                "/System/Library/CoreServices/Finder.app": "com.apple.finder",
            },
            "applicationPaths": ["/System/Library/CoreServices/Finder.app"],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "processesInput": 0,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "useAutomaticInputType": 0,
            "systemImageName": "NSActionTemplate",
            "presentationMode": 15,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }

    info = {
        "NSServices": [
            {
                "NSMenuItem": {"default": QUICK_ACTION_NAME},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {
                    "NSApplicationIdentifier": "com.apple.finder",
                },
                "NSBackgroundColorName": "background",
                "NSIconName": "NSActionTemplate",
                # public.item permite usar la Acción rápida con uno o varios
                # PDF y también con carpetas; la GUI filtra después los PDF.
                "NSSendFileTypes": ["public.item"],
            }
        ]
    }

    with (contents / "document.wflow").open("wb") as fh:
        plistlib.dump(wflow, fh, fmt=plistlib.FMT_XML, sort_keys=False)
    with (contents / "Info.plist").open("wb") as fh:
        plistlib.dump(info, fh, fmt=plistlib.FMT_XML, sort_keys=False)
