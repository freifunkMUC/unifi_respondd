# unifi_respondd

This queries the API of a UniFi controller to get the current status of the Accesspoints and sends the information via the respondd protocol. Thus it can be picked up by `yanic` and other respondd queriers.

### Config File:
```yaml
controller_url: unifi.lan
controller_port: 8443
username: ubnt
password: ubnt
multicast_address: ff05::2:1001
multicast_port: 1001
interface: eth0
verbose: true
```
