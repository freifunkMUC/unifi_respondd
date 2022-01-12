#!/usr/bin/env python3
from functools import lru_cache
import yaml
import os
from typing import List, Dict, Any, Union, Optional
import dataclasses
import sys

UNIFI_RESPONDD_CONFIG_OS_ENV = "UNIFI_RESPONDD_CONFIG_FILE"
UNIFI_RESPONDD_CONFIG_DEFAULT_LOCATION = "./unifi_respondd.yaml"


class Error(Exception):
    """Base Exception handling class."""


class ConfigFileNotFoundError(Error):
    """File could not be found on disk."""


@dataclasses.dataclass
class Config:
    """A representation of the configuration file.
    Attributes:
        controller_url: The unifi controller URL.
        controller_port: The unifi Controller port.
        username: The username for unifi controller.
        password: The password for unifi controller.
    """

    controller_url: str
    controller_port: int
    username: str
    password: str
    ssid_regex: str
    offloader_mac: Dict[str, str]
    nodelist: str

    multicast_address: str
    multicast_port: int
    unicast_address: str
    unicast_port: int
    interface: str
    verbose: bool = False
    multicast_enabled: bool = True

    version: str = "v5"
    ssl_verify: bool = True

    @classmethod
    def from_dict(cls, cfg: Dict[str, str]) -> "Config":
        """Creates a Config object from a configuration file.
        Arguments:
            cfg: The configuration file as a dict.
        Returns:
            A Config object.
        """

        return cls(
            controller_url=cfg["controller_url"],
            controller_port=cfg["controller_port"],
            username=cfg["username"],
            password=cfg["password"],
            ssid_regex=cfg["ssid_regex"],
            offloader_mac=cfg["offloader_mac"],
            nodelist=cfg["nodelist"],
            version=cfg["version"],
            ssl_verify=cfg["ssl_verify"],
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
