#!/usr/bin/env python3
import dataclasses
import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import yaml

UNIFI_RESPONDD_CONFIG_OS_ENV = "UNIFI_RESPONDD_CONFIG_FILE"
UNIFI_RESPONDD_CONFIG_DEFAULT_LOCATION = "./unifi_respondd.yaml"


class Error(Exception):
    """Base Exception handling class."""


class ConfigFileNotFoundError(Error):
    """File could not be found on disk."""


@dataclasses.dataclass
class ControllerConfig:
    """A representation of one configured controller instance.
    Attributes:
        type: The vendor registry key selecting the client implementation (e.g. "unifi", "omada").
        name: A unique label for this controller, used in logs.
        controller_url: The controller URL.
        controller_port: The controller port. UniFi-specific; ignored by vendors that embed the port in controller_url.
        username: The username for the controller.
        password: The password for the controller.
        ssid_regex: The regex used to match Freifunk SSIDs on this controller.
        offloader_mac: A mapping of site name to offloader MAC address.
        ssl_verify: Whether to verify the controller's TLS certificate.
        version: The controller API version. UniFi-specific; ignored by other vendors.
    """

    type: str
    name: str
    controller_url: str
    username: str
    password: str
    ssid_regex: str
    offloader_mac: Dict[str, str]
    controller_port: Optional[int] = None
    ssl_verify: bool = True
    version: str = "v5"

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> "ControllerConfig":
        """Creates a ControllerConfig object from a configuration dict.
        Arguments:
            cfg: One entry of the configuration file's `controllers` list.
        Returns:
            A ControllerConfig object.
        """

        return cls(
            type=cfg["type"],
            name=cfg.get("name", cfg["controller_url"]),
            controller_url=cfg["controller_url"],
            controller_port=cfg.get("controller_port"),
            username=cfg["username"],
            password=cfg["password"],
            ssid_regex=cfg["ssid_regex"],
            offloader_mac=cfg["offloader_mac"],
            ssl_verify=cfg.get("ssl_verify", True),
            version=cfg.get("version", "v5"),
        )


@dataclasses.dataclass
class Config:
    """A representation of the configuration file.
    Attributes:
        controllers: The list of configured controller instances.
        nodelist: The URL of the meshviewer.json map, shared across all controllers.
        fallback_domain: The default domain code used when a controller/offloader has none.
    """

    controllers: List[ControllerConfig]
    nodelist: str
    fallback_domain: str

    multicast_address: str
    multicast_port: int
    unicast_address: str
    unicast_port: int
    interface: str
    verbose: bool = False
    multicast_enabled: bool = True

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> "Config":
        """Creates a Config object from a configuration file.
        Arguments:
            cfg: The configuration file as a dict.
        Returns:
            A Config object.
        """

        if "controllers" in cfg:
            controllers = [ControllerConfig.from_dict(c) for c in cfg["controllers"]]
        else:
            # Legacy flat single-UniFi-controller format (pre-multi-controller
            # unifi_respondd.yaml). Synthesized into a one-entry controllers
            # list so every downstream consumer only ever deals with the new
            # shape.
            controllers = [
                ControllerConfig.from_dict(
                    {
                        "type": "unifi",
                        "name": cfg["controller_url"],
                        "controller_url": cfg["controller_url"],
                        "controller_port": cfg["controller_port"],
                        "username": cfg["username"],
                        "password": cfg["password"],
                        "ssid_regex": cfg["ssid_regex"],
                        "offloader_mac": cfg["offloader_mac"],
                        "version": cfg["version"],
                        "ssl_verify": cfg["ssl_verify"],
                    }
                )
            ]

        return cls(
            controllers=controllers,
            nodelist=cfg["nodelist"],
            fallback_domain=cfg.get("fallback_domain", "unifi_respondd_fallback"),
            multicast_enabled=cfg["multicast_enabled"],
            multicast_address=cfg["multicast_address"],
            multicast_port=cfg["multicast_port"],
            unicast_address=cfg["unicast_address"],
            unicast_port=cfg["unicast_port"],
            interface=cfg["interface"],
            verbose=cfg["verbose"],
        )


@lru_cache(maxsize=10)
def fetch_from_config(key: str) -> Optional[Union[Dict[str, Any], List[str]]]:
    """Fetches a specific key from configuration.
    Arguments:
        key: The named key to fetch.
    Returns:
        The config value associated with the key
    """
    return load_config().get(key)


def load_config() -> Dict[str, str]:
    """Fetches and validates configuration file from disk.
    Returns:
        Linted configuration file.
    """
    cfg_contents = fetch_config_from_disk()
    try:
        config = yaml.safe_load(cfg_contents)
    except yaml.YAMLError as e:
        print("Failed to load YAML file: %s", e)
        sys.exit(1)
    try:
        _ = Config.from_dict(config)
        return config
    except (KeyError, TypeError) as e:
        print("Failed to lint file: %s", e)
        sys.exit(2)


def fetch_config_from_disk() -> str:
    """Fetches config file from disk and returns as string.
    Raises:
        ConfigFileNotFoundError: If we could not find the configuration file on disk.
    Returns:
        The file contents as string.
    """
    config_file = os.environ.get(
        UNIFI_RESPONDD_CONFIG_OS_ENV, UNIFI_RESPONDD_CONFIG_DEFAULT_LOCATION
    )
    try:
        with open(config_file, "r") as stream:
            return stream.read()
    except FileNotFoundError as e:
        raise ConfigFileNotFoundError(
            f"Could not locate configuration file in {config_file}"
        ) from e
