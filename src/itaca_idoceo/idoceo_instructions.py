from __future__ import annotations


def build_import_instructions(*, has_photos: bool, normalize_names: bool) -> str:
    lines = [
        "ITACA → iDoceo | guía de importación",
        "",
        "CLASE NUEVA",
        "1. En la pantalla principal de iDoceo, pulsa + en la esquina inferior derecha.",
        "2. Elige Clase y escribe el nombre que quieras dar a la clase.",
        "3. En la ventana de la clase, abre la pestaña Herramientas.",
        "4. Pulsa Importar fichero CSV/XLS y selecciona el XLSX generado.",
        "5. Asigna Apellidos y Nombre a sus campos personales. Si hay NIA, asígnalo",
        "   al campo de identificación del alumno (Número de identificación / ID).",
        "6. REPETIX y MATÈRIA/MÒDUL son datos opcionales: no los dejes seleccionados",
        "   accidentalmente como columnas de notas.",
        "",
        "ACTUALIZAR UNA CLASE EXISTENTE SIN PERDER LA EVALUACIÓN",
        "Puedes volver a importar el XLSX completo y, en el último paso del asistente,",
        "añadir los datos a la clase que ya existe. iDoceo intenta reconocer al alumnado",
        "con el mismo nombre: no lo vuelve a crear, actualiza sus datos personales y añade",
        "los alumnos nuevos. El XLSX generado por esta herramienta no contiene columnas de",
        "evaluación, por lo que no necesita sustituir las notas que ya tengas en iDoceo.",
        "",
        "Importante: esta actualización no debe interpretarse como una sincronización de",
        "bajas. Si un alumno ya estaba en iDoceo pero ha dejado de pertenecer a la clase,",
        "revísalo o elimínalo manualmente en iDoceo si procede.",
        "",
    ]

    if normalize_names:
        lines.extend(
            [
                "NORMALIZACIÓN DE NOMBRES ACTIVADA",
                "Los nombres escritos completamente en mayúsculas se han pasado a una",
                "capitalización más natural. Se preservan las palabras que ya contenían",
                "minúsculas, los nombres con guion/apóstrofo y partículas frecuentes como",
                "de, del, de la, da o dos. Es una heurística de presentación y puede tener",
                "excepciones.",
                "",
                "Si vas a actualizar más adelante una clase ya existente, usa la misma opción",
                "de normalización que utilizaste en la primera importación: iDoceo basa la",
                "detección de alumnado existente en el nombre y no conviene cambiar su forma",
                "entre importaciones.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "NOMBRES SIN NORMALIZAR",
                "Los nombres se han conservado tal como aparecen en ITACA. Si ya habías",
                "importado esta clase antes, mantener el mismo criterio facilita que iDoceo",
                "reconozca al alumnado existente al volver a importar.",
                "",
            ]
        )

    if has_photos:
        lines.extend(
            [
                "IMPORTACIÓN MASIVA DE FOTOS",
                "Hazla después de importar/actualizar el alumnado:",
                "1. Entra en la clase.",
                "2. En la columna izquierda abre Plano.",
                "3. Pulsa el botón del martillo de la esquina superior derecha.",
                "4. Elige Importación masiva.",
                "5. En Selecciona campos personales, elige un único criterio:",
                "   - fotos_por_nia/: Número de identificación.",
                "   - fotos_por_nombre/: Apellidos, Nombre.",
                "",
                "iDoceo no combina varios campos en una misma importación masiva. Si existen",
                "las dos carpetas, importa primero fotos_por_nia y después fotos_por_nombre",
                "como una segunda pasada. Las fotos por nombre se generan sólo cuando no se",
                "ha podido recuperar un NIA inequívoco y conviene comprobar su asociación.",
                "",
            ]
        )

    lines.extend(
        [
            "Todos los archivos han sido generados localmente en este equipo.",
            "No compartas PDF, XLSX ni fotografías reales del alumnado para pedir soporte.",
            "",
        ]
    )
    return "\n".join(lines)
