# ITACA → iDoceo

Convierte **localmente** listados PDF de alumnado de ITACA (Generalitat Valenciana) en archivos preparados para importar en iDoceo.

**Descarga e instalación:** [PyPI](https://pypi.org/project/itaca-idoceo/) · **Versiones:** [GitHub Releases](https://github.com/lpla/itaca-idoceo/releases)

> [!IMPORTANT]
> La herramienta no sube PDF, fotografías ni datos del alumnado a ningún servicio. Todo el procesamiento se realiza íntegramente en el ordenador donde se ejecuta.

> [!NOTE]
> Este es un proyecto independiente. No está afiliado, respaldado ni mantenido por la Generalitat Valenciana ni por iDoceo.

## ¿Qué listados admite?

La herramienta reconoce dos tipos de entrada que pueden añadirse **juntos en una sola selección**:

1. **Listados tabulares de referencia**, validados con «LLISTAT D'ALUMNES AMB ASSIGNATURES» generado desde ITACA 3 / Gestión Administrativa, incluidos listados de ESO, Bachillerato y FP.
2. **Listados actuales con fotografías por grupo y materia**, con alumnado distribuido en una cuadrícula de hasta seis fotografías por fila y el nombre debajo de cada casilla.

Los listados tabulares reconocen, entre otras, estas dos cabeceras:

```text
Formato general: ORDE | NIA | REPETIX | COGNOMS I NOM | MATÈRIA
Formato FP:      ORDE | NIA | COGNOMS I NOM | MÒDUL
```

Los PDF obtenidos desde **Mòdul Docent 2 (MD2)** pueden tener otro formato y **todavía no están soportados ni validados**.

## Instalación

La instalación sólo requiere usar una terminal una vez. Después puedes abrir la aplicación desde el acceso gráfico creado por `itaca-idoceo integrate`.

Sigue la guía de tu sistema operativo:

- [Windows](docs/INSTALL.md#windows)
- [macOS](docs/INSTALL.md#macos)
- [LliureX / Ubuntu y derivados](docs/INSTALL.md#lliurex--ubuntu-y-derivados)

Si ya tienes Python 3.12 o posterior y `pipx`:

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

En macOS, tras instalar, puede ser necesario activar una vez **Abrir en ITACA a iDoceo** en **Ajustes del Sistema → Privacidad y seguridad → Extensiones → Finder**. La [guía de instalación](docs/INSTALL.md#macos) explica el paso.

## Uso habitual: añade todo a la vez

1. Abre **ITACA → iDoceo** desde el acceso creado en tu sistema, usa la Acción rápida del explorador de archivos o arrastra una carpeta completa.
2. Añade **todos los PDF que tengas disponibles en ese momento**: listados de referencia del centro y, si ya los has descargado, listados actuales con fotos de las materias que impartes.
3. La aplicación detecta automáticamente qué PDF es de referencia y cuál es un listado actual con fotos.
4. Elige, si quieres, los campos adicionales y la opción **Normalizar nombres**.
5. Pulsa **Preparar todo para iDoceo** una sola vez.

La herramienta elige el flujo automáticamente.

### Si sólo hay listados de referencia

Se genera un XLSX por cada grupo válido encontrado. El NIA se incluye por defecto como identificador recomendado para iDoceo.

Como los listados de referencia no indican qué grupos imparte cada profesor, si se añaden todos los PDF del centro se exportarán todos los grupos encontrados. Puedes quedarte únicamente con los XLSX que necesites.

### Si también hay listados actuales con fotos

Los listados actuales pasan a ser la **fuente de verdad sobre qué alumnado pertenece a cada clase**. Los PDF de referencia ya no generan clases adicionales: se utilizan conjuntamente para recuperar NIA y otros metadatos del alumnado que aparece en cada listado actual.

Esto significa que:

- un alumno que figure en una referencia antigua pero ya no aparezca en el listado actual **no se añade** a la clase;
- un alumno que aparezca en el listado actual pero no exista en ninguna referencia **sí se conserva**, con el NIA y demás metadatos de referencia en blanco;
- si ese alumno nuevo tiene fotografía, se guarda por nombre y apellidos para poder intentar su asociación en iDoceo, pero se marca para comprobación;
- si no tiene fotografía, permanece igualmente en el XLSX;
- una coincidencia realmente ambigua nunca se adivina: sólo esa clase queda marcada como **Revisión necesaria**.

## Normalizar nombres (opcional)

ITACA suele escribir nombres y apellidos completamente en mayúsculas. Si marcas **Normalizar nombres**, la herramienta modifica **sólo la presentación de la salida**: el detector y el cruce entre PDF siguen trabajando con el texto original.

La heurística:

- capitaliza las palabras que llegan completamente en mayúsculas;
- conserva tildes y caracteres Unicode;
- conserva guiones y apóstrofos (`MARÍA-JOSÉ` → `María-José`, `O'NEILL` → `O'Neill`);
- mantiene en minúscula partículas frecuentes en nombres ibéricos cuando forman parte de un nombre compuesto (`DE LA FUENTE` → `de la Fuente`, `DA SILVA` → `da Silva`);
- intenta conservar formas ya capitalizadas expresamente y algunos casos habituales como `McDonald`;
- no modifica NIA, REPETIX ni MATÈRIA/MÒDUL.

Es una heurística de presentación y siempre puede haber excepciones. Si vas a volver a importar más adelante alumnado en una clase existente, usa **el mismo criterio de normalización** que utilizaste al crearla, para que el nombre se mantenga estable entre importaciones.

## Importar una clase nueva en iDoceo

Con la aplicación actual de iDoceo, el flujo verificado es:

1. En la pantalla principal, pulsa **+** en la esquina inferior derecha.
2. Elige **Clase** y escribe el nombre de la clase.
3. En la ventana de la clase, abre la pestaña **Herramientas**.
4. Pulsa **Importar fichero CSV/XLS** y selecciona `alumnado_idoceo.xlsx` (o el XLSX del grupo si sólo has usado referencias).
5. En el asistente, asigna **Apellidos** y **Nombre** a la composición del nombre. Si el XLSX contiene `NIA`, asígnalo a **Número de identificación / ID**.
6. Si has exportado `REPETIX` o `MATÈRIA / MÒDUL`, decide expresamente su destino y no los dejes seleccionados por accidente como columnas del cuaderno.

## Actualizar una clase existente sin perder la evaluación

No hace falta generar un archivo que contenga sólo los alumnos nuevos. Vuelve a importar el **XLSX completo y actualizado** y, en el último paso del asistente de importación, elige añadir los datos a la clase que ya existe.

Según la documentación de iDoceo, al añadir datos a una clase existente intenta localizar al alumnado con el mismo nombre; si lo reconoce, no vuelve a crear al alumno y sólo actualiza sus datos personales, mientras que los alumnos nuevos se añaden a los ya existentes. Como los XLSX generados por esta herramienta no incluyen las columnas de evaluación del cuaderno, este flujo permite conservar la evaluación que ya hayas introducido.

Esto **no es una sincronización de bajas**: si un alumno ya estaba en iDoceo pero ha dejado de pertenecer a la clase, revisa su situación en iDoceo y elimínalo u ocúltalo manualmente si procede.

## Importar las fotografías

Hazlo **después** de crear o actualizar el alumnado de la clase:

1. Entra en la clase y, en la columna izquierda, abre **Plano**.
2. Pulsa el botón del **martillo** de la esquina superior derecha.
3. Elige **Importación masiva**.
4. En **Selecciona campos personales**, elige un único criterio de asociación:
   - para `fotos_por_nia/`: **Número de identificación**;
   - para `fotos_por_nombre/`: **Apellidos, Nombre**.

Si existen ambas carpetas, impórtalas en dos pasadas. `fotos_por_nia/` es la asociación preferente. `fotos_por_nombre/` sólo aparece cuando no se ha podido recuperar un NIA inequívoco para una fotografía y conviene comprobar el resultado.

## ¿Qué resultados puedo encontrar?

La interfaz y `RESUMEN_EXPORTACION.txt` utilizan cuatro estados sencillos:

- **LISTO**: todo el alumnado actual se ha identificado por NIA y tiene foto.
- **LISTO, FALTAN FOTOS**: las identidades están resueltas, pero el PDF no contiene alguna fotografía.
- **LISTO CON AVISOS**: por ejemplo, existe alumnado actual que no aparece en las referencias. La clase se exporta igualmente sin inventar identificadores.
- **REVISIÓN NECESARIA**: hay una correspondencia ambigua y no es seguro asignar un NIA automáticamente.

Para una clase con fotografías, la carpeta de salida puede contener:

```text
<clase>_idoceo/
├── alumnado_idoceo.xlsx
├── fotos_por_nia/          # asociación preferente y segura
├── fotos_por_nombre/       # sólo si hace falta; conviene comprobarla
└── IMPORTAR_EN_IDOCEO.txt
```

La carpeta general de salida incluye además `RESUMEN_EXPORTACION.txt` e `IMPORTAR_EN_IDOCEO.txt` con las instrucciones del flujo completo. Los alumnos sin fotografía se incluyen en el XLSX aunque no tengan archivo de imagen.

Un mismo PDF tabular puede contener varios grupos. También se admiten casos de Bachillerato en los que un mismo grupo contiene varias secciones `CURS` y casos en los que un nombre o la lista de materias ocupa varias líneas del PDF.

## Acción rápida, GUI y terminal usan el mismo flujo

Puedes abrir la aplicación normalmente, arrastrar archivos/carpetas o usar la Acción rápida del sistema sobre una selección múltiple. En terminal, el equivalente es:

```text
itaca-idoceo convert carpeta_con_referencias/ carpeta_con_listados_actuales/ -o salida/
```

Para activar la capitalización opcional de nombres:

```text
itaca-idoceo convert carpeta_con_referencias/ carpeta_con_listados_actuales/ \
  --normalize-names -o salida/
```

`convert` busca PDF recursivamente dentro de las carpetas indicadas, detecta automáticamente ambos formatos y prepara toda la salida en una ejecución.

## Si algo no funciona

**No compartas el PDF real, el XLSX generado ni las fotografías.** Los listados pueden contener datos personales de menores.

En la aplicación usa **Ayuda → Copiar diagnóstico anonimizado** y pega ese texto en una incidencia de GitHub. El diagnóstico está diseñado para omitir nombres, NIA, centro, grupo, tutor, materias, fotografías y rutas locales.

[Cómo informar de un problema de forma segura](SECURITY.md)

## Actualizar

Si ya lo tienes instalado desde PyPI:

```text
pipx upgrade itaca-idoceo
```

Si después de actualizar necesitas recrear el acceso gráfico:

```text
itaca-idoceo integrate --replace
```

## Desinstalar

```text
itaca-idoceo uninstall-integration
pipx uninstall itaca-idoceo
```

## Uso avanzado

La mayoría de usuarios no necesita esta parte. La línea de comandos, el procesamiento por lotes y los diagnósticos técnicos están documentados aparte:

[Uso avanzado y diagnóstico técnico](docs/ADVANCED.md)

## Privacidad y seguridad

El proyecto no incorpora telemetría ni analítica y no necesita servicios remotos para procesar los listados. Las dependencias se descargan únicamente durante la instalación o actualización mediante el gestor de paquetes elegido por el usuario.

Consulta [SECURITY.md](SECURITY.md) antes de abrir una incidencia.

## Licencia

Este proyecto se distribuye bajo **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. El texto completo se incluye en [LICENSE]. PyMuPDF se distribuye bajo AGPL o licencia comercial, por lo que este proyecto adopta AGPL-3.0 para su distribución de código abierto.
