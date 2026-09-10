# Uso avanzado y diagnóstico técnico

Esta documentación no es necesaria para el uso habitual de la aplicación. Está pensada para usuarios con experiencia en terminal y para depurar formatos PDF que todavía no se interpretan correctamente.

## Comandos principales

Comprobar localmente un PDF:

```text
itaca-idoceo check listado.pdf
```

Convertir un PDF:

```text
itaca-idoceo extract listado.pdf
```

Convertir todos los PDF de una carpeta:

```text
itaca-idoceo batch carpeta/
```

Procesar también subcarpetas:

```text
itaca-idoceo batch carpeta/ --recursive
```

## Campos opcionales

Los tres campos adicionales se pueden combinar libremente:

```text
itaca-idoceo extract listado.pdf --include-nia
itaca-idoceo extract listado.pdf --include-repetix --include-materia
itaca-idoceo batch carpeta/ --include-nia --include-repetix --include-materia
```

`--include-materia` exporta la columna `MATÈRIA` en listados generales y `MÒDUL` en los formatos de FP compatibles.

## Salida de `check`

`check` es una herramienta de inspección **local**. Puede mostrar metadatos del listado, por lo que **su salida no debe copiarse directamente a una incidencia pública**.

Para soporte general, utiliza primero **Ayuda → Copiar diagnóstico anonimizado** desde la interfaz gráfica.

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

No compartas nunca el PDF original ni el XLSX generado. Consulta [SECURITY.md](../SECURITY.md) antes de abrir una incidencia.

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
