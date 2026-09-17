# ITACA → iDoceo 0.8.0

Esta versión incorpora el flujo conjunto de listados tabulares de referencia y listados actuales con fotografías, manteniendo todo el procesamiento en local.

## Novedades principales

- Soporte para listados actuales de alumnado con fotografías, incluidos nombres multilínea y casillas «Fotografía no disponible».
- Flujo de una sola pasada: se pueden seleccionar a la vez todos los PDF de referencia del centro y los PDF actuales de las materias impartidas.
- Los listados actuales determinan el alumnado final de cada clase; las referencias sólo se usan para recuperar NIA y otros metadatos.
- Cruce local y conservador contra todas las referencias disponibles, sin adivinar identidades ambiguas.
- Conservación del alumnado actual aunque no exista en las referencias antiguas, sin inventar NIA.
- Fotografías separadas entre `fotos_por_nia/` y, cuando no hay NIA disponible, `fotos_por_nombre/` para comprobación posterior.
- Estados claros de salida: listo, faltan fotos, listo con avisos y revisión necesaria.
- Carpetas de salida nombradas por el `GRUP` extraído del contenido del PDF, no por nombres opacos del tipo `verReport_...`.
- El modo de sólo referencias sigue generando un XLSX por grupo.
- GUI con acceso directo al portfolio del autor, al repositorio y a la creación de incidencias en GitHub.

## Limitaciones conocidas

- Si un profesor descarga varios listados actuales de materias distintas para el mismo grupo, el PDF no contiene el nombre de la materia. Las salidas se distinguen con sufijos `__2`, `__3`, etc.; la herramienta no pide introducirla manualmente.
- Las fotografías de alumnado actual sin NIA se preparan por nombre y deben comprobarse después de importarlas en iDoceo.
- La asociación real de fotografías por ID/NIA en iDoceo debe seguir validándose en diferentes dispositivos y versiones de iDoceo; cualquier incidencia puede comunicarse desde **Ayuda → Informar de un problema en GitHub…**.

## Actualización

```text
pipx upgrade itaca-idoceo
itaca-idoceo integrate --replace
```

Comprobar la versión:

```text
itaca-idoceo --version
```

La salida esperada es `itaca-idoceo 0.8.0`.

## Privacidad

Todo el procesamiento se realiza localmente. No compartas PDF, XLSX ni fotografías reales, ni nombres, NIA u otros datos del alumnado. Para incidencias utiliza únicamente el diagnóstico anonimizado de la aplicación o describe el comportamiento sin datos identificativos.
