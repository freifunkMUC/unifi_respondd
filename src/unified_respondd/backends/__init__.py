"""Controller backends.

A backend is a module providing:
    ControllerConfig: A dataclass with a from_dict(cfg) classmethod reading the
        backend specific keys of the configuration file.
    get_infos(cfg): Returns the model.Accesspoints of the controller or None on error.

Backends are imported lazily, so only the dependencies of the configured
backend have to be installed.
"""

import importlib

DEFAULT_BACKEND = "unifi"

BACKENDS = {
    "omada": "unified_respondd.backends.omada",
    "uisp": "unified_respondd.backends.uisp",
    "unifi": "unified_respondd.backends.unifi",
}


def load(name):
    """Imports and returns the backend module for the given name."""
    try:
        module_name = BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown backend '{name}', choose one of: {', '.join(sorted(BACKENDS))}"
        ) from None
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise ImportError(
            f"Backend '{name}' is missing the dependency '{e.name}', "
            f"install it with: pip install 'unified_respondd[{name}]'"
        ) from e
