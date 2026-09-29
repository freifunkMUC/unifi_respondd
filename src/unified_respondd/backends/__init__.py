"""Controller backends.

A backend is a module implementing the Backend protocol. Backends are imported
lazily, so only the dependencies of the configured backend have to be installed.
"""

import importlib
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from unified_respondd.model import Accesspoints

DEFAULT_BACKEND = "unifi"

# Seconds to wait for a HTTP response, a hanging server must not block respondd
REQUEST_TIMEOUT = 30

BACKENDS = {
    "omada": "unified_respondd.backends.omada",
    "uisp": "unified_respondd.backends.uisp",
    "unifi": "unified_respondd.backends.unifi",
}


class ControllerConfig(Protocol):
    """The backend specific part of the configuration file."""

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> "ControllerConfig": ...


@runtime_checkable
class Backend(Protocol):
    """The interface of a backend module.
    Attributes:
        ControllerConfig: Reads the backend specific keys of the configuration file.
        get_infos: Returns the APs of the controller, None on error.
    """

    ControllerConfig: type

    def get_infos(self, cfg: Any) -> Optional[Accesspoints]: ...


def load(name) -> Backend:
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
