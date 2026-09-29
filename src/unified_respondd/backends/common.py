#!/usr/bin/env python3
"""Helpers shared by the backends of WiFi controllers (unifi, omada)."""

import time

from geopy.point import Point
from requests import get as rget

from unified_respondd import logger

# Seconds to wait for a HTTP response, a hanging server must not block respondd
REQUEST_TIMEOUT = 30


def get_location_by_address(address, app, attempts=3):
    """This function returns latitude and longitude of a given address."""
    try:
        point = Point().from_string(address)
        return point.latitude, point.longitude
    except Exception:
        if attempts <= 0:
            raise
        try:
            time.sleep(1)
            geocode = app.geocode(address)
            return geocode.raw["lat"], geocode.raw["lon"]
        except Exception:
            return get_location_by_address(address, app, attempts - 1)


def scrape(url):
    """returns remote json"""
    try:
        return rget(url, timeout=REQUEST_TIMEOUT).json()
    except Exception as ex:
        logger.error("Error: %s" % (ex))


def get_offloader(offloader_macs, ffnodes, site_name):
    """This function returns the offloader of a site.
    Arguments:
        offloader_macs: The offloader MAC per site name from the configuration.
        ffnodes: The meshviewer.json nodelist.
        site_name: The name of the site in the controller.
    Returns:
        The configured MAC, the node id and the node of the offloader in the nodelist.
        The node id is None and the node empty if the offloader is not in the nodelist.
    """
    mac = (offloader_macs or {}).get(site_name, None)
    try:
        node = next(node for node in ffnodes["nodes"] if node["mac"] == (mac or ""))
    except Exception:  # no nodelist or offloader not in it
        return mac, None, {}
    return mac, mac.replace(":", ""), node
