#!/usr/bin/env python3

import socket
import select
import struct
import json
from typing import Dict
import zlib
import time
import re
import config
import dataclasses
from typing import List, Dict, Any, Union, Optional
import fcntl
import netifaces as ni
@dataclasses.dataclass
class FirmwareInfo:
    base: str
    release: str

@dataclasses.dataclass
class LocationInfo:
    latitude: float
    longitude: float

@dataclasses.dataclass
class NodeInfo:
    firmware: FirmwareInfo
    hostname: str
    location: LocationInfo

def get_ip_address(ifname):
		return ni.ifaddresses(ifname)[ni.AF_INET6][0]['addr']

def bindSock(config):
        addrinfo = socket.getaddrinfo(config.multicast_address, None)[0]

        s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

        s.bind(('', config.multicast_port))

        group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])

        if config.interface == None:
            mreq = group_bin + struct.pack('@I', 0)
        else:
            ip_addr = get_ip_address(config.interface)
            print(ip_addr)
            ip_addr_n = socket.inet_aton(ip_addr)
            mreq = group_bin + struct.pack("=4s", ip_addr_n)

        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
        return s


def main():
    socket = bindSock(config.Config.from_dict(config.load_config()))
    print(socket)
if __name__ == "__main__":
    main()