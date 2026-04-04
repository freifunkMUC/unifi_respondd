from requests import get as rget
from typing import List, Any
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
    domain_code: str
    firmware: str
    model: str
    uptime: int
    cpu: int
    ram_used_percent: int


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
    links = scrape(cfg.controller_url + "/data-links", cfg.token)
    if links:
        for link in links:
            if link["from"]["device"]["identification"]["name"] == get_hostname(json):
                try:
                    return link["to"]["device"]["identification"]["name"]
                except Exception:
                    return ""


def get_firmware(json):
    """returns the firmware version"""
    try:
        return json["identification"]["firmwareVersion"]
    except Exception:
        return ""


def get_model(json):
    """returns the model"""
    try:
        return json["identification"]["model"]
    except Exception:
        return ""


def get_uptime(json):
    """returns the uptime"""
    try:
        overview = json.get("overview", {})
        uptime = overview.get("uptime")
        if uptime is None:
            uptime = overview.get("serviceUptime")
        if uptime is None:
            return 0

        uptime = _as_int(uptime, 0)
        if uptime <= 0:
            return 0

        # UISP instances may report uptime in ms. Convert when value is implausibly high for seconds.
        if uptime > 10 * 365 * 24 * 60 * 60:
            uptime = int(uptime / 1000)
        return max(uptime, 0)
    except Exception:
        return 0


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def get_cpu_percent(json):
    """returns CPU usage in percent from 0..100"""
    value = _as_int(json.get("overview", {}).get("cpu"), 0)
    return max(0, min(value, 100))


def get_ram_used_percent(json):
    """returns RAM usage in percent from 0..100"""
    value = _as_int(json.get("overview", {}).get("ram"), 0)
    return max(0, min(value, 100))


def get_infos():
    aps = Accesspoints(accesspoints=[])
    devices = scrape(cfg.controller_url + "/devices", cfg.token)
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
                        domain_code="uisp_respondd_fallback",
                        firmware=get_firmware(device),
                        model=get_model(device),
                        uptime=get_uptime(device),
                        cpu=get_cpu_percent(device),
                        ram_used_percent=get_ram_used_percent(device),
                    )
                )
    return aps
