"""ITACA → iDoceo: conversión local de listados de alumnado."""

__version__ = "0.8.0"

# `core.SCRIPT_VERSION` sólo se conserva para el manifiesto del comando batch
# heredado. Sincronizarlo en tiempo de importación evita que ese resumen muestre
# una versión distinta a la distribución mientras se elimina esa duplicidad.
from . import core as _core

_core.SCRIPT_VERSION = __version__
del _core
