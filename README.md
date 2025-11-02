# unifi_respondd

This queries the API of a UniFi controller to get the current status of the Accesspoints and sends the information via the respondd protocol. Thus it can be picked up by `yanic` and other respondd queriers.

## Overview

```mermaid
graph TD;
	A{"*respondd_main*"} -->| | B("*unifi_client*")
    A -->| | C("*respondd_client*")
	B -->|"RestFul API"| D("unifi_controller")
    C -->|"Subscribe"| E("multicast")
    C -->|"Send per interval / On multicast request"| F("unicast")
    G{"yanic"} -->|"Request metrics"| E
    F -->|"Receive"| G
```

## Config File:
```yaml
controller_url: unifi.lan
controller_port: 8443
username: ubnt
password: ubnt
ssid_regex: .*freifunk.*
offloader_mac:
    SiteName: 00:00:00:00:00:00
    SiteName2: 00:00:00:00:00:00
nodelist: https://MAPURL/data/meshviewer.json
version: v5
ssl_verify: True
multicast_enabled: false
multicast_address: ff05::2:1001
multicast_port: 1001
unicast_address: fe80::68ff:94ff:fe00:1504
unicast_port: 10001
interface: eth0
verbose: true
logging_config:
    formatters:
      standard:
        format: '%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    handlers:
      console:
        class: logging.StreamHandler
        formatter: standard
    root:
      handlers:
      - console
      level: DEBUG
    version: 1
fallback_domain: "unifi_respondd_fallback"  # optional
```

## Linking an Offloader to an Unifi Site by MAC Address

To link an offloader to your site in unifi_respondd, specify the MAC address of the offloader in your YAML configuration file. This enables unifi_respondd to identify the offloader device and mark it correctly on the map.

### Steps

1. Open your unifi_respondd YAML configuration file (e.g., `unifi_respondd.yaml`).
2. Add or find the section for offloader settings. (Seactionname `offloader_mac`)
3. Insert the MAC address of your offloader device like this:
   ```yaml
	offloader_mac:
    SiteName: 00:00:00:00:00:00
   ```
4. Save the YAML file.
5. Restart the unifi_respondd service to apply the changes.

<img width="468" height="607" alt="image" src="https://github.com/user-attachments/assets/dbce4cf9-c2b7-4488-8ef2-90bf86a3421a" />

## Setting Location for UniFi Devices

To set the GPS location of each UniFi Access Point (AP):

1. Open the UniFi Controller web interface.
2. Go to the **Devices** section.
3. Select the Access Point you want to configure.
4. Click on **Settings** for that AP.
5. Under **SNMP**, enter the GPS coordinates as latitude and longitude separated by a comma in the **Location** field, e.g., `48.1351, 11.5820`.
6. Save your changes.

This sets the location for the AP, helping with accurate device placement on Freifunk maps.

<img width="514" height="278" alt="image" src="https://github.com/user-attachments/assets/24180910-6428-4431-be4e-902aa56f92b6" />

## Setting Contact Information for UniFi Devices

To set contact information for each UniFi Access Point (AP):

1. Open the UniFi Controller web interface.
2. Go to the **Devices** section.
3. Select the Access Point you want to configure.
4. Click on **Settings** for that AP.
5. Under **SNMP**, enter contact details (email, phone, etc.) in the **Contact** field.
6. Save your changes.

This free-text field helps identify device ownership or provides general contact info which is shown on the Freifunk maps.


