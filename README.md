# ITACA → iDoceo

Convierte **localmente** listados PDF de alumnado de ITACA (Generalitat Valenciana) en archivos `.xlsx` preparados para importar en iDoceo.

> [!IMPORTANT]
> La herramienta no sube PDF ni datos del alumnado a ningún servicio. No contiene telemetría, analítica ni funciones de red para procesar los listados: la lectura del PDF y la generación del XLSX se realizan íntegramente en el equipo del usuario.

## Compatibilidad actual

La versión **0.6.0a8** es una alpha y ha sido validada con listados reales **«LLISTAT D'ALUMNES AMB ASSIGNATURES» generados desde ITACA 3 / Gestión Administrativa**, incluidos casos de ESO, Bachillerato y FP.

Antes de procesar un listado, la aplicación comprueba la firma estructural del formato actualmente soportado mediante la fila de cabeceras:

```text
ORDE | NIA | REPETIX | COGNOMS I NOM | MATÈRIA
```

Si esa firma no aparece, el documento queda marcado para revisar. Esto ayuda a evitar que un PDF diferente de ITACA sea interpretado accidentalmente como el formato conocido.

Los PDF obtenidos desde el entorno docente **Mòdul Docent 2 (MD2)** pueden tener otro formato y **todavía no están soportados ni validados**. Se añadirá un extractor específico cuando dispongamos de ejemplos que puedan comprobarse localmente sin compartir datos personales.

## Instalación

Requiere **Python 3.12 o posterior**. La instalación recomendada será mediante `pipx`, que mantiene la aplicación aislada del Python del sistema:

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

Mientras la alpha aún no esté publicada en PyPI, puede instalarse directamente desde este repositorio:

```text
pipx install 'git+https://github.com/lpla/itaca-idoceo.git'
itaca-idoceo integrate
```

La aplicación también puede abrirse directamente con:

```text
itaca-idoceo
```

### Dependencias de interfaz por plataforma

En Windows, las instalaciones de Python de python.org incluyen normalmente Tkinter. En macOS con Homebrew:

```text
brew install python python-tk pipx
```

En LliureX/Ubuntu y derivados:

```text
sudo apt install python3-tk pipx
```

`itaca-idoceo integrate` crea accesos gráficos locales: un acceso directo en Windows, un lanzador `.desktop` en Linux y, en macOS, `~/Applications/ITACA a iDoceo.app` junto con la Acción rápida de Finder **Abrir en ITACA a iDoceo**.

## Uso gráfico

El área superior de la ventana es el punto de entrada principal. Cuando TkDND está disponible, admite arrastrar uno o varios PDF o una carpeta; al hacer clic permite seleccionar uno o varios PDF. Si el drag-and-drop no puede cargarse en una combinación concreta de Python/Tk/sistema operativo, la aplicación continúa funcionando y el área sigue siendo clicable. Las carpetas también pueden añadirse desde **Archivo → Añadir carpeta…**.

La tabla no muestra nombres ni NIA. Antes de convertir enseña únicamente el PDF, el grupo, el curso, el número de alumnos y un estado `Correcto`, `Revisar` o `Error`.

La unidad de salida es **GRUP**. Un mismo PDF puede contener varios grupos, como ocurre en determinados listados de FP. A la vez, un mismo `GRUP` puede incluir varias secciones `CURS`, como ocurre en determinados listados de Bachillerato; cada reinicio legítimo de `ORDE` se valida por sección sin dividir necesariamente el XLSX final.

La herramienta detecta también `TUTOR` cuando existe. Se usa como metadato local y para comprobaciones de coherencia, pero no se exporta al XLSX.

## XLSX generado

Por defecto contiene únicamente:

```text
Apellidos | Nombre
```

Opcionalmente puede incluir `NIA`, pensado para mapearlo al campo personal `ID` / `Student ID` de iDoceo.

`ORDE` se utiliza para validar la estructura. `REPETIX` y `MATÈRIA` forman parte de la firma del informe, pero por ahora no se exportan: no se añaden columnas al cuaderno de iDoceo sin un destino claro.

## Importación en iDoceo

En el asistente de importación de iDoceo, utiliza la primera fila como cabecera, asigna `Nombre` y `Apellidos` en la composición del nombre del estudiante y, si se exportó el NIA, asígnalo al campo personal `ID` / `Student ID`. Comprueba antes de terminar que iDoceo no haya seleccionado ninguna columna no deseada como columna del cuaderno.

## Diagnóstico anonimizado

Para informar de un problema sin compartir datos del alumnado, usa **Ayuda → Copiar diagnóstico anonimizado**. El texto copiado incluye versión, sistema operativo, versiones de Python/Tcl/Tk, disponibilidad del drag-and-drop, número de páginas, número de clases, recuentos de alumnado, resultado de la firma ITACA 3 y mensajes de validación filtrados.

El diagnóstico **no incluye** nombres ni rutas de PDF, centro, `GRUP`, `CURS`, valor de `TUTOR`, nombres del alumnado ni NIA. Los errores no reconocidos se omiten en lugar de copiar su texto potencialmente sensible.

No adjuntes PDF reales, XLSX resultantes ni capturas con datos personales a una incidencia pública.

## Terminal

```text
itaca-idoceo check listado.pdf
itaca-idoceo extract listado.pdf
itaca-idoceo batch carpeta/
```

Para incluir NIA:

```text
itaca-idoceo extract listado.pdf --include-nia
itaca-idoceo batch carpeta/ --include-nia
```

`check` es una herramienta de inspección **local** y sí puede mostrar metadatos del listado, por lo que su salida no debe copiarse a una incidencia pública. Para soporte utiliza el diagnóstico anonimizado de la GUI.

## Actualización y desinstalación

Cuando la distribución esté en PyPI:

```text
pipx upgrade itaca-idoceo
```

Para eliminar los accesos creados por la aplicación y después desinstalarla:

```text
itaca-idoceo uninstall-integration
pipx uninstall itaca-idoceo
```

## Privacidad y seguridad

Los PDF de ITACA pueden contener datos personales de menores. El proyecto está diseñado para no necesitar que esos documentos salgan del ordenador del centro. Consulta [SECURITY.md](SECURITY.md) antes de abrir una incidencia.

El drag-and-drop, cuando está disponible, se implementa mediante `tkinterdnd2`/TkDND y no cambia el modelo de procesamiento local. Si esa extensión nativa no puede cargarse, se desactiva automáticamente sin impedir el uso de la aplicación.

## Licencia

Este proyecto se distribuye bajo **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. El texto completo se incluye en [LICENSE](LICENSE). PyMuPDF se distribuye bajo AGPL o licencia comercial, por lo que este proyecto adopta AGPL-3.0 para su distribución de código abierto.
