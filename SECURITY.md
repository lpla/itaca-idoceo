# Seguridad y privacidad

## Datos tratados

ITACA → iDoceo procesa localmente PDF que pueden contener datos personales de alumnado. Los listados reales no deben salir del ordenador autorizado ni adjuntarse a incidencias públicas del proyecto.

No adjuntes PDF, XLSX, nombres, NIA, REPETIX, MATÈRIA, información identificativa del centro, nombres de tutores ni capturas que contengan esos datos.

## Cómo informar de un fallo

En la interfaz utiliza **Ayuda → Copiar diagnóstico anonimizado** y pega ese texto en la incidencia. El diagnóstico omite nombres y rutas de ficheros, centro, `GRUP`, `CURS`, valor de `TUTOR`, nombres del alumnado, NIA, REPETIX y MATÈRIA. Los mensajes de error no reconocidos se sustituyen por un texto genérico para evitar que una excepción futura pueda filtrar accidentalmente una ruta u otro dato sensible.

Si hace falta describir algo adicional, utiliza únicamente recuentos o estructura no identificativa: número de páginas, número esperado/detectado de alumnos o la posición relativa de una cabecera. No inventes ni sustituyas datos reales por otros dentro del PDF para compartirlo: el documento no debe compartirse en ningún caso.

## Procesamiento local

La extracción del PDF y la generación del XLSX no requieren servicios remotos, telemetría ni analítica. Las dependencias se instalan mediante el gestor elegido por el usuario; se recomienda `pipx`.

Para actualizar una instalación publicada en PyPI:

```text
pipx upgrade itaca-idoceo
```

## Vulnerabilidades del software

Si el problema es una vulnerabilidad del propio programa y publicarla pudiera poner en riesgo a usuarios, evita incluir datos reales de alumnado incluso en una comunicación privada. Describe el problema con entradas sintéticas o con código mínimo que lo reproduzca.
