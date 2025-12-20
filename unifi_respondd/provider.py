#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from unifi_respondd import unifi_client


class Provider(ABC):
    """Base class for all providers that can supply access point information."""

    @abstractmethod
    def get_accesspoints(self) -> unifi_client.Accesspoints:
        """Fetches access point information from the provider.

        Returns:
            Accesspoints object containing a list of access points.
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> str:
        """Returns the type of provider (e.g., 'unifi', 'mikrotik', etc.)."""
        pass


class UnifiProvider(Provider):
    """Provider implementation for UniFi controllers."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the UniFi provider with configuration.

        Args:
            config: Dictionary containing UniFi-specific configuration:
                - controller_url: The UniFi controller URL
                - controller_port: The UniFi controller port
                - username: Username for authentication
                - password: Password for authentication
                - version: UniFi version (default: "v5")
                - ssl_verify: Whether to verify SSL certificates (default: True)
                - ssid_regex: Regex pattern to filter SSIDs
                - offloader_mac: Dictionary mapping site names to offloader MACs
                - nodelist: URL to the nodelist/meshviewer JSON
                - fallback_domain: Fallback domain name
        """
        self.controller_url = config["controller_url"]
        self.controller_port = config["controller_port"]
        self.username = config["username"]
        self.password = config["password"]
        self.version = config.get("version", "v5")
        self.ssl_verify = config.get("ssl_verify", True)
        self.ssid_regex = config["ssid_regex"]
        self.offloader_mac = config["offloader_mac"]
        self.nodelist = config["nodelist"]
        self.fallback_domain = config.get("fallback_domain", "unifi_respondd_fallback")

    def get_accesspoints(self) -> unifi_client.Accesspoints:
        """Fetches access point information from UniFi controller."""
        # Use the existing unifi_client logic but with this provider's config
        return unifi_client.get_infos_from_config(
            controller_url=self.controller_url,
            controller_port=self.controller_port,
            username=self.username,
            password=self.password,
            version=self.version,
            ssl_verify=self.ssl_verify,
            ssid_regex=self.ssid_regex,
            offloader_mac=self.offloader_mac,
            nodelist=self.nodelist,
            fallback_domain=self.fallback_domain,
        )

    def get_provider_type(self) -> str:
        """Returns 'unifi' as the provider type."""
        return "unifi"


def create_provider(provider_type: str, config: Dict[str, Any]) -> Provider:
    """Factory function to create a provider instance.

    Args:
        provider_type: Type of provider to create (e.g., 'unifi')
        config: Configuration dictionary for the provider

    Returns:
        Provider instance

    Raises:
        ValueError: If provider_type is not supported
    """
    if provider_type == "unifi":
        return UnifiProvider(config)
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")
