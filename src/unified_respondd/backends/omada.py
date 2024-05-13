#!/usr/bin/env python3

from geopy.point import Point
from omada import Omada
from typing import List
from geopy.geocoders import Nominatim
from omada_respondd import config
from requests import get as rget
from omada_respondd import logger
import time
import dataclasses
import re


ffnodes = None


@dataclasses.dataclass
class Accesspoint:
    """This class contains the information of an AP.
    Attributes:
        name: The name of the AP (alias in the unifi controller).
        mac: The MAC address of the AP.
        snmp_location: The location of the AP (SNMP location in the unifi controller).
        client_count: The number of clients connected to the AP.
        client_count24: The number of clients connected to the AP via 2,4 GHz.
        client_count5: The number of clients connected to the AP via 5 GHz.
        latitude: The latitude of the AP.
        longitude: The longitude of the AP.
        model: The hardware model of the AP.
        firmware: The firmware information of the AP.
        uptime: The uptime of the AP.
        contact: The contact of the AP for example an email address.
        load_avg: The load average of the AP.
        mem_used: The used memory of the AP.
        mem_total: The total memory of the AP.
        mem_buffer: The buffer memory of the AP.
        tx_bytes: The transmitted bytes of the AP.
        rx_bytes: The received bytes of the AP."""

    name: str
    mac: str
    snmp_location: str
    client_count: int
    client_count24: int
    client_count5: int
    latitude: float
    longitude: float
    model: str
    firmware: str
    uptime: int
    contact: str
    load_avg: float
    mem_used: int
    mem_total: int
    mem_buffer: int
    tx_bytes: int
    rx_bytes: int
    gateway: str
    gateway6: str
    gateway_nexthop: str
    neighbour_macs: List[str]
    domain_code: str
    autoupdater: bool
    frequency24: int
    frequency5: int



@dataclasses.dataclass
class Accesspoints:
    """This class contains the information of all APs.
    Attributes:
        accesspoints: A list of Accesspoint objects."""

    accesspoints: List[Accesspoint]


def get_client_count_for_ap(ap_mac, clients, cfg):
    """This function returns the number total clients, 2,4Ghz clients and 5Ghz clients connected to an AP."""
    client5_count = 0
    client24_count = 0
    for client in clients:
        if re.search(cfg.ssid_regex, client.get("essid", "")):
            if client.get("ap_mac", "No mac") == ap_mac:
                if client.get("channel", 0) > 14:
                    client5_count += 1
                else:
                    client24_count += 1
    return client24_count + client5_count, client24_count, client5_count


def get_location_by_address(address, app):
    """This function returns latitude and longitude of a given address."""
    time.sleep(1)
    try:
        point = Point().from_string(address)
        return point.latitude, point.longitude
    except:
        try:
            return app.geocode(address).raw["lat"], app.geocode(address).raw["lon"]
        except:
            return get_location_by_address(address)


def scrape(url):
    """returns remote json"""
    try:
        return rget(url).json()
    except Exception as ex:
        logger.error("Error: %s" % (ex))


def get_ap_frequency(channelData):
    parts = channelData.split('/')
    # Der zweite Teil enthält die MHz-Zahl
    return int(parts[1].replace('MHz', '').strip())


def get_infos():
    """This function gathers all the information and returns a list of Accesspoint objects."""
    cfg = config.Config.from_dict(config.load_config())
    ffnodes = scrape(cfg.nodelist)
    try:
        cb = Omada(baseurl=cfg.controller_url, verify=cfg.ssl_verify, verbose=False)
        cb.login(username=cfg.username, password=cfg.password)
    except Exception as ex:
        logger.error("Error: %s" % (ex))
        return
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    aps = Accesspoints(accesspoints=[])
    for site in cb.getCurrentUser()["privilege"]["sites"]:
        csite = Omada(
            baseurl=cfg.controller_url,
            site=site["name"],
            verify=cfg.ssl_verify,
            verbose=False,
        )
        csite.login(
            username=cfg.username,
            password=cfg.password,
        )
        siteSettings = csite.getSiteSettings()
        autoupgrade = siteSettings["autoUpgrade"]["enable"]
        aps_for_site = csite.getSiteDevices()

        clients = csite.getSiteClients()
        for ap in aps_for_site:
            if (
                ap.get("name", None) is not None
                and (ap.get("status", 0) != 0 and ap.get("status", 0) != 20) ##Offline Check
                and ap.get("type") == "ap"
            ):
                moreAPInfos = csite.getSiteAP(mac=ap["mac"])

                # ssids = ap.get("vap_table", None)

                # containsSSID = False
                
                tx = 0
                rx = 0 
                
                radioTraffic2g = moreAPInfos.get("radioTraffic2g", None)
                if radioTraffic2g is not None:
                    tx = tx + radioTraffic2g.get("tx", 0)
                    rx = rx + radioTraffic2g.get("rx", 0)

                radioTraffic5g = moreAPInfos.get("radioTraffic5g", None)
                if radioTraffic5g is not None:
                    tx = tx + radioTraffic5g.get("tx", 0)
                    rx = rx + radioTraffic5g.get("rx", 0)

                client_count=ap.get("clientNum"),
                client_count24=ap.get("clientNum2g"),
                client_count5=ap.get("clientNum5g"),
                # if ssids is not None:
                # for ssid in ssids:
                # if re.search(cfg.ssid_regex, ssid.get("essid", "")):
                # containsSSID = True
                # tx = tx + ssid.get("tx_bytes", 0)
                # rx = rx + ssid.get("rx_bytes", 0)
                # if containsSSID:
                # (
                # client_count,
                # client_count24,
                # client_count5,
                # ) = get_client_count_for_ap(ap.get("mac", None), clients, cfg)
                neighbour_macs = []

                moreAPInfos.get("cpuUtil") #in Prozent 
                moreAPInfos.get("memUtil") # in Prozent


                wp2g = moreAPInfos.get("wp2g", None)
                if wp2g.get("actualChannel", None) is not None:
                    frequency24 = get_ap_frequency(wp2g.get("actualChannel"))

                wp5g = moreAPInfos.get("wp5g", None)
                if wp5g.get("actualChannel", None) is not None:
                    frequency5 = get_ap_frequency(wp5g.get("actualChannel"))


                try:
                    neighbour_macs.append(cfg.offloader_mac.get(site["name"], None))
                    offloader_id = cfg.offloader_mac.get(site["name"], "").replace(
                        ":", ""
                    )
                    offloader = list(
                        filter(
                            lambda x: x["mac"]
                            == cfg.offloader_mac.get(site["name"], ""),
                            ffnodes["nodes"],
                        )
                    )[0]
                except:
                    offloader_id = None
                    offloader = {}
                    pass

                uplink = ap.get("uplink", None)
                if uplink is not None:
                    neighbour_macs.append(uplink.replace("-",":"))

                #lldp_table = ap.get("lldp_table", None)
                #if lldp_table is not None:
                    #for lldp_entry in lldp_table:
                        #if not lldp_entry.get("is_wired", True):
                            #neighbour_macs.append(lldp_entry.get("chassis_id"))

                # Location
                lat, lon = 0, 0
                location = moreAPInfos.get("location", None)
                if location.get("longitude", None) is not None and location.get("latitude", None) is not None:
                    lon = location["longitude"]
                    lat = location["latitude"]
                
                snmp = moreAPInfos.get("snmp", None)
                if snmp.get("location", None) is not None:
                    try:
                        lat, lon = get_location_by_address(snmp["location"], geolookup)
                    except:
                        pass

                    aps.accesspoints.append(
                        Accesspoint(
                            name=ap.get("name", None),
                            mac=ap.get("mac", None).replace("-",":").lower(),
                            snmp_location=snmp.get("location", None),
                            client_count=client_count,
                            client_count24=client_count24,
                            client_count5=client_count5,
                            frequency24=frequency24,
                            frequency5=frequency5,
                            latitude=float(lat),
                            longitude=float(lon),
                            model=ap.get("model", None),
                            firmware=ap.get("version", None),
                            uptime=moreAPInfos.get("uptimeLong", None),
                            contact=snmp.get("contact", None),
                            load_avg=float(
                                ap.get("sys_stats", {}).get("loadavg_1", 0.0)
                            ),
                            mem_used=ap.get("sys_stats", {}).get("mem_used", 0),
                            mem_buffer=ap.get("sys_stats", {}).get("mem_buffer", 0),
                            mem_total=ap.get("sys_stats", {}).get("mem_total", 0),
                            tx_bytes=tx,
                            rx_bytes=rx,
                            gateway=offloader.get("gateway", None),
                            gateway6=offloader.get("gateway6", None),
                            gateway_nexthop=offloader_id,
                            neighbour_macs=neighbour_macs,
                            domain_code=offloader.get(
                                "domain", "ffmuc_omada_respondd_fallback"
                            ),
                            autoupdater=autoupgrade,
                        )
                    )
    return aps


def main():
    """This function is the main function, it's only executed if we aren't imported."""
    print(get_infos())


if __name__ == "__main__":
    main()
