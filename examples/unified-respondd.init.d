#!/bin/sh /etc/rc.common
# OpenWrt procd service running unified_respondd from a checkout in /tmp/unified_respondd
USE_PROCD=1
START=95
STOP=01
start_service() {
    procd_open_instance
    procd_set_param command /usr/bin/python3 /tmp/unified_respondd/respondd.py
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param env UNIFIED_RESPONDD_CONFIG_FILE=/tmp/unified_respondd/unified_respondd.yaml
    procd_close_instance
}
