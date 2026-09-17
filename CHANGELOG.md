# Changelog

## Próxima 0.8.0

- Valida de extremo a extremo en iDoceo la creación de clases, importación de alumnado y asociación masiva de fotografías por NIA/ID.
- Actualiza las instrucciones de importación al flujo actual de iDoceo y genera `IMPORTAR_EN_IDOCEO.txt` en la carpeta general de salida.
- Documenta la actualización segura de una clase existente: iDoceo puede añadir nuevos alumnos al volver a importar el XLSX completo, conservando el alumnado ya reconocido y sus datos del cuaderno.
- Aclara que una reimportación no debe interpretarse como sincronización automática de bajas.
- Añade la opción de presentación **Normalizar nombres** en la GUI y `--normalize-names` en `itaca-idoceo convert`.
- La normalización se aplica sólo a la salida, nunca al detector ni al matching; conserva Unicode, guiones/apóstrofos, capitalización ya explícita y partículas ibéricas frecuentes como `de`, `del`, `de la`, `da` o `dos`.
- Mantiene alineados los nombres normalizados del XLSX y los nombres de archivo de `fotos_por_nombre/`.
- Añade pruebas de regresión para la normalización, la guía de importación y el flujo de sólo referencias.

## 0.8.0a1

- Añade soporte inicial para listados actuales de alumnado con fotografías, incluidos nombres multilínea y casillas «Fotografía no disponible».
- Permite seleccionar en una sola pasada todos los PDF de referencia del centro y los listados actuales de las materias impartidas; GUI, Acción rápida y `itaca-idoceo convert` comparten el mismo flujo.
- Cuando existen listados actuales con fotos, éstos determinan el alumnado final de cada clase; las referencias antiguas sólo enriquecen con NIA, REPETIX y MATÈRIA/MÒDUL y nunca reintroducen alumnado ausente del listado actual.
- Cruza cada listado actual contra una piscina común de referencias tabulares, con normalización progresiva y coincidencias conservadoras; las identidades ambiguas no se asignan automáticamente.
- Conserva alumnado actual que no aparezca en las referencias sin inventar NIA. Si tiene foto, la prepara por nombre para comprobación; si no tiene foto, permanece igualmente en el XLSX.
- Separa fotografías asociables por NIA en `fotos_por_nia/` y fotografías sin NIA en `fotos_por_nombre/`.
- Distingue estados de usuario entre resultados listos, fotografías ausentes, avisos tolerables y casos que requieren revisión.
- Corrige la reconstrucción de nombres multilínea en los listados fotográficos y evita confundir continuaciones visuales de MATÈRIA/MÒDUL con continuaciones del nombre en referencias tabulares.
- Reutiliza las referencias ya analizadas para todos los listados actuales de una misma selección, evitando reprocesarlas por cada clase.
- Nombra las carpetas de salida a partir del `GRUP` extraído del contenido del PDF, no del nombre opaco `verReport_...`. Si hay varios listados actuales del mismo grupo, usa sufijos `__2`, `__3`, etc.; el PDF no contiene el nombre de la materia.
- Mantiene el modo de sólo referencias: genera un XLSX por grupo usando el nombre de grupo detectado dentro del PDF.
- Esta alpha está destinada a testers. Aún queda validar en dispositivo la importación real de fotografías por ID/NIA y el fallback por nombre en una versión actual de iDoceo.

## 0.7.0

- Primera versión pública sin sufijo alpha; el proyecto pasa a estado de madurez **Beta** en los metadatos de PyPI.
- Corrige la integración de macOS para registrar **Abrir en ITACA a iDoceo** como Acción rápida real de Finder, además de como servicio.
- La Acción rápida acepta un PDF, varios archivos o carpetas y abre la GUI con la selección ya cargada; el filtrado de PDF sigue realizándose dentro de la aplicación.
- Añade el contexto y los metadatos de Finder que permiten mostrar la acción en **Acciones rápidas** y en **Privacidad y seguridad → Extensiones → Finder**.
- Documenta el paso de activación que macOS puede requerir la primera vez y la recreación mediante `itaca-idoceo integrate --replace` al actualizar desde versiones anteriores.
- Conserva sin cambios la lógica de extracción validada en 0.6.0a14 para ITACA 3, incluidos FP, múltiples grupos, múltiples secciones CURS, campos opcionales y continuaciones de celdas.
- Añade pruebas de regresión específicas para los metadatos del workflow de macOS.

## 0.6.0a14

- Mantiene intacto el detector estable por bloque y corrige las celdas con wrap únicamente como una fase posterior de augmentación.
- Los bloques sin `ORDE`/`NIA` situados inmediatamente después de una fila y antes de la siguiente pueden completar `COGNOMS I NOM`, `REPETIX` y `MATÈRIA`/`MÒDUL`.
- Una nueva ancla `ORDE`+`NIA` siempre actúa como frontera, aunque esa fila no haya podido parsearse, evitando arrastrar contenido entre alumnos.
- La asociación de continuaciones exige además proximidad visual a la fila base; no se vuelve a segmentar globalmente la página como en 0.6.0a12.
- Añade pruebas basadas en las geometrías anonimizadas observadas para overflow de nombre, overflow de materias y protección frente a filas intermedias no parseables.

## 0.6.0a13

- Revierte la reconstrucción global de filas lógicas introducida en 0.6.0a12, que podía omitir alumnos en formatos antes válidos.
- Recupera como base el detector estable por bloque de 0.6.0a11, manteniendo soporte de MÒDUL, exportación opcional y diagnóstico anonimizado.
- Mantiene `layout-report` para analizar de forma segura los casos de celdas desbordadas antes de reintroducir una solución acotada.

## 0.6.0a12

- Introdujo una reconstrucción global de filas lógicas para celdas desbordadas de `COGNOMS I NOM` o `MATÈRIA`/`MÒDUL`.
- Recuperaba `REPETIX` y concatenaba continuaciones, pero podía omitir alumnos en algunos formatos previamente válidos.
- Esta estrategia fue revertida en 0.6.0a13 y sustituida en 0.6.0a14 por una augmentación conservadora sobre el detector estable.

## 0.6.0a11

- Mantiene la firma alternativa de FP (`ORDE`, `NIA`, `COGNOMS I NOM`, `MÒDUL`).
- Revierte el intento especulativo de reconstrucción de nombres partidos de 0.6.0a10 para volver a la base estable anterior.
- Añade temporalmente `itaca-idoceo layout-report`, un informe geométrico anonimizado para estudiar celdas partidas sin compartir datos personales.

## 0.6.0a10

- La firma de ITACA 3 acepta también la cabecera observada en FP: `ORDE | NIA | COGNOMS I NOM | MÒDUL`.
- Los nombres largos partidos visualmente en varias líneas se reconstruyen antes de separar apellidos y nombre.
- La continuación de un nombre ya no puede confundirse con `REPETIX` ni con `MATÈRIA`/`MÒDUL`, por lo que las columnas opcionales se conservan en esas filas.

## 0.6.0a9

- El área principal permite elegir tanto uno o varios PDF como una carpeta también cuando el drag-and-drop no está disponible; al hacer clic muestra ambas opciones junto al propio área.
- Las opciones de exportación pasan a estar visibles en la ventana principal para que no dependan de descubrir el menú de la aplicación.
- Se añaden opciones independientes para exportar `NIA`, `REPETIX` y `MATÈRIA`.
- `REPETIX` y `MATÈRIA` se extraen de la misma fila estructural de cada alumno y se conservan sólo cuando el usuario decide incluirlas en el XLSX.
- La CLI incorpora `--include-repetix` y `--include-materia` tanto en `extract` como en `batch`.
- Se mantienen `REPETIX` y `MATÈRIA` fuera del diagnóstico anonimizado.

## 0.6.0a8

- Renombra el proyecto/distribución a `itaca-idoceo`, el paquete Python a `itaca_idoceo` y el comando principal a `itaca-idoceo`, evitando confundir el antiguo `2` con ITACA 2/MD2.
- Documenta explícitamente que la compatibilidad actual corresponde al listado «LLISTAT D'ALUMNES AMB ASSIGNATURES» de ITACA 3 / Gestión Administrativa; los PDF de MD2 todavía no están soportados ni validados.
- Añade una firma del formato ITACA 3 basada en las cinco cabeceras `ORDE`, `NIA`, `REPETIX`, `COGNOMS I NOM` y `MATÈRIA`; si falta, el listado queda marcado para revisar.
- Añade `Ayuda → Copiar diagnóstico anonimizado`, que excluye nombres/rutas de archivos, centro, grupo, curso, tutor, nombres del alumnado y NIA.
- Filtra los mensajes incluidos en el diagnóstico mediante una lista de incidencias internas conocidas; cualquier detalle inesperado se omite por privacidad.
- Sustituye el aviso provisional de licencia por el texto completo de GNU AGPL v3.
- Mantiene la lógica validada en ESO, Bachillerato y FP de la alpha anterior.

## 0.6.0a7

- Corrige la validación de Bachillerato cuando un mismo `GRUP` contiene varias secciones `CURS` y `ORDE` reinicia en 1 en cada una.
- `GRUP` sigue siendo la unidad de salida: las distintas secciones `CURS` del mismo grupo se combinan en un único XLSX para iDoceo.
- Cada aparición de `CURS` se registra internamente como una sección; los reinicios de `ORDE` se validan por subsecuencia.
- Una repetición de la cabecera `CURS` por paginación no fuerza una subsecuencia nueva si `ORDE` continúa.
- Se marca como incidencia un reinicio de `ORDE` en 1 sin una nueva fila CURS.
- Los detalles locales conservan los distintos valores `CURS` detectados dentro del grupo.
- Se añaden pruebas para Bachillerato y segmentación/validación por grupos de FP.

## 0.6.0a6

- Un mismo PDF puede contener varias clases/grupos; se reconstruyen por las cabeceras `GRUP`, `TUTOR` y `CURS` que preceden visualmente a cada bloque de alumnado.
- La validación de `ORDE` y NIA pasa a hacerse por grupo, de modo que los reinicios `1..N` de distintos grupos de FP son válidos.
- La GUI muestra una fila por grupo detectado aunque varios procedan del mismo PDF y genera un XLSX independiente por grupo.
- `CURS` se extrae ahora completo, no sólo su primera palabra.
- Los cursos de Bachillerato general/específico se consideran compatibles cuando uno es prefijo semántico del otro; se conserva la variante más específica (p. ej. `PRIMER BATX. HUMANITATS I CIÈNCIES SOCIALS`).
- La CLI `extract` genera varios XLSX cuando un único PDF contiene varios grupos.
- Se añaden pruebas para Bachillerato y segmentación/validación por grupos de FP.

## 0.6.0a5

- Aclara el texto del área principal según esté disponible o no el drag-and-drop.
- Extrae el campo `TUTOR` cuando está rellenado y comprueba su coherencia entre páginas.
- Muestra el tutor sólo en los detalles locales del listado; no se exporta al XLSX ni al diagnóstico compartible.


## 0.6.0a4

- Interfaz simplificada: desaparece la fila de botones bajo el área de entrada.
- El área principal es ahora el único control visible para añadir listados: al hacer clic abre directamente el selector de uno o varios PDF.
- Las carpetas se pueden arrastrar cuando TkDND está disponible o añadir desde `Archivo → Añadir carpeta…`.
- El estado de TkDND deja de mostrarse en la interfaz principal y pasa a `Ayuda → Detalles técnicos…`.
- `Detalles` y `Quitar de la lista` pasan al doble clic, menú contextual y teclas Supr/Retroceso.
- `Vaciar lista`, la opción de NIA y la ayuda de importación pasan a la barra de menús.
- La barra de progreso y `Abrir carpeta` sólo aparecen cuando son necesarios.
- Se compacta el texto superior para reducir carga visual.

## 0.6.0a3

- El drag-and-drop pasa a ser una mejora opcional: un fallo al cargar la extensión nativa TkDND ya no impide abrir la GUI.
- Fallback automático a Tkinter estándar con selección mediante botones e integraciones del sistema.
- La interfaz indica cuándo el drag-and-drop no está disponible en el entorno actual.
- Los detalles muestran versión de Python/Tcl/Tk y estado de TkDND para facilitar diagnósticos sin datos del alumnado.
- Corregido el fallo observado en macOS con Python 3.14 que terminaba en `RuntimeError: Unable to load tkdnd library`.

## 0.6.0a2

- Drag-and-drop nativo en la GUI para un PDF, varios PDF y carpetas.
- Validación estructural de `ORDE` como secuencia `1..N`.
- Aviso de NIA duplicados y de inconsistencias de `GRUP`/`CURS`.
- Detección en la GUI de grupos repetidos entre varios PDF cargados.
- Botón de detalles sin mostrar nombres ni NIA.
- Ayuda integrada con los pasos de importación en iDoceo.
- Barra de progreso durante análisis y conversión.
- `tkinterdnd2` 0.6.3 como dependencia para drag-and-drop multiplataforma.

## 0.6.0a1

- Primera estructura instalable como paquete Python moderno.
- CLI mediante `itaca-idoceo`.
- GUI multiplataforma mediante Tkinter.
- Procesamiento de varios PDF y carpetas.
- Separación de apellidos/nombre mediante la coma del campo `COGNOMS I NOM`.
- Detección de `GRUP` por geometría visual del PDF.
- Detección de `CURS` sólo en páginas que contienen alumnado.
- Exportación XLSX mínima para iDoceo (`Apellidos`, `Nombre`; NIA opcional).
- Integraciones locales para Windows, Linux y macOS.
- Acción rápida experimental de Finder en macOS.
