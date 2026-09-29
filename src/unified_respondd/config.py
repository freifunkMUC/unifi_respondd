#!/usr/bin/env python3
import dataclasses
import os
import sys
from typing import Any, Dict, List, Optional

import yaml

from unified_respondd import backends

# The first entry is the current name, the others are kept for existing deployments.
CONFIG_OS_ENVS = ("UNIFIED_RESPONDD_CONFIG_FILE", "UNIFI_RESPONDD_CONFIG_FILE")
CONFIG_DEFAULT_LOCATIONS = ("./unified_respondd.yaml", "./unifi_respondd.yaml")

# How to handle APs without a location (0/0): report them at 0/0, omit the location
# (listed, but not on the map) or skip them completely
UNKNOWN_LOCATION_MODES = ("report", "omit", "skip")


class Error(Exception):
    """Base Exception handling class."""


class ConfigFileNotFoundError(Error):
    """File could not be found on disk."""


def _unknown_location(cfg: Dict[str, Any], default: str) -> str:
    unknown_location = cfg.get("unknown_location", default)
    if unknown_location not in UNKNOWN_LOCATION_MODES:
        raise ValueError(
            f"Invalid unknown_location '{unknown_location}', "
            f"choose one of: {', '.join(UNKNOWN_LOCATION_MODES)}"
        )
    return unknown_location


@dataclasses.dataclass
class Controller:
    """A controller to query.
    Attributes:
        name: The name of the controller used in the logs.
        backend: The name of the controller backend, e.g. "unifi".
        config: The backend specific configuration (backend.ControllerConfig).
        unknown_location: How to handle APs without a location, see UNKNOWN_LOCATION_MODES.
    """

    name: str
    backend: str
    config: Any
    unknown_location: str = "report"

    @classmethod
    def from_dict(
        cls, cfg: Dict[str, Any], unknown_location: str, index: Optional[int] = None
    ) -> "Controller":
        """Creates a Controller from its part of the configuration file.
        Arguments:
            cfg: The keys of the controller.
            unknown_location: The default from the top level of the configuration.
            index: The position in the controllers list, used for the default name.
        """
        backend = cfg.get("backend", backends.DEFAULT_BACKEND)
        default_name = backend if index is None else f"{backend}{index}"
        return cls(
            name=cfg.get("name", default_name),
            backend=backend,
            config=backends.load(backend).ControllerConfig.from_dict(cfg),
            unknown_location=_unknown_location(cfg, unknown_location),
        )


@dataclasses.dataclass
class Config:
    """A representation of the configuration file.
    Attributes:
        controllers: The controllers to query. A config without a "controllers" list
            is a single controller, the backend keys are at the top level then.
    """

    controllers: List[Controller]

    multicast_address: str
    multicast_port: int
    unicast_address: str
    unicast_port: int
    interface: str
    verbose: bool = False
    multicast_enabled: bool = True

    @classmethod
    def from_dict(cls, cfg: Dict[str, str]) -> "Config":
        """Creates a Config object from a configuration file.
        Arguments:
            cfg: The configuration file as a dict.
        Returns:
            A Config object.
        """
        unknown_location = _unknown_location(cfg, "report")
        if "controllers" in cfg:
            if not isinstance(cfg["controllers"], list) or not cfg["controllers"]:
                raise ValueError("controllers must be a non-empty list")
            controllers = [
                Controller.from_dict(controller, unknown_location, index)
                for index, controller in enumerate(cfg["controllers"], start=1)
            ]
        else:
            controllers = [Controller.from_dict(cfg, unknown_location)]

        return cls(
            controllers=controllers,
            multicast_enabled=cfg["multicast_enabled"],
            multicast_address=cfg["multicast_address"],
            multicast_port=cfg["multicast_port"],
            unicast_address=cfg["unicast_address"],
            unicast_port=cfg["unicast_port"],
            interface=cfg["interface"],
            verbose=cfg["verbose"],
        )


def config_file_path() -> str:
    """Returns the path of the configuration file.
    An environment variable takes precedence over the default locations.
    """
    for env in CONFIG_OS_ENVS:
        if os.environ.get(env):
            return os.environ[env]
    for location in CONFIG_DEFAULT_LOCATIONS:
        if os.path.isfile(location):
            return location
    return CONFIG_DEFAULT_LOCATIONS[0]


def load_config() -> Dict[str, str]:
    """Fetches and validates configuration file from disk.
    Returns:
        Linted configuration file.
    """
    cfg_contents = fetch_config_from_disk()
    try:
        config = yaml.safe_load(cfg_contents)
    except yaml.YAMLError as e:
        print(f"Failed to load YAML file: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        _ = Config.from_dict(config)
        return config
    except (KeyError, TypeError, ValueError, ImportError) as e:
        print(f"Failed to lint file: {e}", file=sys.stderr)
        sys.exit(2)


def fetch_config_from_disk() -> str:
    """Fetches config file from disk and returns as string.
    Raises:
        ConfigFileNotFoundError: If we could not find the configuration file on disk.
    Returns:
        The file contents as string.
    """
    config_file = config_file_path()
    try:
        with open(config_file, "r") as stream:
            return stream.read()
    except FileNotFoundError as e:
        raise ConfigFileNotFoundError(
            f"Could not locate configuration file in {config_file}"
        ) from e
