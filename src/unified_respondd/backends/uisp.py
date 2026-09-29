import dataclasses
from typing import Any, Dict, Optional, Tuple

from requests import get as rget

from unified_respondd import logger
from unified_respondd.backends.common import REQUEST_TIMEOUT
from unified_respondd.model import Accesspoint, Accesspoints


@dataclasses.dataclass
class ControllerConfig:
    """The UISP specific part of the configuration file.
    Attributes:
        controller_url: The UISP API URL, e.g. https://uisp.example.org/nms/api/v2.1
        token: The UISP API token.
        fallback_domain: The domain of all devices.
    """

    controller_url: str
    token: str
    fallback_domain: str = "uisp_respondd_fallback"

    @classmethod
    def from_dict(cls, cfg: Dict[str, str]) -> "ControllerConfig":
        return cls(
            controller_url=cfg["controller_url"],
            token=cfg["token"],
            fallback_domain=cfg.get("fallback_domain", "uisp_respondd_fallback"),
        )


def scrape(url, token):
    """returns remote json"""
    try:
        return rget(
            url, headers={"X-Auth-Token": token}, timeout=REQUEST_TIMEOUT
        ).json()
    except Exception as ex:
        logger.error("Error: %s" % (ex))
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


def get_apDevice(json, links):
    """returns apDevice"""
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


def get_device_status(json):
    """Extract device status: active, disconnected, unauthorized, disabled, unknown"""
    try:
        status = json.get("overview", {}).get("status")
        if status:
            return str(status).lower()
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


def get_device_statistics(cfg, device_id: str, interval: str = "hour"):
    if not device_id:
        return None
    stats = scrape(
        cfg.controller_url + f"/devices/{device_id}/statistics?interval={interval}",
        cfg.token,
    )
    if isinstance(stats, dict):
        return stats
    return None


def get_device_interfaces(cfg, device_id: str):
    if not device_id:
        return None
    interfaces = scrape(
        cfg.controller_url + f"/devices/{device_id}/interfaces", cfg.token
    )
    if isinstance(interfaces, list):
        return interfaces
    return None


def get_device_stations(cfg, device_id: str):
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


def get_traffic_bytes_from_station(
    stations: Any,
) -> Tuple[Optional[int], Optional[int]]:
    """Extract rxBytes/txBytes from primary P2P link station."""
    if not isinstance(stations, list) or not stations:
        return None, None

    station = stations[0]
    if not isinstance(station, dict):
        return None, None

    tx = (
        _as_int(station.get("txBytes"), -1)
        if station.get("txBytes") is not None
        else None
    )
    rx = (
        _as_int(station.get("rxBytes"), -1)
        if station.get("rxBytes") is not None
        else None
    )
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


def get_infos(cfg):
    aps = Accesspoints(accesspoints=[])
    neighbour_names = {}
    devices = scrape(cfg.controller_url + "/devices", cfg.token)
    if devices:
        links = scrape(cfg.controller_url + "/data-links", cfg.token)
        for device in devices:
            hostname = get_hostname(device)
            if "Router" not in hostname:
                # Skip disconnected devices
                device_status = get_device_status(device)
                if device_status == "disconnected":
                    continue

                device_id = get_device_id(device)
                device_type = get_device_type(device)

                # Fetch additional data sources
                stats = (
                    get_device_statistics(cfg, device_id, "hour") if device_id else None
                )
                interfaces = (
                    get_device_interfaces(cfg, device_id) if device_id else None
                )
                stations = get_device_stations(cfg, device_id) if device_id else None

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

                uptime = get_uptime(device, interfaces, stations)
                loadavg = get_loadavg(device, stats)
                ram_used_percent = get_ram_used_percent(device)

                # Some UISP devices are blackBox/inventory-only and do not expose
                # telemetry. For these, emit safe defaults so they appear online
                # (not offline) in meshviewer.
                if (
                    uptime is None
                    and ram_used_percent is None
                    and loadavg is None
                    and tx_bytes is None
                    and rx_bytes is None
                    and client_total is None
                    and str(device_type).lower() == "blackbox"
                ):
                    logger.debug(
                        "Emitting safe defaults for %s (%s): blackBox with no telemetry",
                        hostname,
                        get_mac(device),
                    )

                if tx_bytes is not None or rx_bytes is not None:
                    tx_bytes = tx_bytes if tx_bytes is not None else 0
                    rx_bytes = rx_bytes if rx_bytes is not None else 0

                ap = Accesspoint(
                    name=hostname,
                    mac=get_mac(device),
                    latitude=float(get_location(device)[0]),
                    longitude=float(get_location(device)[1]),
                    domain_code=cfg.fallback_domain,
                    firmware=get_firmware(device),
                    firmware_base="UISP",
                    model=get_model(device),
                    uptime=uptime if uptime is not None else 0,
                    load_avg=round(loadavg, 2) if loadavg is not None else 0.0,
                    # Meshviewer computes the memory usage from total/free/buffers,
                    # UISP only reports the usage in percent.
                    mem_total=100 * 1024,
                    mem_used=(ram_used_percent or 0) * 1024,
                    mem_buffer=0,
                    tx_bytes=tx_bytes,
                    rx_bytes=rx_bytes,
                    client_count=client_total,
                    client_count24=0 if client_total is not None else None,
                    client_count5=0 if client_total is not None else None,
                )
                aps.accesspoints.append(ap)
                neighbour_names[ap.mac] = get_apDevice(device, links)

    # UISP links devices by name, respondd by MAC
    for ap in aps.accesspoints:
        neighbour_name = neighbour_names[ap.mac]
        if neighbour_name is not None:
            ap.neighbour_macs = [
                neighbour.mac
                for neighbour in aps.accesspoints
                if neighbour.name == neighbour_name
            ]
    return aps


def main():
    """This function is the main function, it's only executed if we aren't imported."""
    from unified_respondd import config

    print(get_infos(config.Config.from_dict(config.load_config()).controller))


if __name__ == "__main__":
    main()
