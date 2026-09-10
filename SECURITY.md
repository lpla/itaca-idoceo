# Seguridad y privacidad

Los PDF de ITACA pueden contener datos personales de menores. La regla principal para pedir ayuda es sencilla: **no compartas el PDF original ni el XLSX generado**.

## Qué no debes adjuntar a una incidencia

No publiques PDF, XLSX, capturas con datos visibles, nombres del alumnado, NIA, REPETIX, MATÈRIA/MÒDUL, centro, grupo, tutor ni rutas locales que identifiquen personas o equipos.

## Cómo informar de un fallo de extracción

1. Abre ITACA → iDoceo.
2. Ve a **Ayuda → Copiar diagnóstico anonimizado**.
3. Revisa el texto copiado.
4. Pégalo en la incidencia junto con una descripción que use únicamente estructura o recuentos no identificativos.

El diagnóstico omite nombres y rutas de ficheros, centro, `GRUP`, `CURS`, valor de `TUTOR`, nombres del alumnado, NIA, REPETIX y MATÈRIA/MÒDUL. Los mensajes de error no reconocidos se sustituyen por un texto genérico para reducir el riesgo de filtrar información accidentalmente.

Si necesitas describir algo adicional, utiliza expresiones como «se detectan 29 alumnos y deberían ser 30» o «la cabecera cambia de MATÈRIA a MÒDUL». No modifiques un PDF real para intentar anonimizarlo y compartirlo: **el PDF no debe salir del equipo autorizado**.

## Informes `layout-report`

Para algunos problemas de maquetación el mantenedor puede pedir un informe generado con `itaca-idoceo layout-report`. Ese informe está diseñado para anonimizar el contenido y conservar únicamente la geometría necesaria para depuración, pero debes revisarlo antes de compartirlo.

La salida de `itaca-idoceo check` es para inspección local y **no** debe pegarse en una incidencia pública porque puede mostrar metadatos del listado.

Las instrucciones técnicas están en [Uso avanzado y diagnóstico técnico](docs/ADVANCED.md).

## Procesamiento local

La extracción del PDF y la generación del XLSX se realizan localmente. El programa no incorpora telemetría ni analítica y no necesita servicios remotos para procesar los listados. Las conexiones de red se limitan a las que realice el gestor de paquetes durante la instalación o actualización de dependencias.

## Vulnerabilidades del software

Si el problema es una vulnerabilidad del propio programa y publicarla pudiera poner en riesgo a usuarios, evita incluir datos reales de alumnado incluso en una comunicación privada. Describe el problema con entradas sintéticas o con código mínimo que lo reproduzca.
