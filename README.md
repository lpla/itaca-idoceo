# ITACA → iDoceo

Convierte **localmente** listados PDF de alumnado de ITACA (Generalitat Valenciana) en archivos `.xlsx` preparados para importar en iDoceo.

**Descarga e instalación:** [PyPI](https://pypi.org/project/itaca-idoceo/) · **Versiones:** [GitHub Releases](https://github.com/lpla/itaca-idoceo/releases)

> [!IMPORTANT]
> La herramienta no sube PDF ni datos del alumnado a ningún servicio. La lectura del PDF y la creación del XLSX se realizan íntegramente en el ordenador donde se ejecuta.

> [!NOTE]
> Este es un proyecto independiente. No está afiliado, respaldado ni mantenido por la Generalitat Valenciana ni por iDoceo.

## ¿Qué listados admite?

Actualmente está validado con **«LLISTAT D'ALUMNES AMB ASSIGNATURES» generado desde ITACA 3 / Gestión Administrativa**, incluidos listados de ESO, Bachillerato y FP.

Reconoce, entre otras, estas dos cabeceras:

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

Si ya tienes Python 3.12 o posterior y `pipx`, la instalación es simplemente:

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

En macOS, tras instalar, puede ser necesario activar una vez **Abrir en ITACA a iDoceo** en **Ajustes del Sistema → Privacidad y seguridad → Extensiones → Finder**. La [guía de instalación](docs/INSTALL.md#macos) explica el paso.

## Uso habitual

1. Abre **ITACA → iDoceo** desde el acceso creado en tu sistema.
2. Arrastra uno o varios PDF, una carpeta completa, o haz clic en el área superior para seleccionarlos.
3. Comprueba que cada grupo aparece como `Correcto`. Si aparece `Revisar` o `Error`, consulta los detalles antes de convertir.
4. Marca sólo los datos adicionales que quieras exportar: `NIA`, `REPETIX` y/o `MATÈRIA / MÒDUL`.
5. Genera los XLSX e impórtalos en iDoceo.

Por defecto, el XLSX contiene únicamente:

```text
Apellidos | Nombre
```

`NIA` está pensado para mapearlo al campo personal `ID` / `Student ID` de iDoceo. Si exportas `REPETIX` o `MATÈRIA / MÒDUL`, decide expresamente su destino durante la importación para evitar que iDoceo los interprete como columnas de notas.

Un mismo PDF puede contener varios grupos y la aplicación generará un XLSX por `GRUP`. También admite casos de Bachillerato en los que un mismo grupo contiene varias secciones `CURS` y casos en los que un nombre o la lista de materias ocupa varias líneas del PDF.

## Si algo no funciona

**No compartas el PDF real ni el XLSX generado.** Los listados pueden contener datos personales de menores.

En la aplicación usa **Ayuda → Copiar diagnóstico anonimizado** y pega ese texto en una incidencia de GitHub. El diagnóstico está diseñado para omitir nombres, NIA, centro, grupo, tutor, materias y rutas locales.

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

La mayoría de usuarios no necesita esta parte. La línea de comandos, el procesamiento por lotes y `layout-report` están documentados aparte:

[Uso avanzado y diagnóstico técnico](docs/ADVANCED.md)

## Privacidad y seguridad

El proyecto no incorpora telemetría ni analítica y no necesita servicios remotos para procesar los listados. Las dependencias se descargan únicamente durante la instalación o actualización mediante el gestor de paquetes elegido por el usuario.

Consulta [SECURITY.md](SECURITY.md) antes de abrir una incidencia.

## Licencia

Este proyecto se distribuye bajo **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. El texto completo se incluye en [LICENSE](LICENSE). PyMuPDF se distribuye bajo AGPL o licencia comercial, por lo que este proyecto adopta AGPL-3.0 para su distribución de código abierto.
