# Publicación para mantenedores

El proyecto utiliza el nombre `itaca-idoceo` tanto en GitHub como en PyPI. El paquete Python importable es `itaca_idoceo` y el comando principal es `itaca-idoceo`.

## GitHub

Repositorio: `lpla/itaca-idoceo`.

Antes de publicar una versión, comprobar:

```text
python -m pytest
python -m build
python -m twine check dist/*
```

No incluir nunca PDF ni XLSX reales en tests, fixtures, artefactos de CI o incidencias.

## TestPyPI

`.github/workflows/testpypi.yml` utiliza Trusted Publishing (OIDC), sin API token persistente.

Configurar en TestPyPI un Pending Trusted Publisher con:

- owner: `lpla`
- repository: `itaca-idoceo`
- workflow: `testpypi.yml`
- environment: `testpypi`
- project name: `itaca-idoceo`

Crear también el Environment `testpypi` en GitHub y ejecutar manualmente **Publish to TestPyPI**.

URL prevista: `https://test.pypi.org/project/itaca-idoceo/`.

## PyPI

Configurar en PyPI un Pending Trusted Publisher con:

- owner: `lpla`
- repository: `itaca-idoceo`
- workflow: `release.yml`
- environment: `pypi`
- project name: `itaca-idoceo`

Crear el Environment `pypi` en GitHub. Se recomienda exigir aprobación manual para ese environment.

Al publicar una GitHub Release, `release.yml` construye las distribuciones y las publica mediante OIDC.

URL prevista: `https://pypi.org/project/itaca-idoceo/`.

Un Pending Trusted Publisher no reserva el nombre del proyecto hasta la primera publicación efectiva.
