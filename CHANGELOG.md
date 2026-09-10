# Changelog

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
- Se marca como incidencia un reinicio de `ORDE` en 1 sin una nueva fila `CURS`.
- Los detalles locales conservan los distintos valores `CURS` detectados dentro del grupo.
- Se añaden pruebas con el caso realista `1..21` + `1..11` de Bachillerato.

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
