from requests import get as rget
from typing import List
import uisp_respondd.config as config

import dataclasses

ffnodes = None

cfg = config.Config.from_dict(config.load_config())


@dataclasses.dataclass
class Accesspoint:
    """This class contains the information of an AP.
    Attributes:
        name: The name of the AP (alias in the unifi controller).
        mac: The MAC address of the AP.
        snmp_location: The location of the AP (SNMP location in the unifi controller).
        latitude: The latitude of the AP.
        longitude: The longitude of the AP.
        model: The hardware model of the AP.
        firmware: The firmware information of the AP.
        uptime: The uptime of the AP.
    """

    name: str
    mac: str
    latitude: float
    longitude: float
    neighbour: str


@dataclasses.dataclass
class Accesspoints:
    """This class contains the information of all APs.
    Attributes:
        accesspoints: A list of Accesspoint objects."""

    accesspoints: List[Accesspoint]


def scrape(url, token):
    """returns remote json"""
    try:
        return rget(url, headers={"X-Auth-Token": token}).json()
    except Exception:
        return ""


def get_hostname(json):
    """returns name of device"""
    try:
        return json["identification"]["hostname"]
    except Exception:
        return ""


def get_mac(json):
    """returns name of device"""
    try:
        return json["identification"]["mac"]
    except Exception:
        return ""


def get_location(json):
    """returns location of device"""
    try:
        return json.get("location").get("latitude", 0), json.get("location").get(
            "longitude", 0
        )
    except Exception:
        return 0, 0


def get_apDevice(json):
    """returns apDevice"""
    try:
        print(json["attributes"]["apDevice"]["name"])
        return json["attributes"]["apDevice"]["name"]
    except Exception:
        return ""


def get_infos():
    aps = Accesspoints(accesspoints=[])
    devices = scrape(cfg.controller_url, cfg.token)
    if devices:
        for device in devices:
            if "Router" not in get_hostname(device):
                aps.accesspoints.append(
                    Accesspoint(
                        name=get_hostname(device),
                        mac=get_mac(device),
                        latitude=float(get_location(device)[0]),
                        longitude=float(get_location(device)[1]),
                        neighbour=get_apDevice(device),
                    )
                )
    return aps
