# Instalación de ITACA → iDoceo

Esta guía está pensada para usuarios que no trabajan habitualmente con Python. La terminal sólo es necesaria para instalar, actualizar o desinstalar la aplicación; después puedes usar el acceso gráfico creado por el propio programa.

La aplicación requiere **Python 3.12 o posterior**.

## Windows

### 1. Instalar Python

Descarga Python desde [python.org](https://www.python.org/downloads/windows/) e instálalo. Durante la instalación, activa la opción para añadir Python al `PATH` si aparece.

### 2. Abrir PowerShell

Abre el menú Inicio, escribe `PowerShell` y ejecútalo.

### 3. Instalar pipx

Copia y pega estas dos órdenes, una cada vez:

```text
py -m pip install --user pipx
py -m pipx ensurepath
```

Cierra PowerShell y vuelve a abrirlo.

### 4. Instalar ITACA → iDoceo

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

El segundo comando crea un acceso gráfico para abrir la aplicación sin tener que volver a usar la terminal.

## macOS

La forma recomendada es usar Homebrew. Si no lo tienes instalado, sigue primero las instrucciones oficiales de [brew.sh](https://brew.sh/).

### 1. Abrir Terminal

Abre **Aplicaciones → Utilidades → Terminal**.

### 2. Instalar Python, Tkinter y pipx

```text
brew install python python-tk pipx
pipx ensurepath
```

Cierra Terminal y vuelve a abrirla.

### 3. Instalar ITACA → iDoceo

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

Se crea una aplicación en `~/Applications/ITACA a iDoceo.app` y también una Acción rápida de Finder llamada **Abrir en ITACA a iDoceo**.

### 4. Activar la Acción rápida de Finder

La primera vez, macOS puede dejar la Acción rápida desactivada. Para activarla:

1. Abre **Ajustes del Sistema**.
2. Entra en **Privacidad y seguridad → Extensiones → Finder**.
3. Activa **Abrir en ITACA a iDoceo**.

Después puedes seleccionar en Finder un PDF, varios archivos o una carpeta y usar **clic derecho → Acciones rápidas → Abrir en ITACA a iDoceo**. También aparece en **Finder → Servicios** cuando hay una selección compatible.

Si actualizas desde una versión anterior y la Acción rápida no aparece, ejecuta una vez:

```text
itaca-idoceo integrate --replace
```

y comprueba de nuevo **Ajustes del Sistema → Privacidad y seguridad → Extensiones → Finder**.

## LliureX / Ubuntu y derivados

### 1. Abrir Terminal

Abre la aplicación **Terminal** del sistema.

### 2. Instalar Python, Tkinter y pipx

```text
sudo apt update
sudo apt install python3 python3-tk pipx
pipx ensurepath
```

Cierra Terminal y vuelve a abrirla.

### 3. Comprobar la versión de Python

```text
python3 --version
```

Debe indicar **3.12 o posterior**. Si muestra una versión más antigua, no continúes con una instalación alternativa improvisada: abre una incidencia indicando únicamente tu versión de LliureX/Ubuntu y de Python, sin adjuntar ningún PDF de alumnado.

### 4. Instalar ITACA → iDoceo

```text
pipx install itaca-idoceo
itaca-idoceo integrate
```

Se crea un lanzador gráfico `.desktop` para abrir la aplicación.

## Comprobar que está instalado

En cualquier sistema puedes comprobar la versión instalada con:

```text
itaca-idoceo --version
```

Después abre la aplicación desde el acceso gráfico creado. Si no aparece o no funciona, ejecuta:

```text
itaca-idoceo integrate --replace
```

## Actualizar

```text
pipx upgrade itaca-idoceo
```

Si tras una actualización el acceso gráfico deja de funcionar:

```text
itaca-idoceo integrate --replace
```

## Desinstalar

Primero elimina los accesos creados por la aplicación y después el paquete:

```text
itaca-idoceo uninstall-integration
pipx uninstall itaca-idoceo
```

## Si la instalación falla

No necesitas compartir ningún PDF para pedir ayuda con la instalación. Indica únicamente:

- sistema operativo y versión;
- resultado de `python --version`, `python3 --version` o `py --version`, según el sistema;
- resultado de `pipx --version` si llega a funcionar;
- mensaje de error de la instalación, revisando antes que no contenga rutas o nombres personales que no quieras publicar.

Para errores al procesar listados, consulta [Seguridad y privacidad](../SECURITY.md) antes de abrir una incidencia.
