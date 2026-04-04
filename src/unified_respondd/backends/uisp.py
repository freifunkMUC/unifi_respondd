from requests import get as rget
from typing import List, Any, Optional
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
    uptime: Optional[int]
    cpu: Optional[int]
    ram_used_percent: Optional[int]
    loadavg: Optional[float]


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
        fw = json.get("identification", {}).get("firmwareVersion")
        if fw:
            return str(fw)
        return "unknown"
    except Exception:
        return "unknown"


def get_model(json):
    """returns the model"""
    try:
        ident = json.get("identification", {})
        model = ident.get("model")
        model_name = ident.get("modelName")
        dev_type = ident.get("type")

        if model and str(model).upper() != "UNKNOWN":
            return str(model)
        if model_name and str(model_name).lower() != "unknown":
            return str(model_name)
        if dev_type:
            return str(dev_type)
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def get_uptime(json):
    """returns the uptime"""
    try:
        overview = json.get("overview", {})
        uptime = overview.get("uptime")
        if uptime is None:
            uptime = overview.get("serviceUptime")
        if uptime is None:
            return None

        uptime = _as_int(uptime, 0)
        if uptime <= 0:
            return None

        # UISP instances may report uptime in ms. Convert when value is implausibly high for seconds.
        if uptime > 10 * 365 * 24 * 60 * 60:
            uptime = int(uptime / 1000)
        return max(uptime, 0)
    except Exception:
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def get_device_id(json):
    try:
        return json.get("identification", {}).get("id")
    except Exception:
        return None


def get_device_statistics(device_id: str, interval: str = "hour"):
    if not device_id:
        return None
    stats = scrape(
        cfg.controller_url + f"/devices/{device_id}/statistics?interval={interval}",
        cfg.token,
    )
    if isinstance(stats, dict):
        return stats
    return None


def _get_latest_series_value(series: Any) -> Optional[float]:
    if not isinstance(series, list) or not series:
        return None
    for item in reversed(series):
        if isinstance(item, dict) and item.get("y") is not None:
            return _as_float(item.get("y"), 0.0)
    return None


def get_loadavg(json):
    """returns a pseudo loadavg in range 0..1"""
    cpu = get_cpu_percent(json)
    if cpu is not None:
        return round(cpu / 100.0, 3)

    # Fallback for blackBox devices: try UISP statistics endpoint.
    device_id = get_device_id(json)
    stats = get_device_statistics(device_id, "hour")
    if not stats:
        return None

    utilization = stats.get("utilization", {})
    avg_series = utilization.get("avg") if isinstance(utilization, dict) else None
    latest = _get_latest_series_value(avg_series)
    if latest is None:
        return None
    return round(max(0.0, min(latest, 1.0)), 3)


def get_cpu_percent(json):
    """returns CPU usage in percent from 0..100"""
    raw = json.get("overview", {}).get("cpu")
    if raw is None:
        return None
    value = _as_int(raw, 0)
    return max(0, min(value, 100))


def get_ram_used_percent(json):
    """returns RAM usage in percent from 0..100"""
    raw = json.get("overview", {}).get("ram")
    if raw is None:
        return None
    value = _as_int(raw, 0)
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
                        loadavg=get_loadavg(device),
                    )
                )
    return aps
