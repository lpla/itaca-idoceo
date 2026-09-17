# ITACA → iDoceo 0.8.0a1 — versión de prueba

Esta versión alpha está destinada a pruebas en entornos reales antes de cerrar la compatibilidad con los listados actuales con fotografías y la importación final en iDoceo.

## Novedades principales

- Soporte para listados actuales de alumnado con fotografías, incluidos nombres multilínea y casillas «Fotografía no disponible».
- Cruce local con todos los listados tabulares de referencia disponibles para recuperar NIA y metadatos sin reintroducir alumnado que ya no figure en la clase actual.
- Flujo de una sola pasada: se pueden seleccionar a la vez todos los PDF de referencia del centro y los PDF actuales de las materias impartidas.
- Exportación de fotografías por NIA cuando existe una coincidencia inequívoca y fallback por nombre cuando un alumno actual no aparece en las referencias.
- Conservación del alumnado actual sin NIA cuando no existe en las referencias antiguas; nunca se inventan identificadores.
- Estados de resultado diferenciados entre casos listos, fotografías ausentes, avisos tolerables y coincidencias ambiguas que requieren revisión.
- Carpetas de salida nombradas con el grupo extraído del contenido del PDF, no con nombres opacos del tipo `verReport_...`.
- El modo con sólo listados tabulares de referencia sigue generando un XLSX por grupo.

## Limitaciones conocidas de esta alpha

- La importación real de fotografías por ID/NIA en una versión actual de iDoceo todavía debe validarse en dispositivo.
- Si el mismo profesor descarga varios listados actuales de materias distintas para el mismo grupo, el PDF no contiene el nombre de la materia. Las salidas se distinguen de forma segura con sufijos `__2`, `__3`, etc.; la herramienta no pide al usuario que introduzca manualmente la materia.
- Las fotografías de alumnado actual sin NIA se preparan por nombre y deben comprobarse después de importarlas en iDoceo.

## Instalación para testers

Cuando `0.8.0a1` esté publicada en PyPI, instalar explícitamente la prerelease:

```text
pipx install --force 'itaca-idoceo==0.8.0a1'
itaca-idoceo integrate --replace
```

Comprobar la versión:

```text
itaca-idoceo --version
```

La salida esperada es `itaca-idoceo 0.8.0a1`.

## Qué conviene probar

1. Sólo listados tabulares de referencia: comprobar que se siguen generando XLSX con nombres basados en `GRUP`.
2. Referencias + uno o varios listados actuales con fotos en la misma ejecución.
3. Clases con todas las fotografías, con fotografías ausentes y con alumnado nuevo que no aparezca en las referencias.
4. Varios listados actuales del mismo grupo.
5. GUI, Acción rápida del sistema y comando `itaca-idoceo convert`.
6. Cuando haya un dispositivo con iDoceo disponible, importar el XLSX y después las fotografías por NIA/ID; probar también el fallback por nombre si aparece algún caso real.

## Privacidad durante las pruebas

Todo el procesamiento se realiza localmente. No compartas PDF, XLSX ni fotografías reales, ni nombres, NIA u otros datos del alumnado. Para incidencias utiliza únicamente los diagnósticos anonimizados que genera la aplicación o describe el comportamiento sin datos identificativos.
