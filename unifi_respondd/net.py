#!/usr/bin/env python3

import time

from geopy.point import Point
from requests import get as rget

from unifi_respondd import logger


def get_location_by_address(address, app):
    """This function returns latitude and longitude of a given address."""
    try:
        point = Point().from_string(address)
        return point.latitude, point.longitude
    except Exception:
        try:
            time.sleep(1)
            geocode = app.geocode(address)
            return geocode.raw["lat"], geocode.raw["lon"]
        except Exception:
            return get_location_by_address(address, app)


def scrape(url):
    """returns remote json"""
    try:
        return rget(url).json()
    except Exception as ex:
        logger.error("Error: %s" % (ex))
