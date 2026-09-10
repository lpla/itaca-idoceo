# Publicación para mantenedores

Este documento está dirigido a mantenimiento del proyecto. Para instalar y usar la aplicación consulta el [README](../README.md) y la [guía de instalación](INSTALL.md).

El proyecto utiliza `itaca-idoceo` como nombre en GitHub y PyPI. El paquete importable es `itaca_idoceo` y el comando principal es `itaca-idoceo`.

La distribución está publicada en [TestPyPI](https://test.pypi.org/project/itaca-idoceo/) y [PyPI](https://pypi.org/project/itaca-idoceo/). Los dos servicios son independientes y cada uno tiene su propia configuración de Trusted Publishing.

## Antes de publicar una versión

1. Actualizar la versión de forma coherente en `pyproject.toml`, `src/itaca_idoceo/__init__.py` y `SCRIPT_VERSION` en `src/itaca_idoceo/core.py`.
2. Actualizar `CHANGELOG.md` y cualquier documentación que dependa de esa versión.
3. Ejecutar, si es posible:

```text
python -m pytest
python -m build
python -m twine check dist/*
```

4. Hacer push a `main` y esperar a que **Tests** termine correctamente en toda la matriz de sistemas operativos y versiones de Python.

No incluir nunca PDF ni XLSX reales en tests, fixtures, artefactos de CI o incidencias.

Una versión ya publicada en PyPI o TestPyPI no puede sobrescribirse. Cualquier corrección del paquete, incluido el README que muestra PyPI, requiere una versión nueva.

## Trusted Publishing

Los workflows usan OIDC mediante `pypa/gh-action-pypi-publish`, sin API tokens persistentes.

Configuración de TestPyPI:

- owner: `lpla`
- repository: `itaca-idoceo`
- workflow: `testpypi.yml`
- environment: `testpypi`
- project name: `itaca-idoceo`

Configuración de PyPI:

- owner: `lpla`
- repository: `itaca-idoceo`
- workflow: `release.yml`
- environment: `pypi`
- project name: `itaca-idoceo`

Los environments de GitHub deben llamarse exactamente `testpypi` y `pypi`. Para producción puede añadirse aprobación manual al environment `pypi`.

Si hay que recrear un publisher, comprobar especialmente que se está configurando en el servicio correcto: `test.pypi.org` y `pypi.org` no comparten configuración.

## Probar en TestPyPI

`.github/workflows/testpypi.yml` se lanza manualmente desde **Actions → Publish to TestPyPI → Run workflow**. Construye wheel y sdist y los publica en TestPyPI.

Para una versión todavía no publicada en PyPI de producción:

```text
pipx install --force \
  --pip-args='--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/' \
  'itaca-idoceo==VERSION'

itaca-idoceo --version
itaca-idoceo integrate
```

Comprobar al menos que la instalación termina correctamente, que se informa de la versión esperada y que la GUI puede abrirse en un entorno representativo.

## Publicar en PyPI

La producción se dispara al publicar una GitHub Release:

1. Crear el tag `vVERSION` apuntando al commit validado de `main`.
2. Crear una GitHub Release con ese tag.
3. Marcarla como **pre-release** si es alpha, beta o release candidate.
4. Publicarla; guardarla como borrador no dispara el workflow.
5. `.github/workflows/release.yml` construye de nuevo wheel y sdist y los publica en PyPI mediante Trusted Publishing.
6. Comprobar que **Release to PyPI** termina en verde y que la versión aparece en PyPI.
7. Verificar una instalación limpia:

```text
pipx install --force 'itaca-idoceo==VERSION'
itaca-idoceo --version
```

No publicar una GitHub Release de producción hasta que la versión haya pasado CI y la prueba previa en TestPyPI.
