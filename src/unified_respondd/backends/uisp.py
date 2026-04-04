from requests import get as rget
from typing import List, Any, Optional, Tuple
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
    device_type: str
    uptime: Optional[int]
    cpu: Optional[int]
    ram_used_percent: Optional[int]
    loadavg: Optional[float]
    tx_bytes: Optional[int]
    rx_bytes: Optional[int]
    client_total: Optional[int]


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


def get_device_type(json):
    try:
        dev_type = json.get("identification", {}).get("type")
        if dev_type:
            return str(dev_type)
        return "unknown"
    except Exception:
        return "unknown"


def get_uptime(json, interfaces: Any = None, stations: Any = None):
    """returns the uptime from overview, interfaces (serviceUptime), or P2P link stations"""
    try:
        overview = json.get("overview", {})
        uptime = overview.get("uptime")
        if uptime is None:
            uptime = overview.get("serviceUptime")
        if uptime is None:
            uptime = get_uptime_from_interfaces(interfaces)
        if uptime is None:
            uptime = get_uptime_from_station(stations)

        if uptime is None:
            return None

        uptime = _as_int(uptime, 0)
        if uptime <= 0:
            return None

        # UISP instances may report uptime in ms. Convert when value is implausibly high for seconds.
        if uptime > 10 * 365 * 24 * 60 * 60:
            uptime = int(uptime / 1000)

        # Protect against bogus values from API/device quirks that would render nonsense in meshviewer.
        if uptime > 5 * 365 * 24 * 60 * 60:
            return None
        return max(uptime, 0)
    except Exception:
        return get_uptime_from_interfaces(interfaces)


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


def get_device_interfaces(device_id: str):
    if not device_id:
        return None
    interfaces = scrape(
        cfg.controller_url + f"/devices/{device_id}/interfaces", cfg.token
    )
    if isinstance(interfaces, list):
        return interfaces
    return None


def get_device_stations(device_id: str):
    """Get P2P link stations for airFiber/wireless devices.
    
    Returns list of station objects with uptime, rxBytes, txBytes, signal, etc.
    These are remote link endpoints (connections to other devices).
    """
    if not device_id:
        return None
    stations = scrape(
        cfg.controller_url + f"/devices/aircubes/{device_id}/stations", cfg.token
    )
    if isinstance(stations, list):
        return stations
    return None


def _get_latest_series_value(series: Any) -> Optional[float]:
    if not isinstance(series, list) or not series:
        return None
    for item in reversed(series):
        if isinstance(item, dict) and item.get("y") is not None:
            return _as_float(item.get("y"), 0.0)
    return None


def _get_latest_metric_value(metric: Any) -> Optional[float]:
    if isinstance(metric, dict):
        for key in ("sum", "avg", "max", "min"):
            value = _get_latest_series_value(metric.get(key))
            if value is not None:
                return value
    return None


def get_traffic_bytes(stats: Any) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(stats, dict):
        return None, None

    total_tx = 0.0
    total_rx = 0.0
    tx_found = False
    rx_found = False

    interfaces = stats.get("interfaces", [])
    if isinstance(interfaces, list):
        for interface in interfaces:
            if not isinstance(interface, dict):
                continue

            tx_value = _get_latest_metric_value(interface.get("txBytes"))
            if tx_value is not None:
                total_tx += max(0.0, tx_value)
                tx_found = True

            rx_value = _get_latest_metric_value(interface.get("rxBytes"))
            if rx_value is not None:
                total_rx += max(0.0, rx_value)
                rx_found = True

    return (
        int(round(total_tx)) if tx_found else None,
        int(round(total_rx)) if rx_found else None,
    )


def get_traffic_bytes_from_overview(json: Any) -> Tuple[Optional[int], Optional[int]]:
    """returns traffic byte counters from device overview when available"""
    overview = json.get("overview", {}) if isinstance(json, dict) else {}

    tx_raw = overview.get("txBytes")
    rx_raw = overview.get("rxBytes")

    tx = None
    rx = None

    if tx_raw is not None:
        tx_value = _as_int(tx_raw, -1)
        if tx_value >= 0:
            tx = tx_value

    if rx_raw is not None:
        rx_value = _as_int(rx_raw, -1)
        if rx_value >= 0:
            rx = rx_value

    return tx, rx


def get_loadavg(json, stats: Any = None):
    """returns a pseudo loadavg in range 0..1"""
    cpu = get_cpu_percent(json)
    if cpu is not None:
        return round(cpu / 100.0, 3)

    # Fallback for blackBox devices: try UISP statistics endpoint.
    device_id = get_device_id(json)
    if stats is None:
        stats = get_device_statistics(device_id, "hour")
    if not stats:
        return None

    utilization = stats.get("utilization", {})
    avg_series = utilization.get("avg") if isinstance(utilization, dict) else None
    latest = _get_latest_series_value(avg_series)
    if latest is None:
        return None
    return round(max(0.0, min(latest, 1.0)), 3)


def get_uptime_from_interfaces(interfaces: Any) -> Optional[int]:
    if not isinstance(interfaces, list):
        return None

    # Prefer wireless/main interfaces where UISP commonly exposes serviceUptime.
    preferred = sorted(
        interfaces,
        key=lambda i: (
            0
            if isinstance(i, dict)
            and i.get("identification", {}).get("name") in ("main", "wlan0", "wlan")
            else 1
        ),
    )

    for interface in preferred:
        if not isinstance(interface, dict):
            continue

        wireless = interface.get("wireless")
        if not isinstance(wireless, dict):
            continue

        uptime = wireless.get("serviceUptime")
        if uptime is None:
            continue

        uptime = _as_int(uptime, 0)
        if uptime <= 0:
            continue

        if uptime > 10 * 365 * 24 * 60 * 60:
            uptime = int(uptime / 1000)
        if uptime > 5 * 365 * 24 * 60 * 60:
            return None
        return uptime

    return None


def get_uptime_from_station(stations: Any) -> Optional[int]:
    """Extract uptime from primary P2P link station.
    
    Station uptime is already in seconds (unlike overview.uptime which may be in ms).
    """
    if not isinstance(stations, list) or not stations:
        return None
    
    # Take first active station
    station = stations[0]
    if not isinstance(station, dict):
        return None
    
    uptime_sec = _as_int(station.get("uptime"), 0)
    if uptime_sec <= 0:
        return None
    
    # Reject implausible values (>5 years)
    if uptime_sec > 5 * 365 * 24 * 60 * 60:
        return None
        
    return uptime_sec


def get_traffic_bytes_from_station(stations: Any) -> Tuple[Optional[int], Optional[int]]:
    """Extract rxBytes/txBytes from primary P2P link station."""
    if not isinstance(stations, list) or not stations:
        return None, None
    
    station = stations[0]
    if not isinstance(station, dict):
        return None, None
    
    tx = _as_int(station.get("txBytes"), -1) if station.get("txBytes") is not None else None
    rx = _as_int(station.get("rxBytes"), -1) if station.get("rxBytes") is not None else None
    return tx, rx


def get_link_count(stations: Any) -> Optional[int]:
    """Count number of active P2P links."""
    if not isinstance(stations, list):
        return None
    return len(stations) if stations else None


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


def get_client_total(json):
    """returns connected client/station count when available"""
    overview = json.get("overview", {})
    for key in ("stationsCount", "linkStationsCount", "linkActiveStationsCount"):
        raw = overview.get(key)
        if raw is not None:
            value = _as_int(raw, -1)
            if value >= 0:
                return value
    return None


def get_infos():
    aps = Accesspoints(accesspoints=[])
    devices = scrape(cfg.controller_url + "/devices", cfg.token)
    if devices:
        for device in devices:
            hostname = get_hostname(device)
            if "Router" not in hostname:
                device_id = get_device_id(device)
                device_type = get_device_type(device)
                
                # Fetch additional data sources
                stats = get_device_statistics(device_id, "hour") if device_id else None
                interfaces = get_device_interfaces(device_id) if device_id else None
                stations = get_device_stations(device_id) if device_id else None
                
                # Multi-tier fallback for traffic bytes
                tx_bytes, rx_bytes = get_traffic_bytes(stats)
                if tx_bytes is None or rx_bytes is None:
                    tx_station, rx_station = get_traffic_bytes_from_station(stations)
                    if tx_bytes is None:
                        tx_bytes = tx_station
                    if rx_bytes is None:
                        rx_bytes = rx_station
                if tx_bytes is None or rx_bytes is None:
                    tx_overview, rx_overview = get_traffic_bytes_from_overview(device)
                    if tx_bytes is None:
                        tx_bytes = tx_overview
                    if rx_bytes is None:
                        rx_bytes = rx_overview

                # Multi-tier fallback for client count: use link count for P2P devices
                client_total = get_client_total(device)
                if client_total is None and stations is not None:
                    client_total = get_link_count(stations)

                aps.accesspoints.append(
                    Accesspoint(
                        name=hostname,
                        mac=get_mac(device),
                        latitude=float(get_location(device)[0]),
                        longitude=float(get_location(device)[1]),
                        neighbour=get_apDevice(device),
                        domain_code="uisp_respondd_fallback",
                        firmware=get_firmware(device),
                        model=get_model(device),
                        device_type=device_type,
                        uptime=get_uptime(device, interfaces, stations),
                        cpu=get_cpu_percent(device),
                        ram_used_percent=get_ram_used_percent(device),
                        loadavg=get_loadavg(device, stats),
                        tx_bytes=tx_bytes,
                        rx_bytes=rx_bytes,
                        client_total=client_total,
                    )
                )
    return aps
