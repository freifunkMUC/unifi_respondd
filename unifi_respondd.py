#!/usr/bin/env python3

from unificontrol import UnifiClient
from typing import List, Dict, Any, Union, Optional
from geopy.geocoders import Nominatim
import time
import dataclasses
import yaml
import os
from functools import lru_cache

UNIFI_RESPONDD_CONFIG_OS_ENV = "SNMP_TO_INFLUX_CONFIG_FILE"
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

@dataclasses.dataclass
class Accesspoint:
    name: str
    mac: str
    snmp_location: str
    client_count: int
    latitude: float
    longitude: float

@dataclasses.dataclass
class Accesspoints:
    accesspoints: List[Accesspoint]

def get_sites(cfg):
    """This function returns a list of sites."""
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
    )
    client.login()
    sites = client.list_sites()
    return sites


def get_aps(cfg, site):
    """This function returns a list of APs."""
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
        site=site,
    )
    client.login()
    aps = client.list_devices()
    return aps


def get_clients_for_site(cfg, site):
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
        site=site,
    )
    client.login()
    clients = client.list_clients()
    return clients


def get_client_count_for_ap(ap_mac, clients):
    client_count = 0
    for client in clients:
        if client.get("ap_mac", "No mac") == ap_mac:
            client_count += 1
    return client_count


def get_location_by_address(address, app):
    """This function returns latitude and longitude of a given address."""
    time.sleep(1)
    try:
        return app.geocode(address).raw["lat"], app.geocode(address).raw["lon"]
    except:
        return get_location_by_address(address)


def main():
    cfg = Config.from_dict(load_config())
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    aps = Accesspoints(accesspoints=[])
    for site in get_sites(cfg):
        aps_for_site = get_aps(cfg, site["name"])
        clients = get_clients_for_site(cfg,site["name"])
        for ap in aps_for_site:
            lat, lon = 0, 0
            if ap.get("snmp_location", None) is not None:
                try:
                    lat, lon = get_location_by_address(ap["snmp_location"], geolookup)
                except:
                    pass

            aps.accesspoints.append(Accesspoint(
                name=ap.get("name", None),
                mac=ap.get("mac", None),
                snmp_location=ap.get("snmp_location", None),
                client_count=get_client_count_for_ap(ap.get("mac", None), clients),
                latitude=lat,
                longitude=lon
                ))
    print(aps)


if __name__ == "__main__":
    main()
