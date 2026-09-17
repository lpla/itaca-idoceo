from importlib.metadata import version

import itaca_idoceo
from itaca_idoceo import core


def test_package_and_legacy_manifest_versions_match():
    assert itaca_idoceo.__version__ == "0.8.0a1"
    assert core.SCRIPT_VERSION == itaca_idoceo.__version__
    assert version("itaca-idoceo") == itaca_idoceo.__version__
