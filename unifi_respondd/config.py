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
class ProviderConfig:
    """Configuration for a single provider.
    Attributes:
        type: The type of provider (e.g., 'unifi', 'omada', 'uisp').
        config: Provider-specific configuration dictionary.
    """

    type: str
    config: Dict[str, Any]


@dataclasses.dataclass
class Config:
    """A representation of the configuration file.
    Attributes:
        providers: List of provider configurations (new format).
        multicast_address: The multicast address for respondd.
        multicast_port: The multicast port for respondd.
        unicast_address: The unicast address for respondd.
        unicast_port: The unicast port for respondd.
        interface: The network interface to use.
        verbose: Enable verbose logging.
        multicast_enabled: Enable multicast support.

        # Legacy fields for backward compatibility
        controller_url: The unifi controller URL (deprecated).
        controller_port: The unifi Controller port (deprecated).
        username: The username for unifi controller (deprecated).
        password: The password for unifi controller (deprecated).
        ssid_regex: SSID regex pattern (deprecated).
        offloader_mac: Offloader MAC addresses (deprecated).
        nodelist: Nodelist URL (deprecated).
        fallback_domain: Fallback domain (deprecated).
        version: UniFi version (deprecated).
        ssl_verify: SSL verification (deprecated).
    """

    multicast_address: str
    multicast_port: int
    unicast_address: str
    unicast_port: int
    interface: str
    verbose: bool = False
    multicast_enabled: bool = True

    # New multi-provider support
    providers: Optional[List[ProviderConfig]] = None

    # Legacy single-controller fields (for backward compatibility)
    controller_url: Optional[str] = None
    controller_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssid_regex: Optional[str] = None
    offloader_mac: Optional[Dict[str, str]] = None
    nodelist: Optional[str] = None
    fallback_domain: Optional[str] = None
    version: Optional[str] = None
    ssl_verify: Optional[bool] = None

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> "Config":
        """Creates a Config object from a configuration file.

        Supports both legacy format (single UniFi controller) and new format (multiple providers).

        Arguments:
            cfg: The configuration file as a dict.
        Returns:
            A Config object.
        """
        # Check if this is the new multi-provider format
        providers = None
        if "providers" in cfg:
            providers = [
                ProviderConfig(type=p["type"], config=p["config"])
                for p in cfg["providers"]
            ]

        # Handle legacy format - if no providers but has controller_url, create a provider
        if providers is None and "controller_url" in cfg:
            # Legacy format detected - create a single UniFi provider from root config
            provider_config = {
                "controller_url": cfg["controller_url"],
                "controller_port": cfg["controller_port"],
                "username": cfg["username"],
                "password": cfg["password"],
                "ssid_regex": cfg["ssid_regex"],
                "offloader_mac": cfg["offloader_mac"],
                "nodelist": cfg["nodelist"],
                "fallback_domain": cfg.get(
                    "fallback_domain", "unifi_respondd_fallback"
                ),
                "version": cfg.get("version", "v5"),
                "ssl_verify": cfg.get("ssl_verify", True),
            }
            providers = [ProviderConfig(type="unifi", config=provider_config)]

        return cls(
            providers=providers,
            multicast_enabled=cfg["multicast_enabled"],
            multicast_address=cfg["multicast_address"],
            multicast_port=cfg["multicast_port"],
            unicast_address=cfg["unicast_address"],
            unicast_port=cfg["unicast_port"],
            interface=cfg["interface"],
            verbose=cfg["verbose"],
            # Legacy fields (optional, only populated in legacy format)
            controller_url=cfg.get("controller_url"),
            controller_port=cfg.get("controller_port"),
            username=cfg.get("username"),
            password=cfg.get("password"),
            ssid_regex=cfg.get("ssid_regex"),
            offloader_mac=cfg.get("offloader_mac"),
            nodelist=cfg.get("nodelist"),
            fallback_domain=cfg.get("fallback_domain", "unifi_respondd_fallback"),
            version=cfg.get("version", "v5"),
            ssl_verify=cfg.get("ssl_verify", True),
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
        print(
            "Make sure your config has either 'providers' list or legacy UniFi controller fields"
        )
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
