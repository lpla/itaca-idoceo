# Uso avanzado y diagnóstico técnico

Esta documentación no es necesaria para el uso habitual de la aplicación. Está pensada para usuarios con experiencia en terminal y para depurar formatos PDF que todavía no se interpretan correctamente.

## `convert`: flujo recomendado

`convert` acepta simultáneamente archivos y carpetas, recorre las carpetas de forma recursiva y clasifica automáticamente cada PDF como referencia tabular, listado actual con fotos o formato no reconocido.

Una carpeta completa:

```text
itaca-idoceo convert carpeta_con_todos_los_pdf/
```

Varios orígenes en una única pasada:

```text
itaca-idoceo convert referencias/ materia_1.pdf materia_2.pdf -o salida/
```

Si la selección contiene listados actuales con fotos, éstos determinan las clases que se exportan y todos los PDF tabulares seleccionados se reutilizan como una única piscina de referencias. Los PDF de referencia se analizan una sola vez y se reutilizan para todos los listados de materia.

Si no hay ningún listado actual con fotos, se exportan directamente todos los grupos válidos encontrados en las referencias. En este modo `convert` incluye NIA por defecto; puede desactivarse con:

```text
itaca-idoceo convert referencias/ --no-nia
```

Campos opcionales:

```text
itaca-idoceo convert carpeta/ --include-repetix --include-materia
```

Capitalización opcional de nombres y apellidos:

```text
itaca-idoceo convert carpeta/ --normalize-names
```

`--normalize-names` se aplica **después** de detectar y cruzar el alumnado. No interviene en el matching: sólo modifica las columnas `Apellidos` y `Nombre` de la salida y, cuando sea necesario asociar una foto por nombre, su nombre de archivo. Conserva palabras que ya contienen minúsculas, guiones y apóstrofos, y mantiene en minúscula partículas ibéricas frecuentes como `de`, `del`, `de la`, `da` o `dos`. Al ser una heurística de presentación puede tener excepciones.

Si una clase se va a volver a importar posteriormente sobre una clase ya existente en iDoceo, conviene mantener siempre el mismo valor de esta opción, porque iDoceo utiliza el nombre para reconocer alumnado que ya existe.

`convert` genera `RESUMEN_EXPORTACION.txt` e `IMPORTAR_EN_IDOCEO.txt` en la carpeta de salida. La salida normal de terminal sólo muestra contadores y estados, no nombres, NIA ni rutas locales.

## Reimportar sobre una clase existente

El XLSX generado contiene alumnado y datos personales, no las columnas de evaluación que ya existen en iDoceo. Para incorporar matrículas nuevas a una clase ya creada, se puede volver a importar el XLSX completo y seleccionar la clase existente en el último paso del asistente. iDoceo intenta reconocer al alumnado con el mismo nombre, actualiza sus datos personales y añade los alumnos nuevos.

No se genera por defecto un archivo «sólo nuevos» porque la herramienta no conoce el estado real del cuaderno de iDoceo: un profesor puede haber añadido o editado alumnado manualmente después de la primera importación. Tampoco se interpretan como bajas los alumnos que ya existan en iDoceo pero no estén en el nuevo XLSX; esa revisión debe hacerse en iDoceo.

## Comandos históricos por formato

Se mantienen para diagnóstico o usos específicos.

Comprobar localmente un PDF tabular:

```text
itaca-idoceo check listado.pdf
```

Convertir un PDF tabular:

```text
itaca-idoceo extract listado.pdf
```

Convertir todos los PDF tabulares de una carpeta:

```text
itaca-idoceo batch carpeta/
```

Procesar también subcarpetas:

```text
itaca-idoceo batch carpeta/ --recursive
```

Los campos adicionales se pueden combinar libremente:

```text
itaca-idoceo extract listado.pdf --include-nia
itaca-idoceo extract listado.pdf --include-repetix --include-materia
itaca-idoceo batch carpeta/ --include-nia --include-repetix --include-materia
```

`--include-materia` exporta la columna `MATÈRIA` en listados generales y `MÒDUL` en los formatos de FP compatibles.

La opción `--normalize-names` pertenece por ahora al flujo recomendado `convert`; los comandos históricos mantienen su interfaz anterior para no alterar usos existentes.

## Listados con fotos

Para inspeccionar anónimamente un único listado con fotos:

```text
itaca-idoceo photo-check listado_con_fotos.pdf
```

Cruzar ese listado con una carpeta completa de referencias:

```text
itaca-idoceo photo-check listado_con_fotos.pdf \
  --reference-folder referencias/
```

Exportar únicamente ese listado concreto:

```text
itaca-idoceo photo-export listado_con_fotos.pdf \
  --reference-folder referencias/ \
  -o salida/
```

Para el uso habitual con varios listados de materia, es preferible `convert`, ya que analiza las referencias una sola vez, ofrece la normalización opcional de nombres y realiza toda la exportación conjuntamente.

## Salida de `check`

`check` es una herramienta de inspección **local**. Puede mostrar metadatos del listado, por lo que **su salida no debe copiarse directamente a una incidencia pública**.

`photo-check` está diseñado para mostrar únicamente métricas estructurales y diagnósticos anónimos, pero ante un error inesperado una herramienta de terminal puede incluir una ruta proporcionada por el usuario. No copies errores completos sin revisarlos primero.

Para soporte general, utiliza **Ayuda → Copiar diagnóstico anonimizado** desde la interfaz gráfica.

## `layout-report`

`layout-report` genera un informe geométrico anonimizado del PDF para estudiar problemas de maquetación o filas que no se interpretan bien.

Para una fila concreta:

```text
itaca-idoceo layout-report listado.pdf --orde 17 -o informe.txt
```

Para una fila y sus vecinas:

```text
itaca-idoceo layout-report listado.pdf \
  --orde 16 --orde 17 --orde 18 \
  -o informe.txt
```

Si se omite `--orde`, el informe puede ser mucho más largo:

```text
itaca-idoceo layout-report listado.pdf -o informe.txt
```

El informe sustituye el contenido sensible por marcadores estructurales y conserva coordenadas útiles para depuración. Aun así, **revísalo antes de compartirlo**.

No compartas nunca el PDF original, el XLSX generado ni fotografías del alumnado. Consulta [SECURITY.md](../SECURITY.md) antes de abrir una incidencia.

## Integraciones del sistema

Crear los accesos gráficos:

```text
itaca-idoceo integrate
```

Recrearlos:

```text
itaca-idoceo integrate --replace
```

Eliminarlos:

```text
itaca-idoceo uninstall-integration
```
